"""The HTTP API's request and response shapes: the player's side of the game.

Everything here is something the player is allowed to see right now. The views are
built from the game state by ``views.py`` (D44); nothing in this file is a case model,
so a case model can't reach the browser whole by accident.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from casefile.case.ids import CharacterId, EvidenceId, FactId, LieId, LocationId
from casefile.case.world import DifficultyProfile
from casefile.engine.scoring import Accusation

Difficulty = Literal["easy", "normal", "hard"]


class _Out(BaseModel):
    model_config = ConfigDict(frozen=True)


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ------------------------------------------------------------------ requests


class NewGame(_In):
    difficulty: Difficulty = "normal"


class TalkRequest(_In):
    suspect: CharacterId


class AskRequest(_In):
    text: str = Field(min_length=1)
    """The 500-character cap is the session's rule, so its message is the session's too."""


class SearchRequest(_In):
    location: LocationId


class ShowRequest(_In):
    """Shown to the suspect currently being interviewed."""

    evidence: EvidenceId


class AccuseRequest(_In):
    accusation: Accusation


# ------------------------------------------------------------------ the case


class DetectiveOut(_Out):
    name: str
    callsign: str
    bio: str


class PersonOut(_Out):
    id: CharacterId
    name: str
    age: int
    bio: str
    role: Literal["victim", "suspect"]


class OptionOut(_Out):
    id: str
    label: str


class AccusationOptionsOut(_Out):
    culprits: tuple[CharacterId, ...]
    motives: tuple[OptionOut, ...]
    methods: tuple[OptionOut, ...]
    max_evidence: int


class CaseOut(_Out):
    """What the case file's cover shows. The same for every game of this case."""

    id: str
    title: str
    place: str
    date: str
    intro: str
    detective: DetectiveOut
    people: tuple[PersonOut, ...]
    accusation: AccusationOptionsOut
    ai: str
    """Who plays the suspects on this server: ``mock``, ``ollama`` or ``claude``."""
    max_question_chars: int
    """The longest question the server accepts, so the UI can count down to it."""


# ------------------------------------------------------------------ one game


class TimeOut(_Out):
    start: str
    """``HH:MM``"""
    end: str | None
    approx: bool


class NotebookEntryOut(_Out):
    fact: FactId
    statement: str
    source: str
    """An evidence ID or a suspect ID: where the player learned it."""
    source_name: str
    time: TimeOut | None
    subjects: tuple[CharacterId, ...]
    """Who the fact is about, so the notebook can group it by person."""


class LocationOut(_Out):
    id: LocationId
    name: str
    description: str
    accessible: bool
    searched: bool


class EvidenceOut(_Out):
    id: EvidenceId
    name: str
    location: LocationId
    summary: str
    text: str | None
    """Verbatim contents of a document, if it is one."""
    reads: tuple[str, ...]
    """What closer reads have revealed so far, in the order the case lists them."""


class SuspectOut(_Out):
    id: CharacterId
    name: str
    interviewed: bool


class StatementOut(_Out):
    """A lie the suspect has put on record. ``caught`` once evidence disproves it."""

    lie: LieId
    suspect: CharacterId
    claim: str
    caught: bool
    flagged: bool
    """Easy only (``contradictions: auto_flag``): evidence the player holds already
    disproves this standing claim. Always false on other difficulties (D48)."""


class ExchangeOut(_Out):
    detective: str
    """Empty for the opening statement."""
    suspect: str
    demeanor: str


class PointsOut(_Out):
    culprit: int
    motive: int
    method: int
    evidence: int


class ResultOut(_Out):
    culprit: int
    motive: int
    method: int
    evidence: int
    total: int
    out_of: PointsOut
    """The most each part can score, from the case's scoring rules."""
    groups_covered: tuple[str, ...]
    epilogue: str


class TokensOut(_Out):
    used: int
    budget: int | None


class GameOut(_Out):
    """The whole of one game as the player sees it, after every action (D44)."""

    id: str
    difficulty: Difficulty
    help: DifficultyProfile
    """What the chosen difficulty turns on in the UI (D11). The truth never changes."""
    over: bool
    current_suspect: CharacterId | None
    suspects: tuple[SuspectOut, ...]
    locations: tuple[LocationOut, ...]
    evidence: tuple[EvidenceOut, ...]
    notebook: tuple[NotebookEntryOut, ...]
    statements: tuple[StatementOut, ...]
    interviews: dict[CharacterId, tuple[ExchangeOut, ...]]
    tokens: TokensOut
    result: ResultOut | None
    """Set once the player accuses, with the epilogue."""


# ------------------------------------------------------------------ what an action did


class FactLearnedOut(_Out):
    type: Literal["fact_learned"] = "fact_learned"
    fact: FactId
    statement: str
    source: str


class EvidenceFoundOut(_Out):
    type: Literal["evidence_found"] = "evidence_found"
    evidence: EvidenceId
    name: str


class LocationSearchedOut(_Out):
    type: Literal["location_searched"] = "location_searched"
    location: LocationId
    name: str


class LieOnRecordOut(_Out):
    type: Literal["lie_on_record"] = "lie_on_record"
    suspect: CharacterId
    lie: LieId
    claim: str


class LieCaughtOut(_Out):
    type: Literal["lie_caught"] = "lie_caught"
    suspect: CharacterId
    lie: LieId
    claim: str
    evidence: EvidenceId


class AccusationScoredOut(_Out):
    type: Literal["accusation_scored"] = "accusation_scored"
    total: int


EventOut = Annotated[
    FactLearnedOut
    | EvidenceFoundOut
    | LocationSearchedOut
    | LieOnRecordOut
    | LieCaughtOut
    | AccusationScoredOut,
    Field(discriminator="type"),
]


class LineOut(_Out):
    """What the suspect said. Already checked by the guard and grounding (D45)."""

    suspect: CharacterId
    dialogue: str
    demeanor: str


class ActionOut(_Out):
    line: LineOut | None
    """Set for ``talk`` (first meeting) and ``ask``."""
    events: tuple[EventOut, ...]
    game: GameOut


class ErrorOut(_Out):
    detail: str
