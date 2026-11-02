"""Suspect portraits, read from the case folder (D55).

    cases/<case>/portraits/<CHARACTER_ID>/<expression>.webp   (or .png, .jpg)

Any of them may be missing: the cover tells the browser which exist, and it falls back
to the neutral face, then to a plain placeholder. Only files found by this scan are
ever served, so a request can't reach anything else on disk.
"""

from collections.abc import Iterable
from pathlib import Path
from typing import get_args

from casefile.case.ids import CharacterId
from casefile.expressions import Expression

Portraits = dict[CharacterId, dict[Expression, Path]]

SUFFIXES = (".webp", ".png", ".jpg", ".jpeg")


def find_portraits(folder: Path, characters: Iterable[CharacterId]) -> Portraits:
    found: Portraits = {}
    for character in characters:
        for expression in get_args(Expression):
            for suffix in SUFFIXES:
                path = folder / character / f"{expression}{suffix}"
                if path.is_file():
                    found.setdefault(character, {})[expression] = path
                    break
    return found
