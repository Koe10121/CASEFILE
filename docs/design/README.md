# Design docs

| Doc | What it covers |
| --- | --- |
| [decision-log.md](decision-log.md) | Every design decision, why we made it, and what we rejected |
| [ai-evals.md](ai-evals.md) | Eval results for the AI suspects, the chosen local model and its known limits |
| [case-schema.md](case-schema.md) | The case data format, NPC output contract, injection defences and validator rules |
| [../cases/blackwood-manor.md](../cases/blackwood-manor.md) | Story spec for CASE #001 (spoilers) |
| [../research/similar-games.md](../research/similar-games.md) | Prior work and what we took from it |

## Milestones

| # | Milestone | Status |
| --- | --- | --- |
| 1 | Design CASE #001 and the case data model | Done |
| 2 | Backend engine: Pydantic models, validator as pytest, engine core, Richard end-to-end in mock AI mode | Done |
| 3 | Frontend: HTTP API, then the Vue 3 web game | Done: the HTTP API (D43–D46) and the Vue + Vite game (D47–D48) are playable from the cover to the results, with caught suspects reacting (D52), save and resume (D53), hints and the Easy evidence picker (D54), and painted-noir portraits that change with each suspect's mood (D55, art in `cases/blackwood_manor/portraits/`) |
| 4 | AI integration: all four suspects | Done: Claude and free Ollama providers, eval harness, grounding and confession guard. See [ai-evals.md](ai-evals.md) |
| 5 | Full investigation experience: save/resume, accusation, scoring | Done, delivered with Milestones 2 and 3: scoring (D29), accusation and results, save and resume (D53) |
| 6 | Eval harness, testing and deployment | Next. The eval harness is done (Milestone 4). The end-to-end browser test runs in CI (D56). The game ships as one Docker image with rate limits, hosted on Render (D57). Left: players bring their own Claude key, then the per-game budget for it (players bring their own Claude key, rate limits, per-game budgets) |
