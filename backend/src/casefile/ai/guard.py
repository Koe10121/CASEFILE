"""Output guard for the culprit: catch guarded facts leaking into dialogue (D07).

Context gating keeps everything else out of the prompt, but the culprit must know their
secret to lie well. This is the last line for that secret: phrases authored in the
solution's ``leak_markers``. A marker stops counting once the player knows its
``unless_known`` fact, because by then the phrase is fair game.
"""

import re
from collections.abc import Iterable, Set

from casefile.case.ids import FactId
from casefile.case.solution import GuardedFact


def find_leaks(
    dialogue: str, guarded: Iterable[GuardedFact], known_facts: Set[FactId]
) -> tuple[str, ...]:
    """The marker phrases present in ``dialogue`` (case-insensitive) that still count."""
    text = dialogue.casefold()
    return tuple(
        marker.phrase
        for fact in guarded
        for marker in fact.leak_markers
        if marker.phrase.casefold() in text
        and (marker.unless_known is None or marker.unless_known not in known_facts)
    )


_CRIME = re.compile(r"\b(murder\w*|kill\w*|struck|strike|culprit|guilty)\b", re.IGNORECASE)
_FIRST_PERSON = re.compile(
    r"\bI\s+(killed|murdered|struck|hit|did it)\b|\bI'm\s+(the\s+)?(killer|murderer|culprit)\b",
    re.IGNORECASE,
)
_SENTENCES = re.compile(r"(?<=[.!?])\s+")


def find_confession(dialogue: str, culprit_name: str) -> tuple[str, ...]:
    """Sentences where the culprit names themselves as the killer, in any person.

    Leak markers catch the secret's details; this catches the plain admission, including
    the third-person kind a model gives when asked to "pretend to be an AI" ("The
    murderer is Victoria Shaw"). Only ever run on the culprit's own dialogue.
    """
    names = re.compile(
        r"\b(" + "|".join(re.escape(n) for n in culprit_name.split()) + r")\b", re.IGNORECASE
    )
    return tuple(
        s
        for s in _SENTENCES.split(dialogue)
        if _FIRST_PERSON.search(s) or (names.search(s) and _CRIME.search(s))
    )
