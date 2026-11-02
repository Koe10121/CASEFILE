"""Suspects played by the Ollama on the player's own computer (D60).

The public server has no GPU, but a player may have Ollama at home. The server can't
reach it, so the player's browser carries the call: a question first comes back with
the exact Ollama request to make (``RelayNeededError``), the browser sends it to Ollama
on the player's machine, and then asks again with Ollama's reply attached. The reply is
then checked like any other: the reply contract, the culprit's guard, grounding and the
engine's reveal rules (D41, D42). A player who forges a reply gets nothing the suspect
couldn't have said anyway.

The request carries the suspect's briefing, so a curious player can read it in their
browser. That is the price of free AI suspects on a server without a GPU; Kole accepted
it on 2026-11-02.
"""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from casefile.ai.contract import Exchange, NpcTurn, ProviderError, Usage
from casefile.ai.prompt import (
    REPLY_SCHEMA,
    conversation,
    parse_reply,
    stable_instructions,
    turn_state,
)
from casefile.engine.briefing import SuspectBriefing


def chat_request(
    briefing: SuspectBriefing,
    history: Sequence[Exchange],
    player_text: str,
    *,
    model: str,
    max_output_tokens: int,
) -> dict[str, Any]:
    """The body of an Ollama ``/api/chat`` request for one suspect reply."""
    system = f"{stable_instructions(briefing)}\n\n{turn_state(briefing)}"
    messages = [{"role": "system", "content": system}] + [
        {"role": role, "content": text} for role, text in conversation(history, player_text)
    ]
    return {
        "model": model,
        "messages": messages,
        "format": REPLY_SCHEMA,
        "stream": False,
        "options": {"num_predict": max_output_tokens},
    }


class OllamaMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content: str = Field(max_length=20_000)


class OllamaReply(BaseModel):
    """The fields of Ollama's ``/api/chat`` reply that we use."""

    model_config = ConfigDict(extra="ignore")

    message: OllamaMessage
    done_reason: str | None = None
    prompt_eval_count: int = Field(default=0, ge=0)
    eval_count: int = Field(default=0, ge=0)


def turn_from(reply: OllamaReply, latency_ms: int = 0) -> NpcTurn:
    if reply.done_reason == "length":
        raise ProviderError("truncated", "the reply hit the output token limit")
    usage = Usage(
        input_tokens=reply.prompt_eval_count, output_tokens=reply.eval_count, latency_ms=latency_ms
    )
    return NpcTurn(reply=parse_reply(reply.message.content), usage=usage)


class RelayNeededError(Exception):
    """Ask the player's Ollama this, then ask the question again with its reply."""

    def __init__(self, request: dict[str, Any]) -> None:
        super().__init__("relay this request to Ollama")
        self.request = request


_relayed: ContextVar[OllamaReply | None] = ContextVar("relayed", default=None)


@contextmanager
def relayed(reply: OllamaReply | None) -> Iterator[None]:
    """Make ``reply`` the answer to the next model call in this block, in this thread."""
    token = _relayed.set(reply)
    try:
        yield
    finally:
        _relayed.reset(token)


class RelayedOllama:
    def __init__(self, model: str, max_output_tokens: int) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens

    def respond(
        self, briefing: SuspectBriefing, history: Sequence[Exchange], player_text: str
    ) -> NpcTurn:
        reply = _relayed.get()
        if reply is None:
            raise RelayNeededError(
                chat_request(
                    briefing,
                    history,
                    player_text,
                    model=self._model,
                    max_output_tokens=self._max_output_tokens,
                )
            )
        return turn_from(reply)
