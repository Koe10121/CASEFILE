"""Runtime configuration, read from the environment and an optional ``backend/.env``.

Secrets live only in the environment or ``.env`` (which git ignores); see
``.env.example`` for every setting.
"""

from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="CASEFILE_", extra="ignore", frozen=True
    )

    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    """Optional: without it the Anthropic SDK falls back to its own credential chain."""
    model: str = "claude-opus-5-5"
    effort: Effort = "low"
    """Interrogation is chat: low effort keeps replies fast and cheap. Raise it if evals
    show the suspect losing track of its lies."""
    max_output_tokens: int = Field(default=2048, gt=0)
    session_token_budget: int = Field(default=400_000, gt=0)
    """Hard cap on model tokens (input + output) per game session."""
    request_timeout_s: float = Field(default=60.0, gt=0)
