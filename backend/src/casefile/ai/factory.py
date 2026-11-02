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
            return OllamaNpc(settings), settings.local_session_token_budget
        case "claude":
            return ClaudeNpc(settings), settings.session_token_budget


def setup_problem(ai: Ai, settings: Settings) -> str | None:
    """What the player must fix before this provider can play, or ``None``."""
    match ai:
        case "mock":
            return None
        case "ollama":
            return OllamaNpc(settings).problem()
        case "claude":
            if settings.anthropic_api_key is None:
                return "--ai claude needs ANTHROPIC_API_KEY (see backend/.env.example)"
            return None
