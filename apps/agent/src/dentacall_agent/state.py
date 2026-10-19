"""Conversation state tracking for caller identity, intent, and confirmation status."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from dentacall_agent.providers.base import ChatMessage


@dataclass
class ConversationState:
    """Tracks caller identity, operational intent, and multi-turn state."""

    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    caller_phone: str | None = None
    caller_name: str | None = None
    patient_id: uuid.UUID | None = None
    intent: str | None = None

    # Collected appointment parameters
    service_code: str | None = None
    dentist_id: uuid.UUID | None = None
    start_time_utc: str | None = None
    active_hold_id: uuid.UUID | None = None

    # Confirmation and safety guards
    pending_confirmation: bool = False
    pending_action_type: str | None = None  # "BOOK", "RESCHEDULE", "CANCEL"
    pending_action_details: dict[str, Any] = field(default_factory=dict)
    is_emergency: bool = False

    # Counters and history
    turn_count: int = 0
    history: list[ChatMessage] = field(default_factory=list)

    def record_caller_identity(
        self,
        name: str | None = None,
        phone: str | None = None,
        patient_id: uuid.UUID | None = None,
    ) -> None:
        """Update verified caller details."""
        if name:
            self.caller_name = name
        if phone:
            self.caller_phone = phone
        if patient_id:
            self.patient_id = patient_id

    def set_pending_action(self, action_type: str, details: dict[str, Any]) -> None:
        """Set an unconfirmed write action awaiting explicit caller confirmation."""
        self.pending_confirmation = True
        self.pending_action_type = action_type
        self.pending_action_details = details

    def clear_pending_action(self) -> None:
        """Reset the pending confirmation state."""
        self.pending_confirmation = False
        self.pending_action_type = None
        self.pending_action_details = {}

    def add_message(self, role: str, content: str | None = None, **kwargs: Any) -> ChatMessage:
        """Append a message to the conversation history."""
        msg = ChatMessage(role=role, content=content, **kwargs)
        self.history.append(msg)
        return msg
