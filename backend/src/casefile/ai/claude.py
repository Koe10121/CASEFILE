"""The Claude provider: plays a suspect through the Anthropic Messages API.

One request per reply. The reply's shape is guaranteed by structured outputs
(``output_config.format``) rather than a forced tool call, which current models no
longer accept (D35). The briefing is the only game data that leaves the process.
"""

import json
import time
from collections.abc import Sequence

import anthropic
from anthropic.types.beta import BetaMessage, BetaMessageParam, BetaTextBlockParam
from pydantic import ValidationError

from casefile.ai.contract import Exchange, NpcReply, NpcTurn, ProviderError, Usage
from casefile.ai.prompt import (
    REPLY_SCHEMA,
    detective_turn,
    stable_instructions,
    suspect_turn,
    turn_state,
)
from casefile.engine.briefing import SuspectBriefing
from casefile.settings import Settings

FIRST_MEETING_CUE = "(The detective sits down across from you and waits.)"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeNpc:
    def __init__(self, settings: Settings, client: anthropic.Anthropic | None = None) -> None:
        self._settings = settings
        key = settings.anthropic_api_key
        self._client = client or anthropic.Anthropic(
            api_key=key.get_secret_value() if key else None,
            timeout=settings.request_timeout_s,
        )

    def respond(
        self, briefing: SuspectBriefing, history: Sequence[Exchange], player_text: str
    ) -> NpcTurn:
        started = time.monotonic()
        try:
            message = self._client.beta.messages.create(
                model=self._settings.model,
                max_tokens=self._settings.max_output_tokens,
                system=self._system(briefing),
                messages=self._messages(history, player_text),
                output_config={
                    "effort": self._settings.effort,
                    "format": {"type": "json_schema", "schema": REPLY_SCHEMA},
                },
                # If a safety classifier declines, the API retries on a fallback model.
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.APIStatusError as exc:
            raise ProviderError("api", f"HTTP {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("api", f"connection failed: {exc}") from exc
        latency_ms = int((time.monotonic() - started) * 1000)
        return NpcTurn(reply=self._parse(message), usage=self._usage(message, latency_ms))

    # ------------------------------------------------------------ request

    @staticmethod
    def _system(b: SuspectBriefing) -> list[BetaTextBlockParam]:
        return [
            # Identical on every turn with this suspect, so it is cached.
            {
                "type": "text",
                "text": stable_instructions(b),
                "cache_control": {"type": "ephemeral"},
            },
            {"type": "text", "text": turn_state(b)},
        ]

    @staticmethod
    def _messages(history: Sequence[Exchange], player_text: str) -> list[BetaMessageParam]:
        messages: list[BetaMessageParam] = []
        for ex in history:
            messages.append(
                {"role": "user", "content": detective_turn(ex.detective or FIRST_MEETING_CUE)}
            )
            messages.append({"role": "assistant", "content": suspect_turn(ex.suspect, ex.demeanor)})
        messages.append(
            {"role": "user", "content": detective_turn(player_text or FIRST_MEETING_CUE)}
        )
        return messages

    # ------------------------------------------------------------ response

    @staticmethod
    def _parse(message: BetaMessage) -> NpcReply:
        if message.stop_reason == "refusal":
            raise ProviderError("refusal", "the model declined to answer")
        if message.stop_reason == "max_tokens":
            raise ProviderError("truncated", "the reply hit max_tokens")
        text = next((b.text for b in message.content if b.type == "text"), None)
        if text is None:
            raise ProviderError("malformed", "no text block in the reply")
        try:
            return NpcReply.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise ProviderError("malformed", str(exc).splitlines()[0]) from exc

    @staticmethod
    def _usage(message: BetaMessage, latency_ms: int) -> Usage:
        u = message.usage
        return Usage(
            input_tokens=u.input_tokens
            + (u.cache_read_input_tokens or 0)
            + (u.cache_creation_input_tokens or 0),
            output_tokens=u.output_tokens,
            cache_read_input_tokens=u.cache_read_input_tokens or 0,
            latency_ms=latency_ms,
        )
