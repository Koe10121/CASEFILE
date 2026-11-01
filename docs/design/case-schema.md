# Case data schema

A case is a folder with three JSON files. The engine loads and validates all three. The AI layer never reads them; it receives one `SuspectBriefing` per turn, built by the engine. The reasons behind each choice are in [decision-log.md](decision-log.md).

| File | Contains | Ever sent to the LLM? |
| --- | --- | --- |
| `case.json` | Setting, detective, closed `world`, characters (public bios), locations, the fact catalogue, evidence, accusation options, difficulty profiles | Only as slices inside a briefing |
| `briefings.json` | Per suspect: persona and voice, opening statement, `shares_freely`, `gated` facts, the lie ladder, the breaking point | Only the current suspect's slice, filtered by game state |
| `solution.json` | Culprit, motive, method, guarded facts with leak markers, key evidence groups, solution chain with hints, epilogue, scoring | Guarded facts go to the culprit's briefing only. Nothing else, ever. |

## IDs

| Prefix | Entity | Example |
| --- | --- | --- |
| `F_` | Fact | `F_LOCK_NO_OPENING_2144_2158` |
| `G_` | Guarded fact (solution only, opaque) | `G_01` |
| `S_` | Character | `S_VICTORIA` |
| `E` | Evidence | `E05` |
| `LOC_` | Location | `LOC_STUDY` |
| `LIE_` | Scripted lie | `LIE_VICTORIA_NO_CONTACT` |
| `MOT_` / `MTH_` | Accusation options | `MOT_HIDE_THEFT`, `MTH_AWARD_STAGED` |

IDs are permanent once published, because saves refer to them. The API only ever sends the player facts they have already uncovered.

## Entities

**Fact**

```json
{ "id": "F_LOCK_NO_OPENING_2144_2158",
  "statement": "Study lock log: the door was not opened at all between 21:44 and 21:58.",
  "kind": "object_state",
  "subjects": [],
  "location": "LOC_STUDY",
  "time": { "from": "21:44", "to": "21:58", "precision": "exact" },
  "tags": ["key"] }
```

- `kind` is one of `presence`, `movement`, `action`, `object_state`, `relationship`, `motive` or `knowledge`.
- `time.precision` is `exact`, `approx` (±10 min) or `none`. An approximate time can never be used to catch a lie.
- There is no separate timeline. The true timeline is all the timed facts, sorted.

**Evidence**: `id`, `name`, `location`, `summary`, optional `discover_when` (a condition), `establishes` (fact IDs), and `deeper_reads` (`when` + `establishes` + `text`), which give up more once the player knows something else. If `discover_when` is left out, the item is available from the start.

**Location**: `id`, `name`, `description` and an optional `accessible_when` condition.

**Suspect briefing**: `persona` (summary, voice, sample lines, default demeanour), `opening_statement` (`text` + `claims`: the lies put on record when the player first meets them), `shares_freely`, `gated` (`fact` + `withheld_hint` + `reveal_when`), `lies` and `breaking_point` (`when` + `reveal` + `demeanor`).

**Lie**

```json
{ "id": "LIE_RICHARD_BILLIARD",
  "claim": "I was in the billiard room all evening, apart from a cigarette on the terrace.",
  "hides": "F_RICHARD_OFFICE",
  "why": "Being in Arthur's office looks like theft on the night he died.",
  "contradicted_by": ["F_RICHARD_OFFICE"],
  "on_caught": { "fallback_lie": "LIE_RICHARD_NOTE", "reveal": [] } }
```

A lie is caught when the player shows that suspect evidence that establishes a fact in `contradicted_by`, after the lie has been told.

**Conditions**

```
Condition := { "all": [Condition, ...] } | { "any": [Condition, ...] } | Atom
Atom      := { "location_searched": LOC } | { "evidence_found": E }
           | { "evidence_shown": E }   // shown to this suspect
           | { "fact_known": F } | { "lie_caught": LIE } | { "talked_to": S }
```

Conditions have no negation, so every condition is monotone and solvability is a fixpoint.

**Guarded fact**: `id`, `statement` (second person, for the culprit's briefing), optional `time`, `location`, `subjects`, `kind`, and `leak_markers` (`phrase` + optional `unless_known`).

## NPC output contract

```json
{ "reveals": ["F_RICHARD_TERRACE"], "demeanor": "hostile", "dialogue": "Look, I was on the terrace. Ask anyone." }
```

`reveals` must be a subset of what this suspect can reveal right now. Anything else is dropped and logged as an eval failure. The notebook shows the fact's canonical `statement`.

## Prompt-injection defences

| Layer | Defence |
| --- | --- |
| 1 | Context gating: unrevealed facts are never in the prompt |
| 2 | Player text only in the user turn, inside `<detective_says>` tags, and treated as in-world speech |
| 3 | In-character refusal of meta questions, with authored examples |
| 4 | Game state changes only through validated IDs |
| 5 | `leak_markers` filter on the culprit's output |
| 6 | Input length cap, per-session token budget, rate limit |
| 7 | Injection corpus in the eval harness, run on every prompt change |

## Validator rules

| Check | Rule |
| --- | --- |
| Referential integrity | Every ID resolves |
| Guard isolation | `G_` IDs appear only in `solution.json` and the culprit's lies' `hides` |
| Catchable lies | Every lie has a contradicting fact that evidence establishes |
| On record | Every lie is in an opening statement or a fallback chain from one |
| Solvability | Fixpoint over player actions reaches every lie, solution step and key evidence group |
| Dead weight | Every fact and evidence item is reachable |
| Physical consistency | No one is in two places at overlapping times |
| Time window | Timed facts fall within the crime window |
| Whereabouts coverage | Each briefing covers the window with no gap over 15 minutes |
| Boundary leak | A freely shared whereabouts fact may not border an interval the suspect lies about |
