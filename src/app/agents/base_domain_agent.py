from abc import ABC, abstractmethod

from ..models.agent_request import AgentRequest
from ..models.agent_result import AgentResult


class BaseDomainAgent(ABC):
    """
    Abstract base for stubbed domain agents (asset, event, crew, reliability).
    Phase 0: no DB, no tools. Subclasses return canned AgentResult data in the real shape.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Domain agent name (e.g., 'asset', 'event', 'crew', 'reliability')."""

    @abstractmethod
    async def handle(self, request: AgentRequest) -> AgentResult:
        """Handle a dispatched request and return a populated AgentResult. Never a string."""
        raise NotImplementedError
