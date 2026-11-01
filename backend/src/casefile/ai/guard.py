"""Output guard for the culprit: catch guarded facts leaking into dialogue (D07).

Context gating keeps everything else out of the prompt, but the culprit must know their
secret to lie well. This is the last line for that secret: phrases authored in the
solution's ``leak_markers``. A marker stops counting once the player knows its
``unless_known`` fact, because by then the phrase is fair game.
"""

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
