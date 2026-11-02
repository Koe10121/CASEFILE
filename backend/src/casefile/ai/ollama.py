"""The local-model provider: a suspect played by a model running in Ollama. Free (D39).

Same prompt and the same reply contract as the Claude provider. Ollama constrains the
output to ``REPLY_SCHEMA`` (its ``format`` field), and the reply is still checked
against ``NpcReply`` and then by the engine, because a small model can still say odd
things inside a valid shape.

There is no explicit prompt caching: Ollama reuses the model's memory of the longest
matching prefix by itself, so the stable instructions still go first.
"""

import time
from collections.abc import Sequence

import httpx2
from pydantic import BaseModel, ConfigDict, ValidationError

from casefile.ai.contract import Exchange, NpcTurn, ProviderError
from casefile.ai.relay import OllamaReply, chat_request, turn_from
from casefile.engine.briefing import SuspectBriefing
from casefile.settings import Settings


class _Model(BaseModel):
    name: str


class _Tags(BaseModel):
    """The fields of Ollama's ``/api/tags`` reply (installed models) that we use."""

    model_config = ConfigDict(extra="ignore")

    models: list[_Model]


class OllamaNpc:
    def __init__(self, settings: Settings, client: httpx2.Client | None = None) -> None:
        self._settings = settings
        self._client = client or httpx2.Client(
            base_url=settings.ollama_url, timeout=settings.request_timeout_s
        )

    def problem(self) -> str | None:
        """Why this provider can't play right now, or ``None``. Checked once at startup,
        so a missing Ollama fails with instructions instead of on the first question."""
        model = self._settings.ollama_model
        try:
            response = self._client.get("/api/tags", timeout=5)
            response.raise_for_status()
            installed = {m.name for m in _Tags.model_validate_json(response.content).models}
        except (httpx2.HTTPError, ValidationError):
            return (
                f"Ollama isn't answering at {self._settings.ollama_url}. Start the Ollama app "
                "(or run `ollama serve`), or play with scripted suspects: --ai mock"
            )
        if model not in installed and f"{model}:latest" not in installed:
            return f"Ollama doesn't have {model} yet. Run: ollama pull {model}"
        return None

    def respond(
        self, briefing: SuspectBriefing, history: Sequence[Exchange], player_text: str
    ) -> NpcTurn:
        body = chat_request(
            briefing,
            history,
            player_text,
            model=self._settings.ollama_model,
            max_output_tokens=self._settings.max_output_tokens,
        )
        started = time.monotonic()
        try:
            response = self._client.post("/api/chat", json=body)
            response.raise_for_status()
        except httpx2.HTTPStatusError as exc:
            detail = exc.response.text[:200]
            raise ProviderError("api", f"HTTP {exc.response.status_code}: {detail}") from exc
        except httpx2.HTTPError as exc:
            raise ProviderError("api", f"is Ollama running? {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)

        try:
            chat = OllamaReply.model_validate_json(response.content)
        except ValidationError as exc:
            raise ProviderError("malformed", "unexpected response from Ollama") from exc
        return turn_from(chat, latency_ms)
