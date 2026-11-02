# CASE #001: The Last Evening at Blackwood Manor (story spec)

> **Spoilers.** This is the full solution. The data is in [`cases/blackwood_manor/`](../../cases/blackwood_manor/).

## Premise

Halloween, Saturday 31 October 2026, on the North Yorkshire moors. Arthur Blackwood (61), founder of Blackwood Systems, maker of the HALDEN smart-home assistant, is found dead in his soundproofed study at 22:45. He is slumped in his chair with his headset on, facing the dark window. Every door logs who opens it, and every room has an intercom. A storm has taken out the mobile mast. Everyone in the house heard Arthur alive at 22:25.

The player is **DI Voss, call sign "Nightjar"**, North Yorkshire Major Crimes: Rhea (she/her) by default, or Rhys (he/him) or Rae (they/them), as the player chooses (D51). The description below uses the default. She takes the calls that come in after midnight. She is former digital forensics and wears her late father's wind-up watch, because she won't trust a clock that can be told what time it is. She arrives at 23:40.

| Character | Role | Secret |
| --- | --- | --- |
| Victoria Shaw (34) | Executive assistant, house-system admin. **Culprit.** | Has stolen £2.1M with a clone of Arthur's voice to pay for her mother's dementia care. Killed him when he found out. |
| Richard Okafor (58) | Business partner and CFO | Copied the Kestrel term sheet to go over Arthur's head. Deep in debt. |
| Eleanor Blackwood (52) | Wife | Took and burned the new will that cut her out |
| Thomas Reid (63) | Butler | Left his post to phone his daughter, who was in labour |

## True timeline

| Time | What happened | Recorded by |
| --- | --- | --- |
| 20:00–20:50 | Dinner. At 20:35 Arthur kills the Kestrel deal. At 20:40 he argues with Richard: "You'll regret this, Arthur." | Testimony |
| 21:10–21:22 | Arthur fetches port from the cellar. At 21:16 Eleanor enters the study, takes the new will and leaves at 21:19. She burns it at about 21:25. | Study lock log, burnt fragment |
| 21:31–21:37 | Harcourt Bank's fraud team calls Arthur about voice-authorised transfers made while he was on a flight | Desk notepad |
| 21:36–21:52 | Richard copies the term sheet in Arthur's office | Office lock log, USB stick |
| 21:41 | Arthur on the intercom to Victoria's room: "Victoria. Study. Now." | Study panel |
| 21:44 | Victoria's iPad joins the study Wi-Fi, and Arthur lets her in | Audit log, lock log |
| ~21:52 | Victoria strikes Arthur with his crystal award. He dies. | Guarded |
| 21:51–22:04 | Thomas at the gate on the phone. At 21:55 the camera catches a figure at the study window: Victoria staging the body. | Gate camera |
| 21:57–21:58 | Victoria uploads a cloned clip ("Not now, I'm on a call") and builds the "Quiet Hours" routine: privacy lock, intercom auto-reply, lights flicker at 22:20, unlock at 22:40. She leaves at 21:58. | Audit log, lock log |
| 21:58 | Thomas's grandson is born | Thomas |
| 22:05–22:40 | Victoria on a recorded video call in the library (a true alibi) | Testimony, Wi-Fi |
| 22:15 / 22:25 | Thomas, then Eleanor, hear "Arthur" over the intercom: the same words and the same sigh | Testimony, study panel |
| 22:45 | Thomas finds the body | Lock log |
| 22:52 | Victoria deletes the routine. The audit log is append-only. | Audit log, Richard |

## Lies and what catches them

| Suspect | Lie | Caught by | Then |
| --- | --- | --- | --- |
| Victoria | "I didn't see or hear from Arthur after dinner." | E05 summons, or E10 Wi-Fi | Lie 2 |
| Victoria | "He called me in. I left at ten to ten, and he was alive." | E04: no door opening 21:44–21:58, or E10 routine | Lie 3 |
| Victoria | "Lots of people can set up routines." | E10: only two admins, routine made from her iPad | Breaking point (with E11): admits the theft and why, never the killing |
| Richard | "Billiard room all evening." | E07 office log | "I left him a note." |
| Richard | "I left him a note about the deal." | E08 USB stick | Admits his debts; saw Victoria on her iPad at 22:52 |
| Eleanor | "I didn't go into the study." | E04 lock log, 21:16 | "I took nothing." |
| Eleanor | "I took nothing." | E09 burnt will | Admits the will; still believes Arthur was alive at 22:25 |
| Thomas | "In the pantry the whole time." | E06 gate camera | Saw a figure at 21:55; when shown the footage again: "hair pinned up" |

## Evidence

| ID | Item | Location | Unlocks when |
| --- | --- | --- | --- |
| E01 | Body and scene (deeper read: drag marks, so he was moved) | Study | Start |
| E02 | Crystal award: no prints at all, blood in the engraving | Study | Search the study |
| E03 | Desk notepad: "VoiceKey phone auth… I was over the Atlantic… Who could sound like me?" | Study | Search the study |
| E04 | Study lock log | Hall panel | Start |
| E05 | Study wall panel (deeper read: intercom history) | Study | Search the study; deeper read once either voice testimony is known |
| E06 | Gate camera footage | Gatehouse | Search the gatehouse |
| E07 | Office lock log | Arthur's office | Search the office |
| E08 | USB stick in Richard's coat | Cloakroom | Richard's first lie caught |
| E09 | Burnt will fragment | Drawing room | Search the drawing room |
| E10 | HALDEN audit export | Hall panel | The auto-reply is known |
| E11 | Victoria's laptop bag: Northlight card, `AB_voice` clips | Guest room 2 | Victoria's first lie caught |
| E12 | Arthur's journal: "I heard myself in the hall speaker." | Study | Search the study |

## Intended solution path

1. Thomas and Eleanor each heard "Arthur" saying exactly the same thing.
2. The study panel shows both replies were auto-replies. Arthur summoned Victoria at 21:41.
3. Show the panel to Victoria: her first lie breaks.
4. Show her the lock log: her second lie breaks.
5. Request the audit export and show it to her: her third lie breaks.
6. The award was wiped, though Arthur handled it daily, so it is the weapon.
7. The notepad and her bag give the motive.

**Correct accusation:** Victoria, to stop Arthur exposing a theft, by striking him with the award, staging him at his desk and using the house to fake signs of life. The trap option is "struck him after the door unlocked at 22:40".

## Red herrings

| Herring | How it resolves |
| --- | --- |
| Richard's threat, lie, office visit and debts | He was in the office during the killing. The study log never lets him in. |
| Eleanor in the study, lying, burning the will | Arthur came back at 21:22 and summoned Victoria at 21:41, so he was alive after Eleanor's visit |
| The "haunted" house and Arthur's journal | The notepad shows voice-ID fraud. He really was hearing a clone of himself. |

## Validation

The case passes all the validator rules in [case-schema.md](../design/case-schema.md#validator-rules). It has 8 unlock layers, and the largest gap in any suspect's whereabouts is 2 minutes. Remaining risks to playtest: how hard the voice leap is on Hard, whether the audit export is too decisive, players asking about time of death (nobody present can judge it), and the plausibility of moving the body.
