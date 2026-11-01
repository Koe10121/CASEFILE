"""The NPC output contract (D14): one ``respond`` call per reply."""

from pydantic import BaseModel, ConfigDict, Field

MAX_DIALOGUE_CHARS = 1200


class NpcReply(BaseModel):
    """What a provider returns. ``reveals`` and ``demeanor`` come before ``dialogue`` so the
    backend can validate the IDs before any dialogue streams to the player.

    ``reveals`` is plain strings: model output is untrusted until the engine checks it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    reveals: tuple[str, ...] = ()
    demeanor: str = Field(min_length=1, max_length=40)
    dialogue: str = Field(min_length=1, max_length=MAX_DIALOGUE_CHARS)


class Exchange(BaseModel):
    """One question and answer, for the conversation history sent with each turn."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    detective: str
    suspect: str
    demeanor: str


class Usage(BaseModel):
    """What one provider call cost. The mock reports zeros."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    latency_ms: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class NpcTurn(BaseModel):
    """A provider's answer: the model's reply plus what producing it cost."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reply: NpcReply
    usage: Usage = Usage()


class ProviderError(Exception):
    """The provider could not produce a valid reply. Nothing in the game changed.

    ``kind`` is for logs and evals: ``refusal``, ``malformed``, ``truncated`` or ``api``.
    """

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
