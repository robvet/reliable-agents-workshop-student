from abc import ABC, abstractmethod


class IConversationMemory(ABC):
    """Cross-turn store of prior turns, keyed by conversation id.

    The swap-your-own-store extension point: the in-memory reference impl ships with the
    harness; a customer plugs in Redis/Cosmos/their store by implementing this interface.
    """

    @abstractmethod
    def load(self, conversation_id: str) -> list[dict]:
        """Return this conversation's prior turns in order (empty list if none)."""

    @abstractmethod
    def append(self, conversation_id: str, turn: dict) -> None:
        """Append one completed turn to this conversation."""
