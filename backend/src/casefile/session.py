"""One player's game: the engine, an NPC provider and the conversation, wired together.

The engine decides; the provider performs. A question to a suspect goes:

    player text -> length cap -> briefing (engine) -> provider -> reveal check (engine)
                -> leak guard (culprit only) -> dialogue shown, accepted facts learned

Everything that changes the truth is in ``log``, so ``engine.replay(log)`` rebuilds
the state. The transcript is kept for display and for the model's context, but it is
never trusted as a source of facts (D14).
"""

from dataclasses import dataclass, field, replace

from casefile.ai.contract import Exchange
from casefile.ai.guard import find_leaks
from casefile.ai.provider import NpcProvider
from casefile.case.ids import CharacterId, EvidenceId, FactId, LocationId
from casefile.engine.actions import (
    Accuse,
    Action,
    LogEntry,
    NpcReveal,
    SearchLocation,
    ShowEvidence,
    TalkTo,
)
from casefile.engine.briefing import build_briefing
from casefile.engine.engine import Engine, IllegalActionError, Outcome, RejectedReveal
from casefile.engine.events import Event
from casefile.engine.scoring import Accusation
from casefile.engine.state import GameState

MAX_PLAYER_CHARS = 500
"""Injection defence layer 6: long inputs are where elaborate jailbreaks live."""

LEAK_FALLBACK = "I've told you what I know, Inspector."
"""Said instead of a reply that tripped a leak marker. Deliberately bland."""


@dataclass(frozen=True, slots=True)
class Reply:
    """The result of one question, for the UI and for the eval harness."""

    dialogue: str
    demeanor: str
    accepted: tuple[FactId, ...]
    rejected: tuple[RejectedReveal, ...]
    leaks: tuple[str, ...]
    """Leak-marker phrases the provider's dialogue contained (it was replaced)."""
    events: tuple[Event, ...]


@dataclass
class GameSession:
    engine: Engine
    provider: NpcProvider
    state: GameState = field(init=False)
    log: list[LogEntry] = field(default_factory=list, init=False)
    transcripts: dict[CharacterId, list[Exchange]] = field(default_factory=dict, init=False)
    current_suspect: CharacterId | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.state = self.engine.new_game()

    # ------------------------------------------------------------ player actions

    def talk_to(self, suspect: CharacterId) -> Reply:
        """Start or resume an interview. The first meeting returns the opening statement."""
        first_meeting = suspect not in self.state.talked_to
        outcome = self._apply(TalkTo(suspect=suspect))
        self.current_suspect = suspect
        if not first_meeting:
            return Reply("", self._demeanor(suspect), (), (), (), outcome.events)
        reply = self._ask(suspect, "", first_meeting=True)
        return replace(reply, events=outcome.events + reply.events)

    def ask(self, text: str) -> Reply:
        if self.current_suspect is None:
            raise IllegalActionError("talk to a suspect first")
        if not text.strip():
            raise IllegalActionError("say something")
        if len(text) > MAX_PLAYER_CHARS:
            raise IllegalActionError(f"keep it under {MAX_PLAYER_CHARS} characters")
        return self._ask(self.current_suspect, text, first_meeting=False)

    def search(self, location: LocationId) -> Outcome:
        return self._apply(SearchLocation(location=location))

    def show(self, evidence: EvidenceId) -> Outcome:
        if self.current_suspect is None:
            raise IllegalActionError("talk to a suspect first")
        return self._apply(ShowEvidence(suspect=self.current_suspect, evidence=evidence))

    def accuse(self, accusation: Accusation) -> Outcome:
        return self._apply(Accuse(accusation=accusation))

    # ------------------------------------------------------------ internals

    def _apply(self, action: Action) -> Outcome:
        outcome = self.engine.apply(self.state, action)
        self.state = outcome.state
        self.log.append(action)
        return outcome

    def _demeanor(self, suspect: CharacterId) -> str:
        return build_briefing(self.engine, self.state, suspect, first_meeting=False).demeanor

    def _ask(self, suspect: CharacterId, text: str, *, first_meeting: bool) -> Reply:
        briefing = build_briefing(self.engine, self.state, suspect, first_meeting=first_meeting)
        history = self.transcripts.setdefault(suspect, [])
        npc = self.provider.respond(briefing, tuple(history), text)

        disclosure = self.engine.disclose(self.state, suspect, npc.reveals)
        self.state = disclosure.state
        self.log.append(NpcReveal(suspect=suspect, reveals=npc.reveals))

        leaks: tuple[str, ...] = ()
        dialogue = npc.dialogue
        if suspect == self.engine.index.bundle.solution.culprit:
            leaks = find_leaks(dialogue, self.engine.index.guarded.values(), self.state.known_facts)
            if leaks:
                dialogue = LEAK_FALLBACK

        history.append(Exchange(detective=text, suspect=dialogue))
        return Reply(
            dialogue=dialogue,
            demeanor=npc.demeanor,
            accepted=disclosure.accepted,
            rejected=disclosure.rejected,
            leaks=leaks,
            events=disclosure.events,
        )
