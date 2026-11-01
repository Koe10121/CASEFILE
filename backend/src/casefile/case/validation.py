"""The case validator: every rule that needs more than one file (D20).

``validate_case`` runs every rule and returns all problems at once, so an author can fix
a broken case in one pass. ``load_valid_case`` is what the engine calls at startup: a
case with any error never reaches play.

Each rule is a generator of ``Issue``. The rule table in ``docs/design/case-schema.md``
says why each one exists.
"""

from collections.abc import Callable, Iterable, Iterator, Set
from dataclasses import dataclass
from datetime import time
from enum import StrEnum
from pathlib import Path
from typing import Literal

from casefile.case.base import TimeSpan
from casefile.case.conditions import Condition, condition_refs
from casefile.case.ids import CharacterId, FactId, GuardedFactId
from casefile.case.index import CaseIndex
from casefile.case.loader import CaseBundle, CaseLoadError, load_case
from casefile.case.reachability import Reachability, explore
from casefile.case.rules import can_catch_lies
from casefile.case.world import FactKind

MAX_WHEREABOUTS_GAP_MINUTES = 15
"""D12: every suspect accounts for the crime window with no gap longer than this."""

_WHEREABOUTS_KINDS: frozenset[FactKind] = frozenset({"presence", "action", "knowledge"})


class Rule(StrEnum):
    REFERENCES = "references"
    CAST = "cast"
    ANSWER_KEY = "answer_key"
    GUARD_ISOLATION = "guard_isolation"
    CATCHABLE_LIES = "catchable_lies"
    ON_RECORD = "on_record"
    SOLVABILITY = "solvability"
    DEAD_WEIGHT = "dead_weight"
    PHYSICAL = "physical"
    TIME_WINDOW = "time_window"
    COVERAGE = "coverage"
    BOUNDARY_LEAK = "boundary_leak"


Severity = Literal["error", "warning"]


@dataclass(frozen=True, slots=True)
class Issue:
    rule: Rule
    message: str
    severity: Severity = "error"

    def __str__(self) -> str:
        return f"[{self.severity}] {self.rule}: {self.message}"


@dataclass(frozen=True, slots=True)
class ValidationReport:
    issues: tuple[Issue, ...]
    reachability: Reachability

    @property
    def errors(self) -> tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.severity == "error")

    @property
    def warnings(self) -> tuple[Issue, ...]:
        return tuple(i for i in self.issues if i.severity == "warning")

    @property
    def ok(self) -> bool:
        return not self.errors


class CaseInvalidError(CaseLoadError):
    """The case parsed, but breaks validator rules."""

    def __init__(self, folder: Path, report: ValidationReport) -> None:
        self.report = report
        lines = "\n".join(f"  {issue}" for issue in report.errors)
        super().__init__(f"{folder} has {len(report.errors)} validation error(s):\n{lines}")


def validate_case(bundle: CaseBundle) -> ValidationReport:
    ix = CaseIndex.build(bundle)
    reach = explore(ix)
    checks: list[Callable[[], Iterator[Issue]]] = [
        lambda: _references(ix),
        lambda: _cast(ix),
        lambda: _answer_key(ix),
        lambda: _guard_isolation(ix),
        lambda: _catchable_lies(ix),
        lambda: _on_record(ix),
        lambda: _solvability(ix, reach),
        lambda: _dead_weight(ix, reach),
        lambda: _physical(ix),
        lambda: _time_window(ix),
        lambda: _coverage(ix),
        lambda: _boundary_leak(ix),
    ]
    return ValidationReport(
        issues=tuple(i for check in checks for i in check()), reachability=reach
    )


def load_valid_case(folder: Path) -> CaseBundle:
    """Load a case and refuse it if any validator rule fails. Warnings are allowed."""
    bundle = load_case(folder)
    report = validate_case(bundle)
    if not report.ok:
        raise CaseInvalidError(folder, report)
    return bundle


# ---------------------------------------------------------------- references

_ATOM_KIND = {
    "location_searched": "location",
    "evidence_found": "evidence",
    "evidence_shown": "evidence",
    "fact_known": "fact",
    "lie_caught": "lie",
    "talked_to": "character",
}


