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
| `src/casefile/case/loader.py` | `load_case(folder) -> CaseBundle` |
| `tests/test_blackwood_loads.py` | The real CASE #001 loads, round-trips losslessly and is immutable |
| `tests/test_schema_rejects.py` | One test per schema rule, each breaking exactly one thing in the real case |

## What the models check, and what they don't

The models check each file on its own: shapes, ID formats, times, enums, unique IDs, and rules that need only one file (scoring totals 100, solution steps are numbered in order, a fact is not both shared and gated).

Rules that need more than one file (every ID resolves, every lie is catchable, the case is solvable) belong to the case validator, which is the next step of Milestone 2. See [`docs/design/case-schema.md`](../docs/design/case-schema.md#validator-rules).
