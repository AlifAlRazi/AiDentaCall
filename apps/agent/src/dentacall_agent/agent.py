"""DentaCall Conversational Agent orchestrating LLM tool calling, state, and safety guards."""

import json
import logging
import uuid
from typing import Any

from dentacall_agent.prompt import build_system_prompt
from dentacall_agent.providers.base import (
    ChatMessage,
    LLMProvider,
    LLMResponse,
)
from dentacall_agent.providers.factory import get_llm_provider
from dentacall_agent.state import ConversationState
from dentacall_agent.tools import AgentToolDispatcher

logger = logging.getLogger(__name__)


class DentaCallAgent:
    """The brain of DentaCall: orchestrates multi-turn conversation and tool execution."""

    def __init__(
        self,
        provider: LLMProvider | None = None,
        dispatcher: AgentToolDispatcher | None = None,
        state: ConversationState | None = None,
        max_tool_steps: int = 10,
        temperature: float = 0.2,
    ) -> None:
        self.provider = provider or get_llm_provider()
        self.dispatcher = dispatcher or AgentToolDispatcher()
        self.state = state or ConversationState()
        self.max_tool_steps = max_tool_steps
        self.temperature = temperature
        self._initialized = False

    async def initialize(self, caller_phone: str | None = None) -> None:
        """Initialize system prompt and seed caller identity if known."""
        if self._initialized:
            return

        system_prompt = build_system_prompt()
        self.state.history.append(ChatMessage(role="system", content=system_prompt))

        if caller_phone:
            self.state.caller_phone = caller_phone

        self._initialized = True

    async def start_call(self, caller_phone: str | None = None) -> str:
        """Generate the opening greeting when a call connects."""
        await self.initialize(caller_phone=caller_phone)

        # Pre-lookup patient if phone is already known from Caller ID
        if caller_phone:
            lookup = await self.dispatcher.execute_tool(
                "find_patient",
                {"phone": caller_phone},
                call_id=self.state.call_id,
            )
            self.state.tool_calls_record.append(
                {
                    "name": "find_patient",
                    "arguments": {"phone": caller_phone},
                    "step": 0,
                }
            )
            if lookup.get("success") and lookup.get("data", {}).get("patients"):
                patient = lookup["data"]["patients"][0]
                self.state.record_caller_identity(
                    name=f"{patient['first_name']} {patient['last_name']}",
                    phone=patient["phone"],
                    patient_id=uuid.UUID(patient["patient_id"]),
                )
                greeting_prompt = f"The caller phone is {caller_phone}. You matched existing patient {patient['first_name']} {patient['last_name']}. Greet them warmly by first name and ask how you can help."
                self.state.add_message("user", content=greeting_prompt)
                resp = await self.step_internal()
                return resp

        # Standard clinic greeting
        greeting = "Good day! Thank you for calling Grand Canal Dental Clinic. My name is DentaCall Receptionist. How can I help you today?"
        self.state.add_message("assistant", content=greeting)
        return greeting

    async def step(self, user_utterance: str) -> str:
        """Process an incoming caller utterance and return the spoken response."""
        from dentacall_core.tracing import trace_turn

        await self.initialize()

        self.state.turn_count += 1
        self.state.add_message("user", content=user_utterance)

        turn_id = str(uuid.uuid4())
        with trace_turn(
            call_id=self.state.call_id,
            turn_id=turn_id,
            turn_number=self.state.turn_count,
            user_input=user_utterance,
        ):
            return await self.step_internal()

    async def step_internal(self) -> str:
        """Internal tool-calling execution loop with max steps."""
        from dentacall_core.tracing import trace_llm

        tools = self.dispatcher.get_definitions()

        for step_idx in range(self.max_tool_steps):
            response: LLMResponse = await self.provider.generate(
                messages=self.state.history,
                tools=tools,
                temperature=self.temperature,
            )
            self.state.prompt_tokens += response.prompt_tokens
            self.state.completion_tokens += response.completion_tokens

            # Record OpenTelemetry LLM span
            with trace_llm(
                model=getattr(self.provider, "model", "gpt-4o-mini"),
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
            ):
                pass

            if not response.has_tool_calls:
                # LLM finished reasoning and generated spoken text for the caller
                final_text = response.content or ""
                self.state.add_message("assistant", content=final_text)
                return final_text

            # Assistant requested one or more tool calls
            self.state.history.append(
                ChatMessage(
                    role="assistant",
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
            )

            # Execute all requested tools sequentially
            for tool_call in response.tool_calls:
                tool_name = tool_call.function_name
                arguments = tool_call.arguments
                self.state.tool_calls_record.append(
                    {
                        "name": tool_name,
                        "arguments": arguments,
                        "step": step_idx + 1,
                    }
                )

                # Generate deterministic idempotency key for booking actions
                idempotency_key = None
                if tool_name in (
                    "book_appointment",
                    "reschedule_appointment",
                    "cancel_appointment",
                ):
                    action_id = (
                        arguments.get("appointment_id") or arguments.get("start_time_utc") or "act"
                    )
                    idempotency_key = f"{tool_name}-{self.state.call_id}-{action_id}"

                logger.info(
                    "[call_id=%s] Agent executing tool '%s' (step %d/%d)",
                    self.state.call_id,
                    tool_name,
                    step_idx + 1,
                    self.max_tool_steps,
                )

                tool_result = await self.dispatcher.execute_tool(
                    name=tool_name,
                    arguments=arguments,
                    call_id=self.state.call_id,
                    idempotency_key=idempotency_key,
                )

                # Update conversation state with tool findings
                self._update_state_from_tool(tool_name, arguments, tool_result)

                # Return tool result to the LLM
                self.state.history.append(
                    ChatMessage(
                        role="tool",
                        name=tool_name,
                        tool_call_id=tool_call.id,
                        content=json.dumps(tool_result),
                    )
                )

        # Loop fallback if maximum steps exceeded
        fallback_msg = "I am gathering the latest clinic information. Please give me one moment."
        self.state.add_message("assistant", content=fallback_msg)
        return fallback_msg

    def _update_state_from_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        """Update internal conversation state based on tool outcomes."""
        if not result.get("success"):
            return

        data = result.get("data", {})

        if tool_name == "find_patient":
            patients = data.get("patients", [])
            if len(patients) == 1:
                p = patients[0]
                self.state.record_caller_identity(
                    name=f"{p.get('first_name')} {p.get('last_name')}",
                    phone=p.get("phone"),
                    patient_id=uuid.UUID(p["patient_id"]) if "patient_id" in p else None,
                )

        elif tool_name == "hold_slot":
            if "hold_id" in data:
                self.state.active_hold_id = uuid.UUID(data["hold_id"])
            if "service_code" in data:
                self.state.service_code = data["service_code"]
            if "start_time_utc" in data:
                self.state.start_time_utc = data["start_time_utc"]

        elif tool_name == "book_appointment":
            self.state.clear_pending_action()
            self.state.active_hold_id = None

        elif tool_name in ("reschedule_appointment", "cancel_appointment"):
            self.state.clear_pending_action()

        elif tool_name == "transfer_to_human":
            self.state.is_emergency = "EMERGENCY" in str(arguments.get("reason", "")).upper()
