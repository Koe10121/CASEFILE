# CASEFILE backend

The game engine and, later, the API and AI layer. Python 3.12+, managed with [uv](https://docs.astral.sh/uv/).

## Run the checks

```bash
cd backend
uv sync                    # creates .venv with the app and dev dependencies
uv run pytest              # tests
uv run mypy                # strict type check (src and tests)
uv run ruff check .        # lint
uv run ruff format .       # format
```

CI runs the same four checks on every pull request that touches `backend/` or `cases/` (`.github/workflows/backend.yml`).

## Layout

| Path | What it is |
| --- | --- |
| `src/casefile/case/ids.py` | Typed IDs (`FactId`, `EvidenceId`, …): distinct types for mypy, pattern-checked by Pydantic |
| `src/casefile/case/base.py` | `CaseModel` (strict, immutable base), `ClockTime`, `TimeSpan`, `Window` |
| `src/casefile/case/conditions.py` | The reveal/unlock condition tree (`all`, `any` and six atoms) |
| `src/casefile/case/world.py` | Models for `case.json` |
| `src/casefile/case/briefings.py` | Models for `briefings.json` |
| `src/casefile/case/solution.py` | Models for `solution.json` |
| `src/casefile/case/loader.py` | `load_case(folder) -> CaseBundle` (schema checks only) |
| `src/casefile/case/index.py` | `CaseIndex`: ID lookups over a loaded case |
| `src/casefile/case/rules.py` | Game rules shared by the validator and the engine |
| `src/casefile/case/reachability.py` | The solvability fixpoint: everything a player could ever reach |
| `src/casefile/case/validation.py` | `validate_case` (every cross-file rule) and `load_valid_case` (what the engine calls) |
| `tests/test_blackwood_loads.py` | The real CASE #001 loads, round-trips losslessly and is immutable |
| `tests/test_schema_rejects.py` | One test per schema rule, each breaking exactly one thing in the real case |
| `tests/test_conditions.py` | Condition evaluation on a hand-built state |
| `tests/test_case_validator.py` | The real case is valid and fully reachable; 17 broken copies each trip the right rule |

## What the models check, and what they don't

The models check each file on its own: shapes, ID formats, times, enums, unique IDs, and rules that need only one file (scoring totals 100, solution steps are numbered in order, a fact is not both shared and gated).

Rules that need more than one file (every ID resolves, every lie is catchable, the case is solvable) belong to the case validator in `validation.py`. Use `load_valid_case` anywhere a case is loaded for play. The rules are listed in [`docs/design/case-schema.md`](../docs/design/case-schema.md#validator-rules).
