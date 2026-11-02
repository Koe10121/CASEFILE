# CASEFILE backend

The game engine, the AI layer and the HTTP API for the web game. Python 3.12+, managed with [uv](https://docs.astral.sh/uv/).

## Play it

```bash
cd backend
uv run casefile               # CASE #001 in the terminal; a local model (Ollama) plays the suspects: free
uv run casefile --ai mock     # scripted suspects: no setup at all
uv run casefile --ai claude   # Claude plays the suspects: pay as you go
```

Type `help` for commands. Try `talk S_RICHARD`, `ask where were you tonight?`, `search LOC_OFFICE`, `show E07`.

**Free real AI (Ollama).** Install [Ollama](https://ollama.com), run `ollama pull llama3.1:8b`, and keep the Ollama app running. Any model with structured-output support works; set `CASEFILE_OLLAMA_MODEL` to try another. An 8B model needs about 8 GB of free memory and is slower and less consistent than Claude.

**Claude.** Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY` (from console.anthropic.com). `.env` is git-ignored.

Either way, a game stops taking questions after a token budget: 400,000 on Claude (`CASEFILE_SESSION_TOKEN_BUDGET`, a cost cap) and 2,000,000 on a local model (`CASEFILE_LOCAL_SESSION_TOKEN_BUDGET`, free, but still capped so a runaway session ends). Each question re-sends the suspect's briefing, about 3–5k tokens. Every setting is listed in `.env.example`; Ollama is the default (`CASEFILE_AI`); if it isn't running or the model isn't pulled, the game says so at startup and suggests `--ai mock`.

## Serve the API

```bash
uv run casefile-api                # http://127.0.0.1:8000; a local model (Ollama) plays the suspects
uv run casefile-api --ai mock      # scripted suspects: no setup at all
```

Open http://127.0.0.1:8000/docs to try every endpoint in the browser. On Windows PowerShell, start the server in one window:

```powershell
cd C:\Users\User\CASEFILE\backend
uv run casefile-api
```

and talk to it from a second window:

```powershell
$game = Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/games -ContentType application/json -Body '{}'
Invoke-RestMethod -Method Post "http://127.0.0.1:8000/api/games/$($game.id)/talk" -ContentType application/json -Body '{"suspect":"S_RICHARD"}'
```

| Endpoint | What it does |
| --- | --- |
| `GET /api/case` | The case's cover: title, intro, detective, people, accusation options, which AI is playing |
| `POST /api/games` | Start a game (`{"difficulty": "easy" \| "normal" \| "hard"}`) |
| `GET /api/games/{id}` | The game as the player sees it (resume after a reload) |
| `POST /api/games/{id}/talk` | `{"suspect": "S_RICHARD"}`: start or resume an interview |
| `POST /api/games/{id}/ask` | `{"text": "..."}`: ask the suspect you are talking to |
| `POST /api/games/{id}/search` | `{"location": "LOC_STUDY"}` |
| `POST /api/games/{id}/show` | `{"evidence": "E05"}`: show an item to the suspect you are talking to |
| `POST /api/games/{id}/accuse` | `{"accusation": {"culprit", "motive", "method", "evidence": [...]}}`: final |

Each action returns `line` (what the suspect said, if anything), `events` (what happened) and `game` (the whole player view). Errors are `{"detail": "..."}`: 404 unknown or expired game, 409 an illegal move or a request while the last one is still running, 422 a malformed request, 429 the token budget is spent, 502 the model didn't answer (nothing changed), 503 the server is full. Games live in memory for now, so restarting the server ends them.

`uv run casefile-api --openapi ../frontend/openapi.json` writes the API schema that the frontend's TypeScript types are generated from (see [`frontend/README.md`](../frontend/README.md#api-types)).

## Score a model (eval harness)

```bash
uv run casefile-eval --ai ollama --model gemma3:12b   # free, local
uv run casefile-eval --ai claude --repeat 1           # costs a few cents
```

Plays the scripted interviews in `evals/blackwood_manor.json` (each one 3 times by default) and checks every suspect line: broken lies, invented times, clue facts not declared, jailbreaks that worked, culprit leaks, bad fact IDs, parroted sample lines, latency and tokens. It prints a summary table and writes the full transcript, with each flag marked, to `eval-results/` (git-ignored). The checks are text heuristics, so read the flagged lines in the transcript before trusting a number.

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
| `src/casefile/settings.py` | `Settings`: which AI, models, token budget and the API key, from the environment or `.env` |
| `src/casefile/ai/contract.py` | `NpcReply` (the reply contract), `Exchange`, `Usage`, `NpcTurn`, `ProviderError` |
| `src/casefile/ai/provider.py` | `NpcProvider`, the protocol every provider implements |
| `src/casefile/ai/mock.py` | `MockNpc`: deterministic, no API spend |
| `src/casefile/ai/prompt.py` | The suspect prompt: cached instructions, this turn's briefing, the reply schema |
| `src/casefile/ai/claude.py` | `ClaudeNpc`: the Claude provider (structured output, prompt caching, usage) |
| `src/casefile/ai/ollama.py` | `OllamaNpc`: the free local-model provider, same prompt and contract |
| `src/casefile/ai/guard.py` | `find_leaks` and `find_confession`: the culprit's output guard |
| `src/casefile/ai/grounding.py` | `ground`: keeps only the reveals the dialogue actually says, and adds facts it clearly states (D41) |
| `src/casefile/session.py` | `GameSession`: one game, wiring the engine, a provider and the transcript |
| `src/casefile/ai/factory.py` | `make_provider`: the provider a setting names |
| `src/casefile/evals/` | The eval harness: scenario models, the per-line checks, the runner (`uv run casefile-eval`) |
| `evals/blackwood_manor.json` | Eval scenarios for CASE #001 (author-only: they name what each lie hides) |
| `src/casefile/cli.py` | The terminal game (`uv run casefile`) |
| `src/casefile/api/app.py` | The FastAPI app: routes, error mapping, `uv run casefile-api` |
| `src/casefile/api/schemas.py` | Request and response models: only what a player may see |
| `src/casefile/api/views.py` | The spoiler boundary: game state to player view (D44) |
| `src/casefile/api/store.py` | `GameStore`: games in memory, one lock per game, idle expiry (D46) |
| `tests/test_blackwood_loads.py` | The real CASE #001 loads, round-trips losslessly and is immutable |
| `tests/test_schema_rejects.py` | One test per schema rule, each breaking exactly one thing in the real case |
| `tests/test_conditions.py` | Condition evaluation on a hand-built state |
| `tests/test_case_validator.py` | The real case is valid and fully reachable; 17 broken copies each trip the right rule |
| `tests/test_engine.py` | The walkthrough scores 100, the engine reaches exactly what the validator proved, bad reveals are rejected, replay is deterministic |
| `tests/test_richard_slice.py` | Richard's full lie ladder end to end; briefings hold nothing a suspect may not say; a misbehaving model can't change the truth; leak guard |
| `tests/test_claude_provider.py` | The Claude provider against a fake client: request shape, caching, escaping, gating, every failure path |
| `tests/test_ollama_provider.py` | The Ollama provider against a fake server: request, gating, escaping, failures |
| `tests/test_grounding.py` | Grounding and the confession guard, on real lines from the first local eval |
| `tests/test_evals.py` | The eval checks, the scenario file against the case, a clean mock baseline, and a bad reply tripping every check |
| `tests/test_cli.py` | The terminal game wins CASE #001 in mock mode |
| `tests/test_api.py` | CASE #001 won over HTTP; no response of a whole game (even with a leaking model) carries a secret or anything not yet discovered; every error code; the store's locks and expiry |
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