def _references(ix: CaseIndex) -> Iterator[Issue]:
    """Every ID resolves to something that exists."""
    case, solution = ix.bundle.case, ix.bundle.solution
    ids: dict[str, Set[str]] = {
        "character": ix.characters.keys(),
        "location": ix.locations.keys(),
        "fact": ix.facts.keys(),
        "evidence": ix.evidence.keys(),
        "lie": ix.lies.keys(),
        "guarded fact": ix.guarded.keys(),
    }

    def check(kind: str, refs: Iterable[str], where: str) -> Iterator[Issue]:
        for ref in refs:
            if ref not in ids[kind]:
                yield Issue(Rule.REFERENCES, f"{where}: unknown {kind} {ref}")

    def check_condition(cond: Condition | None, where: str) -> Iterator[Issue]:
        if cond is not None:
            for atom, ref in condition_refs(cond):
                yield from check(_ATOM_KIND[atom], [ref], f"{where} ({atom})")

    yield from check("character", case.world.present, "world.present")
    yield from check("character", case.accusation_options.culprits, "accusation culprits")
    for loc in case.locations:
        yield from check_condition(loc.accessible_when, f"{loc.id}.accessible_when")
    for fact in case.facts:
        yield from check("character", fact.subjects, f"{fact.id}.subjects")
        yield from check("location", _opt(fact.location), f"{fact.id}.location")
    for ev in case.evidence:
        yield from check("location", [ev.location], f"{ev.id}.location")
        yield from check_condition(ev.discover_when, f"{ev.id}.discover_when")
        yield from check("fact", ev.establishes, f"{ev.id}.establishes")
        for read in ev.deeper_reads:
            yield from check_condition(read.when, f"{ev.id}.deeper_reads.when")
            yield from check("fact", read.establishes, f"{ev.id}.deeper_reads.establishes")

    for b in ix.bundle.briefings.suspects:
        s = b.suspect
        yield from check("character", [s], "briefing")
        yield from check("lie", b.opening_statement.claims, f"{s}.opening_statement")
        yield from check("fact", b.shares_freely, f"{s}.shares_freely")
        for gated in b.gated:
            yield from check("fact", [gated.fact], f"{s}.gated")
            yield from check_condition(gated.reveal_when, f"{s}.gated[{gated.fact}].reveal_when")
        for lie in b.lies:
            kind = "guarded fact" if lie.hides.startswith("G_") else "fact"
            yield from check(kind, [lie.hides], f"{lie.id}.hides")
            yield from check("fact", lie.contradicted_by, f"{lie.id}.contradicted_by")
            yield from check("lie", _opt(lie.on_caught.fallback_lie), f"{lie.id}.fallback_lie")
            yield from check("fact", lie.on_caught.reveal, f"{lie.id}.on_caught.reveal")
        yield from check_condition(b.breaking_point.when, f"{s}.breaking_point.when")
        yield from check("fact", b.breaking_point.reveal, f"{s}.breaking_point.reveal")

    yield from check("character", [solution.culprit], "solution.culprit")
    for g in solution.guarded_facts:
        yield from check("location", _opt(g.location), f"{g.id}.location")
        yield from check("character", g.subjects, f"{g.id}.subjects")
        yield from check(
            "fact",
            (m.unless_known for m in g.leak_markers if m.unless_known),
            f"{g.id}.unless_known",
        )
    for group in solution.key_evidence_groups:
        yield from check("evidence", group.items, f"key group '{group.label}'")
    for step in solution.solution_chain:
        yield from check("fact", step.learn, f"solution step {step.step}")
        yield from check("lie", _opt(step.breaks), f"solution step {step.step}")


def _opt[T](value: T | None) -> list[T]:
    return [] if value is None else [value]


# ---------------------------------------------------------------- cast and answer key


def _cast(ix: CaseIndex) -> Iterator[Issue]:
    """Suspects, briefings and the accusation form all name the same people."""
    suspects = {c.id for c in ix.characters.values() if c.role == "suspect"}
    briefed = set(ix.briefings)
    culprits = set(ix.bundle.case.accusation_options.culprits)
    for s in sorted(suspects - briefed):
        yield Issue(Rule.CAST, f"suspect {s} has no briefing")
    for s in sorted(briefed - suspects):
        yield Issue(Rule.CAST, f"briefing for {s}, who is not a suspect")
    if culprits != suspects:
        yield Issue(
            Rule.CAST, f"accusation culprits {sorted(culprits)} != suspects {sorted(suspects)}"
        )
    for c in sorted(set(ix.characters) - set(ix.bundle.case.world.present)):
        yield Issue(Rule.CAST, f"character {c} is missing from world.present")


def _answer_key(ix: CaseIndex) -> Iterator[Issue]:
    """The right answer is one of the options, and full marks are possible."""
    solution, options = ix.bundle.solution, ix.bundle.case.accusation_options
    if solution.culprit not in options.culprits:
        yield Issue(Rule.ANSWER_KEY, f"culprit {solution.culprit} is not an accusation option")
    if solution.motive not in {m.id for m in options.motives}:
        yield Issue(Rule.ANSWER_KEY, f"motive {solution.motive} is not an accusation option")
    if solution.method not in {m.id for m in options.methods}:
        yield Issue(Rule.ANSWER_KEY, f"method {solution.method} is not an accusation option")
    groups = len(solution.key_evidence_groups)
    if options.max_evidence < groups:
        yield Issue(
            Rule.ANSWER_KEY,
            f"max_evidence is {options.max_evidence} but there are {groups} key evidence groups, "
            "so full evidence marks are impossible",
        )


