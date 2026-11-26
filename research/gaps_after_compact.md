# What didn't carry over after the compact (Yim, 2026-11-26)

The user: "a lot of knowledge was dropped in the last compact ... keep going for now, I want to see how
broken the experience is and why so much was not carried over properly." Each gap: what happened, where
the knowledge actually lived, and why I didn't have it.

| # | What happened | Where the knowledge was | Why it was missed |
|---|---|---|---|
| 1 | Started the watcher as `--idle` with no value: it crashed and nothing watched the Joppa explore | tools/watch_handover.py's own arguments | I wrote the call from the summary's wording ("`--idle`") instead of reading the tool |
| 2 | Re-planned the outskirts to hunt two giant dragonflies, narrated as "worth hunting" | brain/scripts/fight.py (`flying` prey skipped), design.md, retro_shwyragaun.md | The summary listed "flying prey is skipped" as a code detail, not as a rule for my own planning; I didn't check the creatures' effects before deciding |
| 3 | Joppa's in-town args (fight and hunt off) carried into the outskirts via next_zone.py | next_zone.py copies the current explore args | A latent bug; earlier runs started outside town or with default args. Fixed: leaving copies force fight/hunt back on |
| 4 | A popup ("There's nothing to take.") sat unanswered for minutes | - | A real bug, not lost knowledge: a script's narration-only answer became PASS on a popup, and a popup never asks again. Fixed in step.py (WAIT off the map); the watcher now reports a popup unanswered for 25 s; collect marks "nothing to take" kinds as skip |
| 6 | Walked north zone by zone toward Red Rock instead of taking the world map (the user: "never in the plan before") | playbook_level5.md milestone 2 (world map, 2 steps north); research/goals.md (2026-11-24: "Move up" then two steps north) | I misread the playbook's later line "Red Rock strata 1-3 on foot (no world-map steps: they get us lost)", which is about the strata, as the route there, and didn't check how the earlier characters actually got there |
| 7 | The close-fight hand-over with a croc came in a zone I shouldn't have been in; I fought it by hand to 5/18 HP | - | A consequence of 6. Also: `walk.py --ignore croc` still stopped for the known croc (the ignore covers creatures in view, not the known-threat list), and Charge from 2 cells failed silently (the list stayed open) |
| 8 | After the croc, the explore script waited 50 turns one call each in sight of a hostile glowpad 13 cells off, then walked to siege it at level 1 | - | My own script's rule: rest only with nothing hostile in view, otherwise CmdWait one turn. Fixed: fight.heal() uses CmdWaitUntilHealed when every hostile in view is rooted melee 2+ off, and falls back to CmdWait if the game won't rest (turn unchanged) |
| 9 | "New enemy joined" for a rooted glowpad 5 cells off | - | Bug in my script: fixed (rooted melee 2+ off can't join) |
| 10 | Opened on a hulking baboon at level 1; one thrown boulder did 9 | game_knowledge had max_hit 9 from an earlier character, but not "ranged" | The thrown-hit message ("hits with a small boulder (x5)") didn't match the hit pattern, so it was never learned. Fixed the pattern; marked the kind ranged |
| 5 | Talked to the Joppa people by trial (one screen at a time, re-learning the options) | research/conversations.md (mechanics, who is where, what each offers) | Not named in the summary, and I didn't list research/ before starting |

## Siwur (the restart)

| # | What happened | Note |
|---|---|---|
| 11 | Collect walked onto a canteen in Joppa; "That is not owned by you. Are you sure you want to take it?" handed the run over | Fixed: explore and collect decline owned items (Escape) and say so |
| 12 | The second world-map step north from Joppa got us lost ("You're lost!"), dropped into the salt marsh south of Red Rock | Getting lost is a chance on each world-map step; this is what the playbook's "no world-map steps: they get us lost" meant. Exploring the zone regains bearings. The route question (world map vs on foot) needs the user's call: both cost something |

### Siwur's death (turn 141435, level 1, 65 XP), all my calls

- Lost on the world map into a marsh zone with a snapjaw warlord (20 HP, five attacks) and scavengers.
- Fought by hand: two rays, a teleport out of a water-locked strip, scavengers killed one by one. Then at
  14/18 I meleed the slowed warlord: two misses (DV 11), 14 -> 7.
- My scratch kite loop treated deep water ("≈" missing from its first block list, then the wrong glyph
  set) as open: it swam us into deep water next to a croc.
- At 7-8 HP, out of reach for a moment, I didn't eat witchwood bark (a full heal; its confusion was the
  worry with enemies around) and walked north into a scavenger, which crit for 7. Dead.
- Lessons: heal at the first break in contact when HP is low (bark, despite confusion, beats dying);
  don't melee a high-DV enemy at level 1 for "the freeze window"; hand-written loops again (the confusion
  lesson: every wait/move via a vetted tool) — a scratch kite script without the tools' checks moved us
  into water and into the scavenger's reach.

## Why, in general

- The compaction summary is a lossy digest of one conversation. It names files and code, but not *which
  files I must read before acting*; the research notes, retros and conversations.md were all on disk.
- There's no project CLAUDE.md or start-of-run checklist, so nothing makes me reread them after a compact.
- Rules sit in code comments (fight.py's flying check) where the bot obeys them but I, planning by hand,
  don't see them.

## The fix for the general cause (2026-11-26)

qud-bot/CLAUDE.md now loads into every session: the reading order before a new character or the next
decision after a compact, the route (world map to Red Rock), and the planning rules that otherwise live
only in code comments. The playbook's route line no longer reads as "walk to Red Rock".
