"""Runtime configuration, read from the environment and an optional ``backend/.env``.

Secrets live only in the environment or ``.env`` (which git ignores); see
``.env.example`` for every setting.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Effort = Literal["low", "medium", "high", "xhigh", "max"]
Ai = Literal["mock", "ollama", "claude"]

BACKEND = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="CASEFILE_", extra="ignore", frozen=True
    )

    ai: Ai = "ollama"
    """Who plays the suspects: a local model (free, the default, D50), Claude, or scripted
    suspects (``mock``: no setup at all, and what the tests use)."""

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
    """Hard cap on Claude tokens (input + output) per game session: a cost cap."""
    local_session_token_budget: int = Field(default=2_000_000, gt=0)
    """The same cap for a local model, where tokens cost nothing but GPU time. Still
    capped so a runaway or jailbreak-spamming session ends (D49)."""
    request_timeout_s: float = Field(default=120.0, gt=0)
    """Generous because a local model on a laptop can take a while per reply."""

    max_games: int = Field(default=200, gt=0)
    """Games the API server holds in memory at once. A new game past this is refused."""
    game_idle_minutes: float = Field(default=120, gt=0)
    """The API server drops a game from memory after this long untouched. A saved game
    is loaded again from ``save_file`` the next time it is played."""
    save_file: Path | None = BACKEND / "games.sqlite3"
    """Where the API server saves games (D53). Set it empty to keep games in memory only."""
    keep_saves_days: float = Field(default=30, gt=0)
    """A saved game nobody has played for this long is deleted."""

    new_games_per_hour: int = Field(default=30, gt=0)
    """Rate limit per visitor (D57): games started in any hour."""
    moves_per_minute: int = Field(default=120, gt=0)
    """Rate limit per visitor (D57): moves (talk, ask, search, show, hint, accuse) in
    any minute, across all their games. A player rarely makes more than a few."""
    behind_proxy: bool = False
    """Set on a host that puts a proxy in front (Render, Fly, Hugging Face), so the
    rate limits see the visitor's address instead of the proxy's."""
    web_dir: Path | None = None
    """Serve the built web game from here too (``--web``). The Docker image sets it."""

    @field_validator("save_file", "web_dir", mode="before")
    @classmethod
    def _empty_means_none(cls, value: object) -> object:
        return None if value == "" else value
