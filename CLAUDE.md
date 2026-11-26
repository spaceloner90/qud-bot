# Caves of Qud bot: read before playing

Loaded into every session, including after a compact. The compact summary is a lossy digest: it names
files but not which to reread, and that dropped the route, the Joppa conversations and the flying-prey
rule on 2026-11-26 (research/gaps_after_compact.md). Rules that sit only in code comments are obeyed by
the bot but not seen by me when I plan by hand, so the ones that matter for my own choices are here too.

## Standing lessons (every rule the user has given, loaded with this file)

@research/lessons.md

## Game facts and how-tos (recovered from my own past replies, loaded with this file)

@research/game_facts.md

## Before a new character (or after a compact, before the next decision)

Read, in this order:
1. research/playbook_level5.md: the route and what tends to be worth doing.
2. The latest retros (research/retro_*.md) and research/gaps_after_compact.md.
3. research/conversations.md before talking to anyone (mechanics, who is where in Joppa, what they offer).
4. research/design.md's section for whatever part of the bot I'm about to touch.
Then check a tool's own `--help`/docstring before calling it; never call it from memory or the summary.

## The route to level 5 (what worked)

- Joppa: explore it with fight and hunt off; Elder Irudad -> Mehmet (vermin quest) -> Argyve (knickknack;
  the fractured microchip is not an artifact). Leave the town args behind when leaving.
- **To Red Rock by the world map**: `CMD CmdMoveU` (needs no hostiles nearby), step north to Red Rock,
  `CMD CmdMoveD` (+50 XP on arrival). Not on foot zone by zone through the marsh. "On foot" in the playbook
  means moving between Red Rock's strata, not getting there.
- Red Rock strata 1-3; at an impasse (a Snapjaw King, a baboon troop) go back to Joppa for a checkpoint
  and hunt the marsh zones next to Joppa, zone by zone.

## Rules for my own planning

- Giant dragonflies that are `flying` can't be hit from the ground: never plan around hunting them.
- Glowpads (rooted, 50 HP) are not worth sieging at level 1; fine later.
- Hulking baboons throw boulders (9 damage in one hit at level 1): ranged, a level-5 creature; don't
  open on one at level 1.
- "There are hostiles nearby!" blocks the world map: cross a zone edge first, then go up.
- Hard or chancy fights are played by me at hand-overs, by judgment (cooldowns first, cover, retreat
  while faster); never scripted.

## Retrospectives (after a run, never during a live run)

1. Timeline from the log, what went well, what failed and why; check each failure against lessons.md
   and game_facts.md (a regression or new?). Write research/retro_<name>.md.
2. Every lesson the user gives goes into lessons.md; every new game fact into game_facts.md.
3. **Test cases, incrementally (the user, 2026-11-26):** for each bug or bad bot decision found, freeze
   the state from live/log.jsonl (that turn's snapshot, the plan stage, args and memory) into
   `tests/fixtures/cases/` with a rule for the expected answer, and run them with
   `tools/replay_tests.py` (built 2026-11-26; also runs tests/unit_checks.py for logic that needs no
   whole state). Add cases only as needed, not a big sweep. Run it with the vet after any fix.
4. Fix, vet (`tools/vet_fight.py` + the replay cases), then document.

## At every decision point (hand-over, level-up, take stock, town visit)

Run these before deciding (lessons.md, "How to find the answers"): anything new in view (creatures,
liquids, features, items) evaluated? (hand-overs end with "[new to evaluate: ...]"; record each with
`python tools/world.py evaluate liquid|feature "<kind>" "<note>"`) whole inventory reviewed for use now? whole abilities list
reviewed? in town: every shop's stock read and judged against the character (combat options, stats,
survival), and the town's free resources used (meal, rest, refills)? if I'm driving by hand, have I done
the bot's background checks (food, status, gear)? does the screen stay readable for a viewer? (Past
runs' logs are for when I'm stuck or diagnosing, not a checklist.)

## When I play a fight myself (memory qud-fight-lessons-maggatum, design.md; regressed with Siwur)

- **One action per call, then re-read the board** (HP, every hostile's position and effects, cooldowns)
  until I'm comfortable handing back to the scripts. No `for` loops of attacks or moves, no scratch
  kite/flee scripts, no GOTO/WALK mid-fight: Siwur's death came from a 5-attack loop and a scratch kite
  loop. If a repeated move is worth automating, it becomes a vetted tool first.
- **Pursuers cross zone edges.** Out of sight is not safe and an edge is not a rest spot. Flee in one
  clear direction that avoids enemies, or fight on my terms; remember who is chasing.
- **Terrain from the snapshot, not glyphs.** Glyphs don't say what a cell is (design.md: `≈` was
  furniture in a hut). Deep water: -50% move and +500 action cost, and crocs live there; never path or
  flee through it. Read the snapshot's `features` before choosing a cell.
- **Heal before the next fight, not in it.** Every break in contact while hurt is the time to rest to full
  (out of reach, nothing following). Witchwood bark heals fully but confuses, and confusion mid-combat is
  deadly: it's for when no enemy is near, not a mid-fight button. Don't hand back to explore below half
  HP with hostiles in view.
- **Ray first, melee second**, and engage at full HP with ray and Charge ready; a level-1 character
  misses half its swings against DV 11.
- After any fight-logic change: `python tools/vet_fight.py` (0 failing) before the bot runs it.
- After giving the bot a plan: `python tools/watch_handover.py` in the background (no `--idle` without a
  value), so a stop always wakes me.
