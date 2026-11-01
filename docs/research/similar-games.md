# Research: similar games and what we take from them

Researched 2026-11-01. The closest prior work gates an LLM suspect behind an authored tree of facts and lies, much like our schema, and cut critical hallucinations from 17.8% to 6.3% of replies. Its remaining failures shaped decisions D12–D14 in the [decision log](../design/decision-log.md).

| Work | What it does | What we take | What we avoid |
| --- | --- | --- | --- |
| [Interrogation of Adrian Gale](https://arxiv.org/pdf/2609.23043) (research, 2026) | One LLM suspect behind a JSON tree of facts and lies with prerequisites and contradictions. Three LLM calls per turn. Tested with 33 players. | Structured gating works. Its failure categories become our eval taxonomy. Prompts per contradiction (6.79) is a pacing metric. | Three calls per turn. An LLM choosing which fact to push (forced reveals). Gates so strict that 0 of 33 players got a confession. |
| [Vaudeville](https://www.keengamer.com/articles/previews/vaudeville-preview-the-ai-questioning-to-nowhere/) (2023) ([FAQ](https://store.epicgames.com/p/vaudeville-faq-dd3e5b)) | Voiced AI detective game with Llama 3 dialogue | What players hate: looping conversations, non-answers, NPCs contradicting each other | Free-form truth |
| [Case of the Golden Idol](https://www.gamedeveloper.com/design/case-of-the-golden-idol) (2022) | Fill-in-the-blank deduction | Minimal evidence, several routes to the answer, remove clues that make it trivial, 5–7 silent playtests | Open-ended text answers |
| [Return of the Obra Dinn](https://filmstories.co.uk/?p=83249) (2018) | Answers confirmed in batches of three | Guessing must not pay, so our accusation is final | Feedback that leaks answers |
| [Holmes](https://github.com/eliotjlee/holmes) | LLM-generated cases, suspects answer from vector-DB memories | A contrast: generated cases can't promise solvability | Generated truth, RAG |
| [AlibAi](https://store.steampowered.com/app/3325660/AlibAi) | The player is the killer among GPT-driven NPCs | The genre is full of thin LLM wrappers; CASEFILE's edge is guardrails and evals | Shipping without evals |

## Eval taxonomy (from the Adrian Gale paper, plus our own)

Unauthorized fact, invented alibi, invented entity, physical contradiction, sycophancy (accepting a bluff), persona break, plus two of our own: guarded-fact leak and non-answer.

**Targets:** a critical hallucination rate under 6.3% of replies, and a median of 4–8 prompts per caught lie on Normal.
