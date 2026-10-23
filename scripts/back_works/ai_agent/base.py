from abc import ABC, abstractmethod
from scripts.utils.data_classes import Decision, Ticket


class LLMService(ABC):
    """Abstract interface for LLM ticket decision agent."""

    @abstractmethod
    async def decide(self, ticket: Ticket) -> Decision:
        """
        Processes a ticket using tool calling and returns a structured Decision.
        """
        pass
