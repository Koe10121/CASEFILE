"""Runtime configuration, read from the environment and an optional ``backend/.env``.

Secrets live only in the environment or ``.env`` (which git ignores); see
``.env.example`` for every setting.
"""

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Effort = Literal["low", "medium", "high", "xhigh", "max"]
Ai = Literal["mock", "ollama", "claude"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="CASEFILE_", extra="ignore", frozen=True
    )

    ai: Ai = "mock"
    """Who plays the suspects: scripted (free, no setup), a local model (free), or Claude."""

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    """Any Ollama model that supports structured outputs. The eval harness picks the best."""

    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    """Optional: without it the Anthropic SDK falls back to its own credential chain."""
    claude_model: str = "claude-opus-5-5"
    effort: Effort = "low"
    """Interrogation is chat: low effort keeps replies fast and cheap. Raise it if evals
    show the suspect losing track of its lies."""
    max_output_tokens: int = Field(default=2048, gt=0)
    session_token_budget: int = Field(default=400_000, gt=0)
    """Hard cap on model tokens (input + output) per game session."""
    request_timeout_s: float = Field(default=120.0, gt=0)
    """Generous because a local model on a laptop can take a while per reply."""

    max_games: int = Field(default=200, gt=0)
    """Games the API server holds in memory at once. A new game past this is refused."""
    game_idle_minutes: float = Field(default=120, gt=0)
    """The API server forgets a game nobody has touched for this long."""
