# Unvetted changes: watch these in the next runs

Passed the offline checks (tools/vet_fight.py, tools/replay_tests.py) but not yet seen working in a live
run. The user, 2026-11-26: "as they are unvetted we should keep monitoring and adjust as we go". Move an
entry to "Seen working" (with the run and turn) or fix it when a run shows otherwise. Past wins aren't
re-validated here; this is only what hasn't been seen yet.

| Change (2026-11-26) | What to watch for |
|---|---|
| To-hit from the game's rolls + proficiency (threat.to_hit_bonus) | estimates close to what fights do; no hand-over for easy kills |
| Weapon records per character (not shared) | a new character starts with empty records; estimates still sane |
| Hand-played swings recorded (remote.observe_swings) | rolls/roll_n grow during my own fights |
| Charge only from 3-4 cells | Charge fires and lands; no "no clear line" from 2 |
| Stuck in a pool: struggle free (explore.free_direction) | gets out in a few moves; never 30 moves |
| Missile weapon fills an empty slot (gear check) | one hand-over per missile weapon, with the ammo listed |
| Cook refusal backs off (cook.refused_here) | no repeated refusals in place; still cooks before Famished |
| Vague "shooting at you or the X" ignored twice in 100 turns | a real shooter still hands over (hit or near miss) |
| Camp walk up to 80 steps | reaches a fire spot round walls |
| Fight heal(): rest when only rooted hostiles are 2+ away | rests in one call; falls back to waits when refused |
| Silent-attack guard (2 silent swings at prey: skip it) | doesn't fire on normal misses |
| World-neutral feature kinds (features.feature_kind, re-keyed game knowledge) | a shrine or named place in a new world lists as "shrine" / "named place", not its full name; stained and frozen plants don't list as new |
| Hand-over digest (tools/brief.py) | each section matches the game (cooldowns against the abilities list, XP against the sidebar); nothing a hand-over needed was missing |
| Fight commitment to an out-of-view target (fight.engage, 2026-11-27) | no A-B-A-B walks between rooted targets; it never walks past a mobile or shooting hostile in view |
| Pacing hand-over (8 approach steps on 2 cells) | hands over in a real loop; never fires while a fight is making progress |
| Sighting stops restart autoexplore (sighting_retries) | a zone full of dragonflies gets explored to the end; a real blockage still hands over |
| Unreachable loot kept per zone; swim prompt gives the item up | no walk back to the same loot after a plan change; no stall at the swim prompt |
| Auto-loot opens containers (collect.chest_step) | chests opened and emptied in the sweep; no stray keys in menus; empty ones closed with n |
| Walk: stops before deep water; rooted dangers 2+ off don't stop it | no swimming on walks; walks past pools of glowpads |
| Swim for loot when safe (explore.swim_safe, collect deep list) | swims only in a quiet zone at full HP; deep items fetched later, named in the zone report |
| Torch relight (scripts/light.py) | a fresh torch lit after a swim; no stray keys in the inventory |
| Chest menu after the last item (no picking up the chest) | containers emptied, never taken themselves |
| Unreachable give-ups expire after 300 turns | retried later, without a walk loop |
| Mobile avoid kinds: zone-wide danger (explore.mobile_dangers) | stops in a zone with a fresh mobile avoid sighting; not for routine kinds or accept_kinds |
| Stale sightings dropped after 500 turns (known_threats) | camping and swimming not blocked by old records; rooted shooters still remembered |
| Pacing failsafe in step.py | hands over a real loop; never during a normal walk or fight |
| Script exception holds the run instead of stopping | a broken script hands over and the run stays live |
| profile.py expands every skill group | the full skills list, whatever state the page was left in |
| Mod v0.28: features nearest first, cap 1200 | deep water round us always listed; snapshot size still fine |
| --say / --think on send, walk, next_zone | the line plays before the action; the tool's own arguments still parse |

## Seen working

- **Mod v0.26: autoexplore prey interrupt (`live/interrupt.txt`)** — Siwur (`1f19697d`), turn ~141094: hunted and killed both wet glowfish in `JoppaWorld.11.22.2.2.10` without manual intervention.
- **Mod v0.27: `inventory_ids` / `equipped_ids`** — Siwur (`1f19697d`), turn 141071 onward: present in `live/state.json`.
- **New liquids and features listed (`features.py`)** — Siwur (`1f19697d`), turn 141899: `[new to evaluate: shrine to nathritafa, the cerulean bane of namritara ...]` appeared on hand-over and `tools/world.py evaluate feature` queued cleanly. (2026-11-26, Claude: the listing worked, but it filed that world-specific name as a shared kind; fixed, see the table above.)
- **Plan mtime counts as a new plan (`step.py`)** — Siwur (`1f19697d`), turns 141071 & 141899: rewriting `brain/plan.json` after popup/hand-over resumed `explore` cleanly.
