"""Models for ``case.json``: the world the player can investigate.

Nothing in this file is secret on its own; the engine still sends the player only the
facts they have uncovered, and the model only the slices inside a briefing (D03).
"""

from datetime import date
from typing import Annotated, Literal

from pydantic import Field, PositiveInt, StringConstraints, model_validator

from casefile.case.base import CaseModel, NonEmptyStr, TimeSpan, Window, require_unique
from casefile.case.conditions import Condition
from casefile.case.ids import (
    CaseId,
    CharacterId,
    EvidenceId,
    FactId,
    LocationId,
    MethodId,
    MotiveId,
)

FactKind = Literal[
    "presence", "movement", "action", "object_state", "relationship", "motive", "knowledge"
]
FactTag = Literal["key", "twist", "method", "motive", "red_herring"]


class Setting(CaseModel):
    date: date
    place: NonEmptyStr
    crime_window: Window
    intro: NonEmptyStr


IdentityId = Annotated[str, StringConstraints(pattern=r"^[a-z]+(?:_[a-z]+)*$")]


class DetectiveIdentity(CaseModel):
    """One way the player can play the detective (D51). Only the name, pronouns and bio
    change; the case is the same."""

    id: IdentityId
    label: NonEmptyStr
    """What the choice is called on the cover, e.g. "Woman"."""
    first_name: NonEmptyStr
    pronouns: NonEmptyStr
    """As the suspects should use them, e.g. "she/her"."""
    bio: NonEmptyStr


class Detective(CaseModel):
    """The player character. The first identity is the default."""

    rank: NonEmptyStr
    surname: NonEmptyStr
    callsign: NonEmptyStr
    identities: tuple[DetectiveIdentity, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> "Detective":
        require_unique((i.id for i in self.identities), "detective identity")
        return self

    def identity(self, identity_id: str | None = None) -> DetectiveIdentity:
        """The identity with this ID, or the default. Raises ``KeyError`` if unknown."""
        if identity_id is None:
            return self.identities[0]
        for identity in self.identities:
            if identity.id == identity_id:
                return identity
        raise KeyError(identity_id)

    def full_name(self, identity: DetectiveIdentity) -> str:
        return f"{self.rank} {identity.first_name} {self.surname}"


class World(CaseModel):
    """The closed world: who and what exists. Anything not listed, the NPCs must not invent."""

    present: tuple[CharacterId, ...] = Field(min_length=1)
    offstage: tuple[NonEmptyStr, ...]
    named_objects: tuple[NonEmptyStr, ...]


class Character(CaseModel):
    id: CharacterId
    name: NonEmptyStr
    role: Literal["victim", "suspect"]
    age: PositiveInt
    public_bio: NonEmptyStr


class Location(CaseModel):
    id: LocationId
    name: NonEmptyStr
    description: NonEmptyStr
    accessible_when: Condition | None = None
    """Absent means the player can search it from the start."""


class Fact(CaseModel):
    """An atomic, true statement about the case: the only unit of truth (D01)."""

    id: FactId
    statement: NonEmptyStr
    """Canonical wording. The notebook shows this, never the NPC's dialogue (D14)."""
    kind: FactKind
    subjects: tuple[CharacterId, ...]
    location: LocationId | None = None
    time: TimeSpan | None = None
    tags: tuple[FactTag, ...] = ()


class DeeperRead(CaseModel):
    """More an evidence item gives up once ``when`` holds (e.g. after the player learns X)."""

    when: Condition
    establishes: tuple[FactId, ...] = Field(min_length=1)
    text: NonEmptyStr


class Evidence(CaseModel):
    id: EvidenceId
    name: NonEmptyStr
    location: LocationId
    summary: NonEmptyStr
    discover_when: Condition | None = None
    """Absent means the item is available from the start."""
    establishes: tuple[FactId, ...]
    deeper_reads: tuple[DeeperRead, ...] = ()
    text: NonEmptyStr | None = None
    """Verbatim contents, for documents the player can read (e.g. a handwritten note)."""


class MotiveOption(CaseModel):
    id: MotiveId
    label: NonEmptyStr


class MethodOption(CaseModel):
    id: MethodId
    label: NonEmptyStr


class AccusationOptions(CaseModel):
    """What the accusation form offers. The right answers live only in ``solution.json``."""

    culprits: tuple[CharacterId, ...] = Field(min_length=2)
    motives: tuple[MotiveOption, ...] = Field(min_length=2)
    methods: tuple[MethodOption, ...] = Field(min_length=2)
    max_evidence: PositiveInt

    @model_validator(mode="after")
    def _unique(self) -> "AccusationOptions":
        require_unique(self.culprits, "culprit")
        require_unique((m.id for m in self.motives), "motive")
        require_unique((m.id for m in self.methods), "method")
        return self


HintPolicy = Annotated[
    str, StringConstraints(pattern=r"^(none|auto_after_minutes:[1-9]\d*|on_request:[1-9]\d*)$")
]


class DifficultyProfile(CaseModel):
    """Difficulty changes only the help the player gets, never the truth (D11)."""

    contradictions: Literal["auto_flag", "side_by_side", "off"]
    hints: HintPolicy
    notebook: Literal["by_suspect_and_time", "by_suspect", "flat"]
    evidence_picker: Literal["relevant_only", "all_found"]


class DifficultyProfiles(CaseModel):
    easy: DifficultyProfile
    normal: DifficultyProfile
    hard: DifficultyProfile


class Case(CaseModel):
    """Top-level model for ``case.json``."""

    schema_version: Literal["1.0"]
    case_id: CaseId
    title: NonEmptyStr
    setting: Setting
    detective: Detective
    world: World
    characters: tuple[Character, ...] = Field(min_length=2)
    locations: tuple[Location, ...] = Field(min_length=1)
    facts: tuple[Fact, ...] = Field(min_length=1)
    evidence: tuple[Evidence, ...] = Field(min_length=1)
    accusation_options: AccusationOptions
    difficulty_profiles: DifficultyProfiles

    @model_validator(mode="after")
    def _unique_ids(self) -> "Case":
        require_unique((c.id for c in self.characters), "character")
        require_unique((loc.id for loc in self.locations), "location")
        require_unique((f.id for f in self.facts), "fact")
        require_unique((e.id for e in self.evidence), "evidence")
        return self
