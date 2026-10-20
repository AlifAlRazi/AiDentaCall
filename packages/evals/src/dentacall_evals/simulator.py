"""Simulated caller representing patient persona and conversational intent."""

import logging
from typing import Any

from dentacall_agent.providers.base import ChatMessage, LLMProvider

from dentacall_evals.models import ScenarioCaller

logger = logging.getLogger(__name__)


class SimulatedCaller:
    """Simulates a human caller with persona, goal, and script support."""

    def __init__(
        self,
        caller_spec: ScenarioCaller,
        provider: LLMProvider | None = None,
        use_llm: bool = False,
    ) -> None:
        self.spec = caller_spec
        self.provider = provider
        self.use_llm = use_llm and (provider is not None)
        self.history: list[ChatMessage] = []

    def _build_system_prompt(self) -> str:
        return (
            "You are a simulated telephone caller interacting with the receptionist at "
            "Grand Canal Dental Clinic in Dublin, Ireland.\n\n"
            f"CALLER PERSONA: {self.spec.persona}\n"
            f"CALLER GOAL: {self.spec.goal}\n"
            f"YOUR NAME: {self.spec.name}\n"
            f"YOUR PHONE: {self.spec.phone or 'Private/Unknown'}\n"
            f"YOUR DATE OF BIRTH: {self.spec.dob or 'Not specified'}\n\n"
            "RULES FOR SIMULATOR:\n"
            "1. Stay strictly in character as the caller.\n"
            "2. Respond directly to the receptionist's latest question or statement.\n"
            "3. Speak naturally in 1-2 short spoken sentences, as if over a phone call.\n"
            "4. NEVER mention that you are an AI, simulated caller, or testing prompt.\n"
            "5. If your goal is achieved (e.g. appointment confirmed or question answered), "
            "say thank you and goodbye."
        )

    async def get_response(
        self,
        turn_idx: int,
        agent_utterance: str,
        dialog_history: list[dict[str, Any]] | None = None,
    ) -> str:
        """Produce the caller's next utterance for the given turn."""
        # 1. Scripted execution mode: directly use pre-formulated script
        if not self.use_llm or self.provider is None:
            if turn_idx < len(self.spec.scripted_turns):
                return self.spec.scripted_turns[turn_idx]
            return "Thank you very much, goodbye."

        # 2. Dynamic LLM execution mode
        try:
            if not self.history:
                self.history.append(ChatMessage(role="system", content=self._build_system_prompt()))

            self.history.append(ChatMessage(role="user", content=agent_utterance))

            response = await self.provider.generate(
                messages=self.history,
                temperature=0.3,
                max_tokens=150,
            )

            caller_text = (response.content or "").strip()
            if not caller_text:
                caller_text = (
                    self.spec.scripted_turns[turn_idx]
                    if turn_idx < len(self.spec.scripted_turns)
                    else "Yes, that sounds perfect. Thank you."
                )

            self.history.append(ChatMessage(role="assistant", content=caller_text))
            return caller_text

        except Exception as exc:
            logger.warning("Dynamic LLM caller simulation failed, falling back to script: %s", exc)
            if turn_idx < len(self.spec.scripted_turns):
                return self.spec.scripted_turns[turn_idx]
            return "Thank you, that helps. Goodbye."
