"""Each schema rule rejects the mistake it exists for.

Every case starts from the real Blackwood Manor JSON and breaks exactly one thing, so a
failure here means that one rule stopped working.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from casefile.case import CaseLoadError, load_case
from casefile.case.briefings import Briefings
from casefile.case.solution import Solution
from casefile.case.world import Case
from tests.conftest import RawCase, write_raw

Mutation = Callable[[dict[str, Any]], None]

MODELS: dict[str, type[BaseModel]] = {"case": Case, "briefings": Briefings, "solution": Solution}


def _fact(raw: dict[str, Any], fact_id: str) -> dict[str, Any]:
    return next(f for f in raw["facts"] if f["id"] == fact_id)


def _evidence(raw: dict[str, Any], evidence_id: str) -> dict[str, Any]:
    return next(e for e in raw["evidence"] if e["id"] == evidence_id)


def _suspect(raw: dict[str, Any], suspect_id: str) -> dict[str, Any]:
    return next(s for s in raw["suspects"] if s["suspect"] == suspect_id)


def _set_time(value: str) -> Mutation:
    return lambda c: _fact(c, "F_DINNER")["time"].__setitem__("from", value)


def _set_condition(value: Any) -> Mutation:
    return lambda c: _evidence(c, "E02").__setitem__("discover_when", value)


REJECTIONS: list[tuple[str, str, Mutation, str]] = [
    # (id, file, mutation, expected error text)
    (
        "misspelt key",
        "case",
        lambda c: _fact(c, "F_DINNER").__setitem__("subject", []),
        "Extra inputs are not permitted",
    ),
    (
        "lowercase fact id",
        "case",
        lambda c: _fact(c, "F_DINNER").__setitem__("id", "F_dinner"),
        "should match pattern",
    ),
    (
        "evidence id where a fact id belongs",
        "case",
        lambda c: _evidence(c, "E02")["establishes"].append("E01"),
        "should match pattern '^F_",
    ),
    ("time with seconds", "case", _set_time("20:00:00"), "24-hour 'HH:MM'"),
    ("hour 24", "case", _set_time("24:00"), "24-hour 'HH:MM'"),
    ("single-digit hour", "case", _set_time("8:00"), "24-hour 'HH:MM'"),
    ("span ends before it starts", "case", _set_time("21:00"), "ends (20:50) before it starts"),
    (
        "precision 'none' (omit time instead)",
        "case",
        lambda c: _fact(c, "F_DINNER")["time"].__setitem__("precision", "none"),
        "'exact' or 'approx'",
    ),
    (
        "unknown fact kind",
        "case",
        lambda c: _fact(c, "F_DINNER").__setitem__("kind", "rumour"),
        "Input should be 'presence'",
    ),
    (
        "duplicate fact id",
        "case",
        lambda c: c["facts"].append(dict(c["facts"][0])),
        "duplicate fact IDs: F_DINNER",
    ),
    (
        "condition with two keys",
        "case",
        _set_condition({"fact_known": "F_DINNER", "lie_caught": "LIE_RICHARD_NOTE"}),
        "exactly one key",
    ),
    (
        "unknown condition atom",
        "case",
        _set_condition({"player_is_persuasive": True}),
        "player_is_persuasive",
    ),
    ("empty all-of", "case", _set_condition({"all": []}), "at least 1 item"),
    (
        "bad id deep inside a nested condition",
        "case",
        _set_condition({"all": [{"any": [{"fact_known": "E05"}]}]}),
        "should match pattern '^F_",
    ),
    (
        "crime window crosses midnight",
        "case",
        lambda c: c["setting"]["crime_window"].__setitem__("to", "01:00"),
        "same night",
    ),
    (
        "missing difficulty",
        "case",
        lambda c: c["difficulty_profiles"].pop("hard"),
        "hard\n  Field required",
    ),
    (
        "malformed hint policy",
        "case",
        lambda c: c["difficulty_profiles"]["normal"].__setitem__("hints", "sometimes"),
        "should match pattern",
    ),
    (
        "duplicate motive option",
        "case",
        lambda c: c["accusation_options"]["motives"].append(c["accusation_options"]["motives"][0]),
        "duplicate motive IDs",
    ),
    (
        "lie nothing can contradict",
        "briefings",
        lambda b: _suspect(b, "S_RICHARD")["lies"][0].__setitem__("contradicted_by", []),
        "at least 1 item",
    ),
    (
        "fact both shared and gated",
        "briefings",
        lambda b: _suspect(b, "S_RICHARD")["shares_freely"].append("F_RICHARD_DEBTS"),
        "duplicate S_RICHARD shared-or-gated fact IDs: F_RICHARD_DEBTS",
    ),
    (
        "same lie id on two suspects",
        "briefings",
        lambda b: _suspect(b, "S_THOMAS")["lies"].append(_suspect(b, "S_RICHARD")["lies"][0]),
        "duplicate lie IDs: LIE_RICHARD_BILLIARD",
    ),
    (
        "demeanor with spaces",
        "briefings",
        lambda b: _suspect(b, "S_RICHARD")["breaking_point"].__setitem__("demeanor", "very sad"),
        "should match pattern",
    ),
    (
        "scoring adds up to 105",
        "solution",
        lambda s: s["scoring"].__setitem__("culprit", 45),
        "must total 100 points, got 105",
    ),
    (
        "evidence points unreachable",
        "solution",
        lambda s: s["key_evidence_groups"].pop(),
        "3 groups x 5 = 15",
    ),
    (
        "solution steps out of order",
        "solution",
        lambda s: s["solution_chain"].reverse(),
        "numbered 1..n in order",
    ),
    (
        "solution step with no goal",
        "solution",
        lambda s: s["solution_chain"][0].pop("learn"),
        "must `learn` facts or `breaks` a lie",
    ),
    (
        "too few guarded facts",
        "solution",
        lambda s: s.__setitem__("guarded_facts", s["guarded_facts"][:2]),
        "at least 3 items",
    ),
    (
        "guarded fact with no leak markers",
        "solution",
        lambda s: s["guarded_facts"][0].__setitem__("leak_markers", []),
        "at least 1 item",
    ),
]


@pytest.mark.parametrize(
    ("stem", "mutate", "expected"),
    [pytest.param(stem, mutate, expected, id=name) for name, stem, mutate, expected in REJECTIONS],
)
def test_schema_rejects(blackwood_raw: RawCase, stem: str, mutate: Mutation, expected: str) -> None:
    data = blackwood_raw[stem]
    mutate(data)
    with pytest.raises(ValidationError) as excinfo:
        MODELS[stem].model_validate(data)
    assert expected in str(excinfo.value)


def test_loader_rejects_mismatched_case_ids(blackwood_raw: RawCase, tmp_path: Path) -> None:
    blackwood_raw["solution"]["case_id"] = "some-other-case"
    write_raw(tmp_path, blackwood_raw)
    with pytest.raises(CaseLoadError, match="disagree on case_id"):
        load_case(tmp_path)


def test_loader_names_the_broken_file(blackwood_raw: RawCase, tmp_path: Path) -> None:
    blackwood_raw["briefings"]["suspects"][0]["persona"]["default_demeanor"] = "Not A Word"
    write_raw(tmp_path, blackwood_raw)
    with pytest.raises(CaseLoadError, match=r"briefings\.json does not match the Briefings schema"):
        load_case(tmp_path)


def test_loader_reports_a_missing_file(blackwood_raw: RawCase, tmp_path: Path) -> None:
    write_raw(tmp_path, blackwood_raw)
    (tmp_path / "solution.json").unlink()
    with pytest.raises(CaseLoadError, match=r"cannot read .*solution\.json"):
        load_case(tmp_path)