# ---------------------------------------------------------------- lies


def _guard_isolation(ix: CaseIndex) -> Iterator[Issue]:
    """Only the culprit's lies may hide a guarded fact (D06).

    Typed IDs already make a ``G_`` ID impossible anywhere else outside ``solution.json``:
    every other field that holds a fact ID only accepts the ``F_`` pattern.
    """
    culprit = ix.bundle.solution.culprit
    for lie_id, owned in ix.lies.items():
        if owned.lie.hides in ix.guarded and owned.suspect != culprit:
            yield Issue(
                Rule.GUARD_ISOLATION,
                f"{lie_id} belongs to {owned.suspect}, not the culprit, "
                f"but hides {owned.lie.hides}",
            )


def _catchable_lies(ix: CaseIndex) -> Iterator[Issue]:
    """Some evidence proves a fact that contradicts the lie, with an exact time (D04)."""
    provable: set[FactId] = set()
    for ev in ix.evidence.values():
        provable.update(ev.establishes)
        for read in ev.deeper_reads:
            provable.update(read.establishes)
    for lie_id, owned in ix.lies.items():
        usable = [
            f
            for f in owned.lie.contradicted_by
            if f in provable and f in ix.facts and can_catch_lies(ix.facts[f])
        ]
        if not usable:
            yield Issue(
                Rule.CATCHABLE_LIES,
                f"{lie_id}: no contradicting fact is both proved by evidence and exactly timed",
            )


def _on_record(ix: CaseIndex) -> Iterator[Issue]:
    """Every lie is said at some point: in an opening statement or on a fallback ladder (D08)."""
    for lie_id, owned in ix.lies.items():
        fallback = owned.lie.on_caught.fallback_lie
        if (
            fallback is not None
            and fallback in ix.lies
            and ix.lies[fallback].suspect != owned.suspect
        ):
            yield Issue(Rule.ON_RECORD, f"{lie_id} falls back to another suspect's lie {fallback}")

    for suspect, briefing in ix.briefings.items():
        told: set[str] = set()
        for start in briefing.opening_statement.claims:
            current = ix.lies.get(start)
            if current is not None and current.suspect != suspect:
                yield Issue(Rule.ON_RECORD, f"{suspect} opens with another suspect's lie {start}")
            ladder: list[str] = []
            while current is not None and current.lie.id not in ladder:
                ladder.append(current.lie.id)
                fb = current.lie.on_caught.fallback_lie
                current = ix.lies.get(fb) if fb else None
            if current is not None:
                yield Issue(
                    Rule.ON_RECORD, f"lie ladder loops: {' -> '.join(ladder)} -> {ladder[0]}"
                )
            told.update(ladder)
        for lie in briefing.lies:
            if lie.id not in told:
                yield Issue(
                    Rule.ON_RECORD,
                    f"{lie.id} is never said: it is not in {suspect}'s opening statement "
                    "or on a fallback ladder from it",
                )


# ---------------------------------------------------------------- reachability


def _solvability(ix: CaseIndex, reach: Reachability) -> Iterator[Issue]:
    """Everything the solution needs can be reached through play."""
    final = reach.final
    for lie_id in ix.lies:
        if lie_id not in final.caught_lies:
            yield Issue(Rule.SOLVABILITY, f"lie {lie_id} can never be caught")
    for step in ix.bundle.solution.solution_chain:
        for fact in step.learn:
            if fact not in final.known_facts:
                yield Issue(Rule.SOLVABILITY, f"step {step.step}: fact {fact} is unreachable")
        if step.breaks is not None and step.breaks not in final.caught_lies:
            yield Issue(Rule.SOLVABILITY, f"step {step.step}: lie {step.breaks} can't be caught")
    for group in ix.bundle.solution.key_evidence_groups:
        if not any(item in final.found_evidence for item in group.items):
            yield Issue(Rule.SOLVABILITY, f"no item of key group '{group.label}' can be found")


def _dead_weight(ix: CaseIndex, reach: Reachability) -> Iterator[Issue]:
    """Authored content the player can never see. A warning: it can't break play."""
    for ev in ix.evidence:
        if ev not in reach.final.found_evidence:
            yield Issue(Rule.DEAD_WEIGHT, f"evidence {ev} can never be found", "warning")
    for fact in ix.facts:
        if fact not in reach.final.known_facts:
            yield Issue(Rule.DEAD_WEIGHT, f"fact {fact} can never be learned", "warning")


# ---------------------------------------------------------------- timeline


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _interval(span: TimeSpan) -> tuple[int, int]:
    start = _minutes(span.start)
    return start, _minutes(span.end) if span.end is not None else start


