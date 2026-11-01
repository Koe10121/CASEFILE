"""Load a case folder (``case.json``, ``briefings.json``, ``solution.json``) into models."""

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

from casefile.case.briefings import Briefings
from casefile.case.solution import Solution
from casefile.case.world import Case


class CaseLoadError(Exception):
    """A case folder could not be read or does not match the schema."""


@dataclass(frozen=True, slots=True)
class CaseBundle:
    """The three files of one case, parsed.

    A plain dataclass, not a Pydantic model, on purpose: it has no ``model_dump()``, so
    there is no one-call way to serialise the case together with its solution (D02).
    """

    case: Case
    briefings: Briefings
    solution: Solution


def _load[M: BaseModel](path: Path, model: type[M]) -> M:
    try:
        return model.model_validate_json(path.read_bytes())
    except OSError as exc:
        raise CaseLoadError(f"cannot read {path}: {exc}") from exc
    except ValidationError as exc:
        raise CaseLoadError(f"{path} does not match the {model.__name__} schema:\n{exc}") from exc


def load_case(folder: Path) -> CaseBundle:
    """Parse and schema-check one case folder.

    This checks each file's shape and its internal invariants. Cross-file rules
    (every ID resolves, every lie is catchable, the case is solvable) are the case
    validator's job, not the loader's.
    """
    bundle = CaseBundle(
        case=_load(folder / "case.json", Case),
        briefings=_load(folder / "briefings.json", Briefings),
        solution=_load(folder / "solution.json", Solution),
    )
    ids = {bundle.case.case_id, bundle.briefings.case_id, bundle.solution.case_id}
    if len(ids) != 1:
        raise CaseLoadError(f"{folder}: the three files disagree on case_id: {sorted(ids)}")
    return bundle
