"""One player's game: the engine, an NPC provider and the conversation, wired together.

The engine decides; the provider performs. A question to a suspect goes:

    player text -> length cap -> briefing (engine) -> provider -> leak guard (culprit)
                -> grounding (reveals must match the line shown, D41) -> reveal check
                (engine) -> dialogue shown, accepted facts learned

Everything that changes the truth is in ``log``, so ``engine.replay(log)`` rebuilds
the state. The transcript is kept for display and for the model's context, but it is
never trusted as a source of facts (D14).
"""

from dataclasses import dataclass, field

from casefile.ai.contract import Exchange, Usage
from casefile.ai.grounding import ground, speaker_words
from casefile.ai.guard import find_confession, find_leaks
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
from casefile.engine.briefing import SuspectBriefing, build_briefing
from casefile.engine.engine import Engine, IllegalActionError, Outcome, RejectedReveal
from casefile.engine.events import Event, LieCaught
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
    """Leak markers or confessions in the culprit's dialogue (the line was replaced)."""
    unsupported: tuple[str, ...]
    """Facts the provider declared but the dialogue didn't say (dropped, D41)."""
    inferred: tuple[FactId, ...]
    """Facts the dialogue clearly said but the provider didn't declare (counted, D41)."""
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
    detective: str | None = None
    """The detective identity the player chose (D51). ``None``: the case default."""
    tokens_used: int = field(default=0, init=False)
    state: GameState = field(init=False)
    log: list[LogEntry] = field(default_factory=list, init=False)
    transcripts: dict[CharacterId, list[Exchange]] = field(default_factory=dict, init=False)
    current_suspect: CharacterId | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        try:
            self.engine.index.bundle.case.detective.identity(self.detective)
        except KeyError:
            raise IllegalActionError(f"there is no detective identity {self.detective!r}") from None
        self.state = self.engine.new_game()

    # ------------------------------------------------------------ player actions

    def talk_to(self, suspect: CharacterId) -> Reply:
        """Start or resume an interview. The first meeting returns the opening statement."""
        first_meeting = suspect not in self.state.talked_to
        outcome = self._apply(TalkTo(suspect=suspect))
        self.current_suspect = suspect
        briefing = build_briefing(self.engine, self.state, suspect, self.detective)
        if not first_meeting:
            return Reply("", briefing.demeanor, (), (), (), (), (), outcome.events, Usage())
        # The opening statement is authored, not generated: it must put the suspect's
        # first lie on record word for word (D08), and it costs no model call.
        opening = self.engine.index.briefings[suspect].opening_statement.text
        self.transcripts.setdefault(suspect, []).append(
            Exchange(detective="", suspect=opening, demeanor=briefing.demeanor)
        )
        return Reply(opening, briefing.demeanor, (), (), (), (), (), outcome.events, Usage())

    def ask(self, text: str) -> Reply:
        if self.state.is_over:
            raise IllegalActionError("the accusation is final; the game is over")
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

    def show(self, evidence: EvidenceId) -> Reply:
        """Put evidence in front of the suspect. A catch gets the lie's authored reaction,
        word for word and with no model call (D52); otherwise they say nothing new."""
        suspect = self.current_suspect
        if suspect is None:
            raise IllegalActionError("talk to a suspect first")
        outcome = self._apply(ShowEvidence(suspect=suspect, evidence=evidence))
        ix = self.engine.index
        reaction = " ".join(
            ix.lies[e.lie].lie.on_caught.reaction
            for e in outcome.events
            if isinstance(e, LieCaught)
        )
        demeanor = build_briefing(self.engine, self.state, suspect, self.detective).demeanor
        if reaction:
            shown = ix.evidence[evidence].name
            self.transcripts.setdefault(suspect, []).append(
                Exchange(detective="", suspect=reaction, demeanor=demeanor, shown=shown)
            )
        return Reply(reaction, demeanor, (), (), (), (), (), outcome.events, Usage())

    def accuse(self, accusation: Accusation) -> Outcome:
        return self._apply(Accuse(accusation=accusation))

    # ------------------------------------------------------------ internals

    def _apply(self, action: Action) -> Outcome:
        outcome = self.engine.apply(self.state, action)
        self.state = outcome.state
        self.log.append(action)
        return outcome

    def _ask(self, suspect: CharacterId, text: str) -> Reply:
        briefing = build_briefing(self.engine, self.state, suspect, self.detective)
        history = self.transcripts.setdefault(suspect, [])
        turn = self.provider.respond(briefing, tuple(history), text)  # may raise ProviderError
        self.tokens_used += turn.usage.total_tokens
        npc = turn.reply

        # Guard first: everything after works on the line the player will actually see.
        leaks: tuple[str, ...] = ()
        dialogue = npc.dialogue
        if suspect == self.engine.index.bundle.solution.culprit:
            leaks = find_leaks(
                dialogue, self.engine.index.guarded.values(), self.state.known_facts
            ) + find_confession(dialogue, briefing.name)
            if leaks:
                dialogue = LEAK_FALLBACK

        grounding = ground(npc.reveals, dialogue, briefing.may_reveal, self._names(briefing))
        disclosure = self.engine.disclose(self.state, suspect, grounding.proposals)
        self.state = disclosure.state
        self.log.append(NpcReveal(suspect=suspect, reveals=grounding.proposals))

        history.append(Exchange(detective=text, suspect=dialogue, demeanor=npc.demeanor))
        return Reply(
            dialogue=dialogue,
            demeanor=npc.demeanor,
            accepted=disclosure.accepted,
            rejected=disclosure.rejected,
            leaks=leaks,
            unsupported=grounding.unsupported,
            inferred=grounding.inferred,
            events=disclosure.events,
            usage=turn.usage,
        )

    def _names(self, briefing: SuspectBriefing) -> frozenset[str]:
        """Names that don't count as overlap: the speaker says "I", and everyone says
        "him" for the victim."""
        victims = (c.name for c in self.engine.index.characters.values() if c.role == "victim")
        return speaker_words(briefing.name).union(*(speaker_words(v) for v in victims))
