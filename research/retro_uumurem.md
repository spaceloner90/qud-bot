# Retrospective: Uumurem (the recording; level 5 reached), 2026-11-26

Mutated Human Marauder, Roleplay, world 9b6c18ef. Third start of the recording after the compact (Yim
abandoned, Siwur died at level 1). Level 5 at turn 371190, about 6,060 turns after arriving in Joppa
(turn 365126), with no deaths, by the planned route: Joppa, the world map to Red Rock, strata 1-4, a Joppa
checkpoint at level 4, and the vermin itself as the level-5 kill.

## Timeline (game turns)

| Turn | Event |
|---|---|
| 365126-365533 | Joppa explored with fight/hunt off; Elder, Mehmet (vermin quest), Argyve (knickknack) |
| 365533 | World map: lost on the first step, dropped in Joppa's south outskirts |
| 365560 | Talking to Mehmet cleared "lost" (new fact); two clean steps north; Red Rock +50 |
| 366160-366600 | Surface, stratum 1: dreadroots, snapjaw hunter, mask; Charge from 4 cells on a centipede (+125) |
| 366663 | **Level 2**: Freezing Ray 2. Studded leather (AV 3); the two-handed iron long sword found |
| 366735-366891 | Iron dagger switch (a mistake), centipede + amoeba in a corridor: 8/21, teleport out, ray-and-retreat; the long sword one-shot the amoeba |
| 367126 | **Level 3** (a horned chameleon, ray + one swing): ST 23, Multiple Legs 2, Long Blade (Defensive Stance) |
| 367127 | Fixed the estimate that read the sword as 0.0 damage a turn |
| 367387-368478 | Stratum 2: vines found by walking towards the shots, amoebas by ray + sword, first camp meal |
| ~368190 | The run sat held for minutes (an identical plan re-sent wasn't seen as new); the user caught it |
| 368591 | **Level 4** on stratum 3 (warlord + centipede at once): Freezing Ray 3 |
| ~368950-369420 | Back up to Joppa: checkpoint, spares sold (+37 drams) |
| 370198-371114 | Stratum 3 again: vines in the dark, a young ivory, cook refused (hostiles out of sight), down to stratum 4 (stuck in tar at the stairs) |
| 371190 | **Level 5**: the defanged girshling (28 HP, level 9), waited out the ray's cooldown, ray froze it in a puddle, two sword hits |

33 hand-overs: zone explored 7, under fire 9 (6 with a direction, 3 vague), close fight 4, armour 4,
kite 4 (2 from the bad sword estimate), cook 3, upgrade 1, level 1, dazed 1. The bot fought 34 fights
itself. One stall the watcher missed (the held plan), caught by the user.

## What went well

- **The lessons held.** Every hard fight was played a turn at a time; nothing used a scratch loop; HP
  was rested to full at each break; pursuers weren't trusted to stay away. Compare Siwur, same day.
- **Ray first, then the sword.** Freezing Ray 2-3 (7-8 a ray, freezing pools around targets) plus the
  long sword (often one hit) turned amoebas, a chameleon and the girshling into near-free kills.
- **Teleport as the real last resort.** At 8/21 with a centipede in front, an amoeba behind and a
  neutral ray cat blocking the way back, it was the right call; the first try failed without a turn.
- **Hunting the shooter.** Seed vines out of sight were found by stepping towards the hit's direction,
  one step per call, and died to one swing each time.
- **Checkpoint at level 4**, cheap (known stairs, two world-map steps), as the user asked for.
- **Route fixes from the last two starts worked**: Joppa conversations from conversations.md, the world
  map to Red Rock, lost cleared by talking.

## What went wrong, and why

1. **The iron dagger switch.** The estimate rated it 2.2 a turn against the axe's 1.4; in play it missed
   six times running and did 1 damage a hit to an amoeba. The estimate's hit chance and penetration
   didn't match the fight. The long sword (picked up earlier) was the real upgrade, and I'd parked it for
   the torch, which only adds about one cell of sight. Lesson: a weapon's damage dice and penetration
   matter more than the estimate's small edge; and test the light question before deciding.
2. **The sword read as 0.0 a turn.** Off-hand torch misses counted against it, and three misses alone set
   its hit chance to 0, so the bot handed over a 3-HP bat and a chameleon as "kite". Fixed (misses
   checked against the wielded weapon; observed rate blended with the computed one).
3. **The held plan.** I re-sent a plan identical to the previous one; step.py compared plan text only,
   so the run stayed in the remote stage. Fixed (plan.json's mtime counts), and the watcher now reports
   HELD. My process error as much as the bot's.
4. **Small friction stops**: vague "shooting at you or the shale" (now ignored twice in 100 turns),
   cook refused for hostiles out of sight and retried at once (now backs off), the camp walk's 30-step
   cap on a winding path (now 80), Charge from 2 cells ("no clear line", it needs 3+).
5. **Hand-played swings aren't recorded** in the weapon stats (no target in the remote stage), which is
   part of why the sword's record was all misses.

## Changes made during the run (all vetted, 0 failing of 430)

threat.py (weapon misses, blended hit chance, thrown hits learned as ranged), explore.py (vague fire,
owned items, interrupt list for the mod), cook.py (walk cap, refusal back-off), collect.py (nothing to
take, owned items), fight.py (silent-attack guard, heal with rest when only rooted hostiles), step.py
(plan mtime, PASS -> WAIT off the map), watch_handover.py (HELD, stalled popups), mod v0.26 (autoexplore
interrupt for prey kinds; no `autoact_interrupt` line was logged this run, so it's still unverified live).

## The user's review (2026-11-26), and what it changes

- A very lucky world: no impossibly lethal enemy, early gear drops. The cider and wine weeps on a peaceful
  surface could have filled every container and solved money at the start; I never evaluated them.
- Switching to the two-handed sword mid-fight was right; staying in the dark after wasn't. A viewer sees
  a black screen. It also made the vines' shots hard to place. Torch for exploring, sword for the fight.
- Published: https://www.youtube.com/watch?v=Fn8r-WRl4kI (runs/9b6c18ef-.../recording.json).
- The dagger: unclear if it was worse or just unlucky. Six misses at a ~50% chance is ~1.6%. But the
  estimate doesn't model skill to-hit (Axe Proficiency +2), and weapon records are shared game knowledge
  by name, pooled across five characters, so the axe's 95% came from others' swings.
- Skipped in Joppa what past runs did: a ranged weapon, the free camp meal while Hungry. A bow and
  arrows from the first fight went unconsidered. Sprint was never used.
- Generic lessons (the town one reworded at the user's request: judge the shop stock against the character, don't replay past runs' purchases): research/lessons.md "How to find the answers"; CLAUDE.md "At every decision point".
- Test scenarios: tests/fixtures/cases (7) and tests/unit_checks.py (9), run by tools/replay_tests.py;
  two are marked known bugs (Charge from 2 cells, stuck in tar read as zone done).

Code changes this suggested, made the same day (design.md, "Fixes from Uumurem's retro"): weapon records per character and per
item id (the mod can export item ids as it does creatures); the game's own to-hit for the equipped weapon
instead of modelling it; explore evaluates each new liquid, feature and item kind on first sight as it
does creatures; the gear check reviews the whole pack, missile weapons included.

## Still to do

- Restart the game for mod v0.27 (item ids) and check `equipped_ids` appears; verify the autoexplore
  prey interrupt (`autoact_interrupt` in log.jsonl); evaluate honey and oil when next seen.

- Fix fight.py's Charge from 2 cells (only from 3+).
- Record hand-played swings in weapon stats (observe with the adjacent target in the remote stage).
- Verify the autoexplore prey interrupt in a run (check log.jsonl for `autoact_interrupt`).
- The girshling corpse for Mehmet's quest was left on stratum 4 (+750 at the turn-in).
- As a recording: 33 hand-overs in about 6,000 turns, most short. Ask the user whether the pace works.
