"""Player actions. These arrive from the API as JSON, so they are Pydantic models."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from casefile.case.ids import CharacterId, EvidenceId, LocationId
from casefile.engine.scoring import Accusation


class _Action(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TalkTo(_Action):
    """Start (or resume) an interview. The first time puts the opening statement on record."""

    type: Literal["talk_to"] = "talk_to"
    suspect: CharacterId


class SearchLocation(_Action):
    type: Literal["search"] = "search"
    location: LocationId


class ShowEvidence(_Action):
    """Put an item in front of a suspect. This is how lies get caught (D04)."""

    type: Literal["show"] = "show"
    suspect: CharacterId
    evidence: EvidenceId


class Accuse(_Action):
    type: Literal["accuse"] = "accuse"
    accusation: Accusation


Action = Annotated[TalkTo | SearchLocation | ShowEvidence | Accuse, Field(discriminator="type")]


class NpcReveal(_Action):
    """What an NPC reply proposed to reveal. Not a player action, but part of the game log.

    ``reveals`` holds the raw strings the model produced, rejected ones included, so a
    replay reproduces the same accepted facts and the same rejections.
    """

    type: Literal["npc_reveal"] = "npc_reveal"
    suspect: CharacterId
    reveals: tuple[str, ...]


LogEntry = Annotated[
    TalkTo | SearchLocation | ShowEvidence | Accuse | NpcReveal, Field(discriminator="type")
]
"""One line of a game's log. Replaying the log rebuilds the game exactly."""
