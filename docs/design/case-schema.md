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
- `time` has `from` and `to` (`"HH:MM"`, 24-hour; `to` is `null` for an instant) and `precision`, which is `exact` or `approx` (±10 min). An approximate time can never be used to catch a lie. An untimed fact leaves `time` out (D17).
- There is no separate timeline. The true timeline is all the timed facts, sorted.

**Evidence**: `id`, `name`, `location`, `summary`, optional `discover_when` (a condition), `establishes` (fact IDs), `deeper_reads` (`when` + `establishes` + `text`), which give up more once the player knows something else, and optional `text`, the verbatim contents of a document the player can read. If `discover_when` is left out, the item is available from the start.

**Location**: `id`, `name`, `description` and an optional `accessible_when` condition.

**Suspect briefing** (`AuthoredBriefing` in code, to keep it apart from the per-turn `SuspectBriefing` the engine builds): `persona` (summary, voice, sample lines, default demeanour), `opening_statement` (`text` + `claims`: the lies put on record when the player first meets them), `shares_freely`, `gated` (`fact` + `withheld_hint` + `reveal_when`), `lies` and `breaking_point` (`when` + `reveal` + `demeanor`).

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

## Where each rule is enforced

The Pydantic models in `backend/src/casefile/case/` enforce every rule that needs only one file. The case validator enforces the rules that need more than one (the table under [Validator rules](#validator-rules)).

| Enforced by the models | Example of what is rejected |
| --- | --- |
| No unknown keys in any object | `"subject"` instead of `"subjects"` |
| ID format by prefix | `"E01"` where a fact ID is expected |
| Times are `"HH:MM"`, 24-hour; spans don't end before they start | `"8:00"`, `"20:00:00"`, `from 21:00 to 20:50` |
| Enums: fact `kind`, `tags`, `precision`, difficulty settings | `"kind": "rumour"` |
| A condition has exactly one key, and it is a known one | `{"fact_known": …, "lie_caught": …}` |
| IDs are unique within their list; lie IDs are unique across suspects | Two facts called `F_DINNER` |
| A suspect never both shares and gates the same fact | `F_RICHARD_DEBTS` in `shares_freely` and `gated` |
| Every lie has at least one `contradicted_by` fact | `"contradicted_by": []` |
| The culprit has 3 to 5 guarded facts, each with a leak marker | Two guarded facts |
| Scoring totals 100, and the evidence points are exactly reachable | Four groups of 5 points but `"evidence": 25` |
| Solution steps are numbered 1..n and each one learns facts or breaks a lie | Steps out of order |
| All three files share one `case_id` (checked by the loader) | A solution from another case |

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

`backend/src/casefile/case/validation.py` runs every rule and reports all problems at once. The engine calls `load_valid_case` at startup, so a case with any error never reaches play (D22). The rule name is what appears in the report.

| Rule | Check | Severity |
| --- | --- | --- |
| `references` | Every ID resolves, including every ID inside a condition | error |
| `cast` | Every suspect has exactly one briefing, the accusation form lists exactly the suspects, and every character is in `world.present` | error |
| `answer_key` | The right culprit, motive and method are options on the form, and `max_evidence` allows full evidence marks | error |
| `guard_isolation` | Only the culprit's lies hide a `G_` fact. Typed IDs already stop a `G_` ID appearing anywhere else | error |
| `catchable_lies` | Every lie has a contradicting fact that evidence proves and that is not approximately timed | error |
| `on_record` | Every lie is in its own suspect's opening statement or on a fallback ladder from it, and no ladder loops | error |
| `solvability` | The reachability fixpoint catches every lie, reaches every solution step, and finds an item from every key evidence group | error |
| `dead_weight` | Every fact and evidence item is reachable | warning |
| `physical` | No one is in two places at overlapping times (guarded facts included) | error |
| `time_window` | Timed facts fall within the crime window | error |
| `coverage` | Each briefing covers the window with no gap over 15 minutes | error |
| `boundary_leak` | A freely shared whereabouts fact may not border an interval the suspect lies about | error |

### How solvability is computed

`reachability.py` starts from an empty game and applies every action a player could take, in rounds, until a round adds nothing. Each round reads only the previous round's state, so the round in which something first appears is its unlock depth. The search uses the same rule functions as the engine (`rules.py`) and the same condition evaluator (`conditions.holds`), so the proof is about the real game (D23).

| Assumption | Why it is safe |
| --- | --- |
| The player can talk to every suspect from the start | True in play |
| The player can show any item they hold to any suspect | True in play |
| Every open location gets searched | Searching costs nothing but time |
| Conditions only grow true | No negation in conditions (D05), so the fixpoint is exact and always terminates |

CASE #001 reaches everything in 6 rounds. Victoria's final lie falls in round 5 and her breaking point in round 6.
