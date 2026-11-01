"""Shared building blocks for the case models: the base model, clock times and spans."""

import re
from collections.abc import Iterable
from datetime import time
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
)


class CaseModel(BaseModel):
    """Base for every case-data model.

    ``extra="forbid"``: a misspelt key in hand-written JSON is an error, not silently
    ignored data. ``frozen=True`` (with tuples instead of lists): one loaded case is
    shared by every game session in the process, so nothing may mutate it.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        serialize_by_alias=True,
    )


NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _parse_hhmm(value: object) -> object:
    if isinstance(value, str):
        if not _HHMM.match(value):
            raise ValueError(f"expected a 24-hour 'HH:MM' time, got {value!r}")
        hours, minutes = value.split(":")
        return time(int(hours), int(minutes))
    return value


ClockTime = Annotated[
    time,
    BeforeValidator(_parse_hhmm),
    PlainSerializer(lambda t: t.strftime("%H:%M"), return_type=str, when_used="json"),
]
"""A wall-clock time on the night of the case, written ``"HH:MM"`` in the JSON.

Pydantic's own ``time`` parsing also accepts seconds, ISO forms and timezones; case
files must use exactly one spelling so they stay diff-friendly and unambiguous.
"""

Precision = Literal["exact", "approx"]
"""``exact`` times can catch a lie; ``approx`` (±10 min) times never can.

An untimed fact has no ``time`` at all, rather than a ``"none"`` precision (D17).
"""


class TimeSpan(CaseModel):
    """When a fact holds. ``to`` is ``null`` for an instant."""

    start: ClockTime = Field(alias="from")
    end: ClockTime | None = Field(alias="to")
    precision: Precision

    @model_validator(mode="after")
    def _end_not_before_start(self) -> "TimeSpan":
        if self.end is not None and self.end < self.start:
            raise ValueError(f"span ends ({self.end:%H:%M}) before it starts ({self.start:%H:%M})")
        return self


class Window(CaseModel):
    """A closed interval of clock time on one night (it may not cross midnight)."""

    start: ClockTime = Field(alias="from")
    end: ClockTime = Field(alias="to")

    @model_validator(mode="after")
    def _end_after_start(self) -> "Window":
        if self.end <= self.start:
            raise ValueError("window must end after it starts, on the same night")
        return self


def require_unique(ids: Iterable[str], what: str) -> None:
    """Raise if any ID appears twice. Used by list-holding models."""
    seen: set[str] = set()
    dupes: set[str] = set()
    for item in ids:
        (dupes if item in seen else seen).add(item)
    if dupes:
        raise ValueError(f"duplicate {what} IDs: {', '.join(sorted(dupes))}")
