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
