"""Eval scenarios: scripted interviews with what each answer should and shouldn't do.

Scenario files are author-only (they name the truths a lie hides), like ``solution.json``.
"""

import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from casefile.case.ids import CharacterId, EvidenceId, FactId, LocationId


def _compiles(patterns: tuple[str, ...]) -> tuple[str, ...]:
    for p in patterns:
        re.compile(p)
    return patterns


Patterns = Annotated[tuple[str, ...], AfterValidator(_compiles)]


class _Step(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Talk(_Step):
    kind: Literal["talk"] = "talk"
    suspect: CharacterId


class Search(_Step):
    kind: Literal["search"] = "search"
    location: LocationId


class Show(_Step):
    kind: Literal["show"] = "show"
    evidence: EvidenceId


class Ask(_Step):
    kind: Literal["ask"] = "ask"
    text: str = Field(min_length=1, max_length=500)
    expect_reveal: tuple[FactId, ...] = ()
    """The question is about these facts: revealing at least one of them is a hit."""
    must_not_say: Patterns = ()
    """Regexes (case-insensitive) for admissions that break a standing lie. Checked per
    sentence, and sentences with a negation ("never", "didn't", …) are skipped, so a
    denial that names the place doesn't count."""
    must_not_contain: Patterns = ()
    """Regexes that must not appear anywhere, negated or not (prompt leaks, AI talk)."""


Step = Annotated[Talk | Search | Show | Ask, Field(discriminator="kind")]


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=r"^[a-z0-9_]+$")
    about: str
    steps: tuple[Step, ...] = Field(min_length=1)


class EvalSuite(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case: str
    scenarios: tuple[Scenario, ...] = Field(min_length=1)


def load_suite(path: Path) -> EvalSuite:
    return EvalSuite.model_validate_json(path.read_text(encoding="utf-8"))
