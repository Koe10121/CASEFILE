import json
from pathlib import Path
from typing import Any

import pytest

from casefile.case import CaseBundle, load_case

CASES_DIR = Path(__file__).resolve().parents[2] / "cases"
BLACKWOOD = CASES_DIR / "blackwood_manor"

RawCase = dict[str, dict[str, Any]]
"""The three files of a case as raw JSON, keyed by file stem."""


def read_raw(folder: Path) -> RawCase:
    return {
        stem: json.loads((folder / f"{stem}.json").read_text(encoding="utf-8"))
        for stem in ("case", "briefings", "solution")
    }


def write_raw(folder: Path, raw: RawCase) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for stem, data in raw.items():
        (folder / f"{stem}.json").write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture(scope="session")
def blackwood() -> CaseBundle:
    return load_case(BLACKWOOD)


@pytest.fixture
def blackwood_raw() -> RawCase:
    """A fresh, mutable copy of the Blackwood Manor JSON for each test."""
    return read_raw(BLACKWOOD)
