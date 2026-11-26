# Unvetted changes: watch these in the next runs

Passed the offline checks (tools/vet_fight.py, tools/replay_tests.py) but not yet seen working in a live
run. The user, 2026-11-26: "as they are unvetted we should keep monitoring and adjust as we go". Move an
entry to "Seen working" (with the run and turn) or fix it when a run shows otherwise. Past wins aren't
re-validated here; this is only what hasn't been seen yet.

| Change (2026-11-26) | What to watch for |
|---|---|
| Mod v0.26: autoexplore prey interrupt (live/interrupt.txt) | `autoact_interrupt` lines in live/log.jsonl; no repeated interrupts for one creature |
| Mod v0.27: `inventory_ids` / `equipped_ids` | present in live/state.json after a restart; weapon records keyed `name#id` |
| To-hit from the game's rolls + proficiency (threat.to_hit_bonus) | estimates close to what fights do; no hand-over for easy kills |
| Weapon records per character (not shared) | a new character starts with empty records; estimates still sane |
| Hand-played swings recorded (remote.observe_swings) | rolls/roll_n grow during my own fights |
| Charge only from 3-4 cells | Charge fires and lands; no "no clear line" from 2 |
| Stuck in a pool: struggle free (explore.free_direction) | gets out in a few moves; never 30 moves |
| Missile weapon fills an empty slot (gear check) | one hand-over per missile weapon, with the ammo listed |
| New liquids and features listed (features.py) | "[new to evaluate: ...]" on hand-overs; not noisy; verdicts stick |
| Cook refusal backs off (cook.refused_here) | no repeated refusals in place; still cooks before Famished |
| Vague "shooting at you or the X" ignored twice in 100 turns | a real shooter still hands over (hit or near miss) |
| Camp walk up to 80 steps | reaches a fire spot round walls |
| Plan mtime counts as a new plan; watcher HELD | an identical re-sent plan is picked up |
| Fight heal(): rest when only rooted hostiles are 2+ away | rests in one call; falls back to waits when refused |
| Silent-attack guard (2 silent swings at prey: skip it) | doesn't fire on normal misses |

## Seen working

(none yet)
