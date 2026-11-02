"""The six faces a suspect's portrait can show (D55).

A suspect's demeanour is one free lowercase word: authored ones ("cold", "ashamed") and
whatever the model picks each turn ("nervous", "irritated"). Portraits can't cover an
open set, so each word maps to one of six expressions, and an unknown word shows the
neutral face. The mapping lives here, not in the model's reply schema: asking a small
model for one more field costs reply quality, and a lookup can't go wrong.
"""

from typing import Literal

Expression = Literal["neutral", "guarded", "angry", "afraid", "sad", "shaken"]
EXPRESSIONS: tuple[Expression, ...] = ("neutral", "guarded", "angry", "afraid", "sad", "shaken")

_WORDS: dict[Expression, frozenset[str]] = {
    "neutral": frozenset(
        [
            "formal",
            "calm",
            "helpful",
            "polite",
            "composed",
            "neutral",
            "cooperative",
            "quiet",
            "friendly",
            "warm",
            "tired",
            "thoughtful",
            "patient",
            "matter_of_fact",
        ]
    ),
    "guarded": frozenset(
        [
            "cold",
            "guarded",
            "defensive",
            "evasive",
            "wary",
            "suspicious",
            "careful",
            "curt",
            "stiff",
            "dismissive",
            "aloof",
            "reserved",
            "cautious",
            "icy",
            "distant",
            "smug",
        ]
    ),
    "angry": frozenset(
        [
            "hostile",
            "angry",
            "irritated",
            "annoyed",
            "bitter",
            "indignant",
            "furious",
            "impatient",
            "aggressive",
            "sharp",
            "contemptuous",
            "outraged",
            "frustrated",
        ]
    ),
    "afraid": frozenset(
        [
            "nervous",
            "anxious",
            "afraid",
            "scared",
            "frightened",
            "uneasy",
            "worried",
            "panicked",
            "tense",
            "agitated",
            "fearful",
            "jumpy",
        ]
    ),
    "sad": frozenset(
        [
            "sad",
            "ashamed",
            "broken",
            "deflated",
            "tearful",
            "grieving",
            "defeated",
            "weary",
            "resigned",
            "guilty",
            "remorseful",
            "sorrowful",
            "upset",
        ]
    ),
    "shaken": frozenset(
        ["shaken", "shocked", "rattled", "stunned", "flustered", "startled", "caught"]
    ),
}

KNOWN_DEMEANORS: frozenset[str] = frozenset().union(*_WORDS.values())
"""Every word with a face of its own; the test suite holds authored demeanours to it."""


def expression_for(demeanor: str) -> Expression:
    word = demeanor.strip().lower()
    for expression, words in _WORDS.items():
        if word in words:
            return expression
    return "neutral"
