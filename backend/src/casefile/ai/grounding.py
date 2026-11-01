"""Tie a suspect's ``reveals`` to what their dialogue actually says (D41).

A model's list of revealed fact IDs is a claim, not a record. Small local models get it
wrong both ways: they state a fact and forget to declare it (the clue never reaches the
notebook), or they declare facts they never said (one "debug mode" line dumped eleven).
So the backend reads the line it is about to show:

- a declared fact counts only if the dialogue supports it;
- an undeclared fact counts if the dialogue clearly states it;
- at most ``MAX_REVEALS_PER_TURN`` facts per line, best supported first.

Support is word overlap between the dialogue and the fact's authored statement, with
clock times weighed separately. It is deliberately simple: deterministic, free, and the
same for every provider. The engine still decides whether each fact may be revealed.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from casefile.case.ids import FactId
from casefile.engine.briefing import RevealableFact

MAX_REVEALS_PER_TURN = 3
DECLARED_SUPPORT = 0.2
"""A declared fact needs this much of its statement in the dialogue."""
INFERRED_SUPPORT = 0.45
"""An undeclared fact needs this much: it has to be clearly stated, not just touched on."""

_TIME = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")
_WORD = re.compile(r"[a-z0-9]+")
_STOPWORD_TEXT = """the and but for from with was were been being its this that these those
she they his her their him them you your our had has have did done not then than there
here all any some into over after before about out off just only also very around until
till who what when where which while said says"""
_STOPWORDS = frozenset(_STOPWORD_TEXT.split())


def _stem(word: str) -> str:
    for suffix in ("ing", "ed", "es", "s", "e"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            return word[: -len(suffix)]
    return word


def _words(text: str, ignore: frozenset[str]) -> set[str]:
    plain = _TIME.sub(" ", text.lower())
    return {
        _stem(w)
        for w in _WORD.findall(plain)
        if len(w) > 2 and w not in _STOPWORDS and w not in ignore
    }


def _clocks(text: str) -> set[tuple[int, int]]:
    return {(int(h) % 12, int(m)) for h, m in _TIME.findall(text)}


def support(statement: str, dialogue: str, ignore: frozenset[str] = frozenset()) -> float:
    """How much of ``statement`` the dialogue says, from 0 up to about 1.2.

    A matching clock time adds weight; a dialogue that gives only other times for a
    timed fact counts for half, because it is telling a different story.
    """
    wanted = _words(statement, ignore)
    if not wanted:
        return 0.0
    score = len(wanted & _words(dialogue, ignore)) / len(wanted)
    stated, said = _clocks(statement), _clocks(dialogue)
    if stated and said:
        score = score + 0.2 if stated & said else score * 0.5
    return score


@dataclass(frozen=True, slots=True)
class Grounding:
    proposals: tuple[str, ...]
    """What goes to ``Engine.disclose``: supported and inferred facts, plus any declared
    string that isn't one of this suspect's revealable facts (so the engine can reject it
    with its usual reason and the evals can count it)."""
    unsupported: tuple[str, ...]
    """Declared, revealable, but not said."""
    inferred: tuple[FactId, ...]
    """Said clearly, but not declared."""


def speaker_words(name: str) -> frozenset[str]:
    """A suspect's own name: they say "I", so their name never counts as overlap."""
    return frozenset(name.lower().split())


def ground(
    declared: Sequence[str],
    dialogue: str,
    facts: Iterable[RevealableFact],
    ignore: frozenset[str] = frozenset(),
) -> Grounding:
    candidates = {f.id: f for f in facts}
    scored: list[tuple[float, FactId]] = []
    unsupported: list[str] = []
    inferred: list[FactId] = []
    for fact_id, fact in candidates.items():
        score = support(fact.statement, dialogue, ignore)
        if fact_id in declared:
            if score >= DECLARED_SUPPORT:
                scored.append((score, fact_id))
            else:
                unsupported.append(fact_id)
        elif not fact.already_told and score >= INFERRED_SUPPORT:
            scored.append((score, fact_id))
            inferred.append(fact_id)
    scored.sort(key=lambda pair: -pair[0])
    kept = [fact_id for _, fact_id in scored[:MAX_REVEALS_PER_TURN]]
    others = [d for d in dict.fromkeys(declared) if d not in candidates]
    return Grounding(
        proposals=(*others, *kept),
        unsupported=tuple(unsupported),
        inferred=tuple(f for f in inferred if f in kept),
    )
