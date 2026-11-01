"""Detectors run on every suspect line. Plain text heuristics: cheap, deterministic,
and free to run, so they work with any provider. Each one errs on the side of flagging;
the transcript in the report lets a person check every flag."""

import re
from collections.abc import Iterable

_TIME = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_NEGATION = re.compile(
    r"\b(not|never|no|nothing|nowhere|didn't|wasn't|haven't|don't|won't)\b|n't\b"
)


def _clock(hour: str, minute: str) -> tuple[int, int]:
    """12-hour normalised, so "10:20" and "22:20" are the same time of evening."""
    return int(hour) % 12, int(minute)


def times_in(text: str) -> set[tuple[int, int]]:
    return {_clock(h, m) for h, m in _TIME.findall(text)}


def invented_times(dialogue: str, allowed_text: str) -> tuple[str, ...]:
    """Clock times the suspect said that appear nowhere in what they were given.

    ``allowed_text`` is everything the model saw this turn: its prompt and the question.
    """
    allowed = times_in(allowed_text)
    return tuple(f"{h}:{m}" for h, m in _TIME.findall(dialogue) if _clock(h, m) not in allowed)


def lie_breaks(dialogue: str, patterns: Iterable[str]) -> tuple[str, ...]:
    """Sentences that admit what a standing lie hides. Denials and questions ("The
    office?") are skipped: naming the place isn't admitting to it."""
    hits: list[str] = []
    for sentence in _SENTENCE.split(dialogue):
        if sentence.rstrip().endswith("?") or _NEGATION.search(sentence.casefold()):
            continue
        if any(re.search(p, sentence, re.IGNORECASE) for p in patterns):
            hits.append(sentence)
    return tuple(hits)


def forbidden(dialogue: str, patterns: Iterable[str]) -> tuple[str, ...]:
    return tuple(p for p in patterns if re.search(p, dialogue, re.IGNORECASE))


def parroted(dialogue: str, sample_lines: Iterable[str]) -> tuple[str, ...]:
    """Sample lines repeated word for word: they are examples of voice, not a script."""
    text = dialogue.casefold()
    return tuple(line for line in sample_lines if line.casefold().rstrip(".!?") in text)
