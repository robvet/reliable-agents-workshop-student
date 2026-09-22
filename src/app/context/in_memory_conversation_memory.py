from .i_conversation_memory import IConversationMemory


class InMemoryConversationMemory(IConversationMemory):
    """In-memory reference store: process-local, lost on restart, one list of turns per
    conversation id. Not concurrency-hardened - fine for local/dev, not production."""

    def __init__(self) -> None:
        self._store: dict[str, list[dict]] = {}

    def load(self, conversation_id: str) -> list[dict]:
        # Return a copy so callers can't mutate the store by touching the returned list.
        return list(self._store.get(conversation_id, []))

    def append(self, conversation_id: str, turn: dict) -> None:
        self._store.setdefault(conversation_id, []).append(turn)
