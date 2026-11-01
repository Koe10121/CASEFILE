# CASEFILE backend

The game engine and, later, the API and AI layer. Python 3.12+, managed with [uv](https://docs.astral.sh/uv/).

## Play it

```bash
cd backend
uv run casefile        # CASE #001 in the terminal, mock AI, no API key needed
```

Type `help` for commands. Try `talk S_RICHARD`, `ask where were you tonight?`, `search LOC_OFFICE`, `show E07`.

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
| `src/casefile/engine/state.py` | `GameState`: an immutable record of what the player has done and learned |
| `src/casefile/engine/actions.py` | Player actions (`TalkTo`, `SearchLocation`, `ShowEvidence`, `Accuse`) and `NpcReveal`: together, one game-log entry |
| `src/casefile/engine/engine.py` | `Engine`: `new_game`, `apply`, `allowed_reveals`, `disclose` (the `reveal_fact` check) and `replay` |
| `src/casefile/engine/events.py` | What an action caused (fact learned, lie caught, …), for the UI and notebook |
| `src/casefile/engine/scoring.py` | `Accusation` and deterministic `score` |
| `src/casefile/engine/briefing.py` | `build_briefing`: the per-turn `SuspectBriefing`, the only thing a model sees |
| `src/casefile/ai/contract.py` | `NpcReply` (the `respond` output contract) and `Exchange` |
| `src/casefile/ai/provider.py` | `NpcProvider`, the protocol every provider implements |
| `src/casefile/ai/mock.py` | `MockNpc`: deterministic, no API spend |
| `src/casefile/ai/guard.py` | `find_leaks`: leak markers on the culprit's dialogue |
| `src/casefile/session.py` | `GameSession`: one game, wiring the engine, a provider and the transcript |
| `src/casefile/cli.py` | The terminal game (`uv run casefile`) |
| `tests/test_blackwood_loads.py` | The real CASE #001 loads, round-trips losslessly and is immutable |
| `tests/test_schema_rejects.py` | One test per schema rule, each breaking exactly one thing in the real case |
| `tests/test_conditions.py` | Condition evaluation on a hand-built state |
| `tests/test_case_validator.py` | The real case is valid and fully reachable; 17 broken copies each trip the right rule |
| `tests/test_engine.py` | The walkthrough scores 100, the engine reaches exactly what the validator proved, bad reveals are rejected, replay is deterministic |
| `tests/test_richard_slice.py` | Richard's full lie ladder end to end; briefings hold nothing a suspect may not say; a misbehaving model can't change the truth; leak guard |
| `tests/test_cli.py` | The terminal game wins CASE #001 in mock mode |
| `tests/test_scoring.py` | Scoring cases, including the wrong culprit and two items from one group |

## How a question to a suspect works

```text
player text -> 500-char cap -> build_briefing (engine) -> provider.respond
            -> engine.disclose (reveal check) -> leak guard (culprit only) -> reply
```

`GameSession` does this in `ask`. The engine calls underneath look like this:

## Engine calls

```python
engine = Engine(load_valid_case(path))  # one per case, shared by every session
state = engine.new_game()
state = engine.apply(state, TalkTo(suspect="S_RICHARD")).state  # opening lie on record
allowed = engine.allowed_reveals(state, "S_RICHARD")  # what the model may be told
result = engine.disclose(state, "S_RICHARD", model_reply.reveals)  # validate what it said
state = result.state  # accepted facts learned
log_eval_failures(result.rejected)  # unknown / guarded / not_allowed
```

Every call returns a new state; nothing changes in place. Store the log of actions and reveals, and `engine.replay(log)` rebuilds the game exactly.

## What the models check, and what they don't

The models check each file on its own: shapes, ID formats, times, enums, unique IDs, and rules that need only one file (scoring totals 100, solution steps are numbered in order, a fact is not both shared and gated).

Rules that need more than one file (every ID resolves, every lie is catchable, the case is solvable) belong to the case validator in `validation.py`. Use `load_valid_case` anywhere a case is loaded for play. The rules are listed in [`docs/design/case-schema.md`](../docs/design/case-schema.md#validator-rules).
