# Design docs

| Doc | What it covers |
| --- | --- |
| [decision-log.md](decision-log.md) | Every design decision, why we made it, and what we rejected |
| [case-schema.md](case-schema.md) | The case data format, NPC output contract, injection defences and validator rules |
| [../cases/blackwood-manor.md](../cases/blackwood-manor.md) | Story spec for CASE #001 (spoilers) |
| [../research/similar-games.md](../research/similar-games.md) | Prior work and what we took from it |

## Milestones

| # | Milestone | Status |
| --- | --- | --- |
| 1 | Design CASE #001 and the case data model | Done |
| 2 | Backend engine: Pydantic models, validator as pytest, engine core, Richard end-to-end in mock AI mode | In review: step 4 of 4 (Richard end-to-end in mock AI mode) |
| 3 | Frontend (Nuxt or Vue + Vite, still to decide) | |
| 4 | AI integration: all four suspects | |
| 5 | Full investigation experience: save/resume, accusation, scoring | |
| 6 | Eval harness, testing and deployment | |