@dataclass(frozen=True, slots=True)
class _Placed:
    """A timed, located statement about who was where: a fact or a guarded fact."""

    id: str
    subjects: tuple[CharacterId, ...]
    location: str
    start: int
    end: int


def _placements(ix: CaseIndex) -> list[_Placed]:
    return [
        _Placed(item.id, item.subjects, item.location, *_interval(item.time))
        for item in ix.statements.values()
        if item.kind == "presence" and item.time and item.location
    ]


def _overlap(a: _Placed, b: _Placed) -> bool:
    """Open-interval overlap; an instant counts if it falls strictly inside the other span.

    Spans that only touch (one ends at 21:44, the next starts at 21:44) are a move, not a
    contradiction.
    """
    if a.start == a.end:
        return b.start < a.start < b.end
    if b.start == b.end:
        return a.start < b.start < a.end
    return a.start < b.end and b.start < a.end


def _physical(ix: CaseIndex) -> Iterator[Issue]:
    """Nobody is in two places at once."""
    placed = _placements(ix)
    for i, a in enumerate(placed):
        for b in placed[i + 1 :]:
            if a.location == b.location:
                continue
            for who in sorted(set(a.subjects) & set(b.subjects)):
                if _overlap(a, b):
                    yield Issue(
                        Rule.PHYSICAL,
                        f"{who} is in {a.location} ({a.id}) and {b.location} ({b.id}) at once",
                    )


def _time_window(ix: CaseIndex) -> Iterator[Issue]:
    """Every timed fact falls inside the crime window."""
    window = ix.bundle.case.setting.crime_window
    lo, hi = _minutes(window.start), _minutes(window.end)
    for item_id, item in ix.statements.items():
        if item.time is not None:
            start, end = _interval(item.time)
            if start < lo or end > hi:
                yield Issue(
                    Rule.TIME_WINDOW,
                    f"{item_id} falls outside {window.start:%H:%M}-{window.end:%H:%M}",
                )


def _briefing_knowledge(ix: CaseIndex, suspect: CharacterId) -> set[FactId | GuardedFactId]:
    """Everything a suspect's briefing could ever put in front of the model."""
    b = ix.briefings[suspect]
    known: set[FactId | GuardedFactId] = {*b.shares_freely, *(g.fact for g in b.gated)}
    known.update(b.breaking_point.reveal)
    for lie in b.lies:
        known.add(lie.hides)
        known.update(lie.on_caught.reveal)
    if suspect == ix.bundle.solution.culprit:
        known.update(ix.guarded)
    return known


def _coverage(ix: CaseIndex) -> Iterator[Issue]:
    """Each briefing accounts for the whole crime window (D12)."""
    window = ix.bundle.case.setting.crime_window
    lo, hi = _minutes(window.start), _minutes(window.end)
    for suspect in ix.briefings:
        spans: list[tuple[int, int]] = []
        for ref in _briefing_knowledge(ix, suspect):
            item = ix.statements.get(ref)
            if item is None or item.time is None or item.location is None:
                continue
            kind = item.kind or "presence"
            if suspect in item.subjects and kind in _WHEREABOUTS_KINDS:
                spans.append(_interval(item.time))
        cursor, worst, worst_at = lo, 0, lo
        for start, end in sorted(spans):
            if start - cursor > worst:
                worst, worst_at = start - cursor, cursor
            cursor = max(cursor, end)
        if hi - cursor > worst:
            worst, worst_at = hi - cursor, cursor
        if worst > MAX_WHEREABOUTS_GAP_MINUTES:
            yield Issue(
                Rule.COVERAGE,
                f"{suspect}'s briefing has a {worst}-minute gap from "
                f"{worst_at // 60:02d}:{worst_at % 60:02d} (limit {MAX_WHEREABOUTS_GAP_MINUTES})",
            )


def _boundary_leak(ix: CaseIndex) -> Iterator[Issue]:
    """A freely shared whereabouts fact must not start or end inside a lied-about interval (D13)."""
    for suspect, b in ix.briefings.items():
        for lie in b.lies:
            hidden = ix.statements.get(lie.hides)
            if hidden is None or hidden.time is None:
                continue
            h_start, h_end = _interval(hidden.time)
            for fact_id in b.shares_freely:
                fact = ix.facts.get(fact_id)
                if (
                    not fact
                    or fact.kind != "presence"
                    or not fact.time
                    or suspect not in fact.subjects
                ):
                    continue
                start, end = _interval(fact.time)
                touches = h_start - 1 <= start <= h_end + 1 or h_start - 1 <= end <= h_end + 1
                encloses = start <= h_start and end >= h_end and fact.location == hidden.location
                if touches and not encloses:
                    yield Issue(
                        Rule.BOUNDARY_LEAK,
                        f"{suspect} freely shares {fact_id}, whose edge touches the interval "
                        f"{lie.id} hides; gate it until the lie is caught",
                    )
