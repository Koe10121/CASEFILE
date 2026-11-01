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
| 3 | Frontend (Nuxt or Vue + Vite, still to decide) | Next |
| 4 | AI integration: all four suspects | Done: Claude and free Ollama providers, eval harness, grounding and confession guard. See [ai-evals.md](ai-evals.md) |
| 5 | Full investigation experience: save/resume, accusation, scoring | |
| 6 | Eval harness, testing and deployment | |
