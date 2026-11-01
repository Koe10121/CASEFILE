"""One player's game: the engine, an NPC provider and the conversation, wired together.

The engine decides; the provider performs. A question to a suspect goes:

    player text -> length cap -> briefing (engine) -> provider -> reveal check (engine)
                -> leak guard (culprit only) -> dialogue shown, accepted facts learned

Everything that changes the truth is in ``log``, so ``engine.replay(log)`` rebuilds
the state. The transcript is kept for display and for the model's context, but it is
never trusted as a source of facts (D14).
"""

from dataclasses import dataclass, field

from casefile.ai.contract import Exchange, Usage
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
    usage: Usage


class BudgetExhaustedError(IllegalActionError):
    """The session has spent its model tokens. Injection defence layer 6, and a cost cap."""


@dataclass
class GameSession:
    engine: Engine
    provider: NpcProvider
    token_budget: int | None = None
    """Model tokens (input + output) this session may spend. ``None``: no cap (mock mode)."""
    tokens_used: int = field(default=0, init=False)
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
        briefing = build_briefing(self.engine, self.state, suspect)
        if not first_meeting:
            return Reply("", briefing.demeanor, (), (), (), outcome.events, Usage())
        # The opening statement is authored, not generated: it must put the suspect's
        # first lie on record word for word (D08), and it costs no model call.
        opening = self.engine.index.briefings[suspect].opening_statement.text
        self.transcripts.setdefault(suspect, []).append(
            Exchange(detective="", suspect=opening, demeanor=briefing.demeanor)
        )
        return Reply(opening, briefing.demeanor, (), (), (), outcome.events, Usage())

    def ask(self, text: str) -> Reply:
        if self.current_suspect is None:
            raise IllegalActionError("talk to a suspect first")
        if not text.strip():
            raise IllegalActionError("say something")
        if len(text) > MAX_PLAYER_CHARS:
            raise IllegalActionError(f"keep it under {MAX_PLAYER_CHARS} characters")
        if self.token_budget is not None and self.tokens_used >= self.token_budget:
            raise BudgetExhaustedError("this session has used its model token budget")
        return self._ask(self.current_suspect, text)

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

    def _ask(self, suspect: CharacterId, text: str) -> Reply:
        briefing = build_briefing(self.engine, self.state, suspect)
        history = self.transcripts.setdefault(suspect, [])
        turn = self.provider.respond(briefing, tuple(history), text)  # may raise ProviderError
        self.tokens_used += turn.usage.total_tokens
        npc = turn.reply

        disclosure = self.engine.disclose(self.state, suspect, npc.reveals)
        self.state = disclosure.state
        self.log.append(NpcReveal(suspect=suspect, reveals=npc.reveals))

        leaks: tuple[str, ...] = ()
        dialogue = npc.dialogue
        if suspect == self.engine.index.bundle.solution.culprit:
            leaks = find_leaks(dialogue, self.engine.index.guarded.values(), self.state.known_facts)
            if leaks:
                dialogue = LEAK_FALLBACK

        history.append(Exchange(detective=text, suspect=dialogue, demeanor=npc.demeanor))
        return Reply(
            dialogue=dialogue,
            demeanor=npc.demeanor,
            accepted=disclosure.accepted,
            rejected=disclosure.rejected,
            leaks=leaks,
            events=disclosure.events,
            usage=turn.usage,
        )
