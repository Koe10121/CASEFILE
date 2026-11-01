"""Build the provider a setting names. Shared by the terminal game and the eval harness."""

from casefile.ai.claude import ClaudeNpc
from casefile.ai.mock import MockNpc
from casefile.ai.ollama import OllamaNpc
from casefile.ai.provider import NpcProvider
from casefile.settings import Ai, Settings


def make_provider(ai: Ai, settings: Settings) -> tuple[NpcProvider, int | None]:
    """The provider and its session token budget. The mock is free, so it has none."""
    match ai:
        case "mock":
            return MockNpc(), None
        case "ollama":
            return OllamaNpc(settings), settings.session_token_budget
        case "claude":
            return ClaudeNpc(settings), settings.session_token_budget
