# Retrospective: Shwyragaun (run 2's character; level 5 reached), 2026-11-25

Mutated Human Marauder, Roleplay. World bb75178b. The user's verdict: a good roll all round, not as
blessed as run 1; successful (level 5), but not a recording, because of the churn. Keep trying.

## Timeline (game turns)

| Turn | Event |
|---|---|
| 431126 | Start in Joppa; explored it fully (quests, loot) |
| ~432100-433560 | Red Rock surface, strata 1-3: dreadroots, lovers, vines, spiders; good loot |
| 433489 | Level 3 (Red Rock) |
| 433560 | Stratum 3: met the Snapjaw King (112 HP) next to us; teleported away, town trip |
| 434420 | Joppa: Argyve's quests, books read and sold, musket + 52 slugs, camp meal |
| 434748 | Lost in the salt marsh on the way back; croc; regained bearings |
| 435331-435360 | Stratum 3 again: the King in the arrival room; ran out with her pack behind (unhurt) |
| 435401-438626 | World-map survey of the 8 tiles around Joppa: nothing (3200 turns, 11 drams) |
| 438626-440250 | Hunting inside the marsh zones near Joppa: crocs, glowpads, glowfish, dragonflies |
| 438961 | Level 4 |
| 440250 | **Level 5** (glowpad kill, marsh south-west of Joppa) |

About 9100 game turns from start to level 5. In the log since the start: 45 hand-overs to the LLM, 5
run stops (no keys, cook failure twice, a key press, a brain crash I caused).

## What went well

- **The roll and the loot.** An early iron long sword, books worth 96 drams, two artifacts (wasted, see
  below), food and water enough; Freezing Ray carried every fight that mattered.
- **Dynamic danger reading.** The threat estimate said the King was hopeless (about 52 turns for us to
  kill her against 3 for her to kill us) and that crocs and glowpads were safe. Both held.
- **The escape.** Beelining to the stairs, then single steps without walk stops, outran the King and six
  snapjaws (move 120 vs 100) with no damage.
- **Marsh hunting, once set up.** Zone by zone inside the tiles next to Joppa, with neutral prey marked
  and hunted, took us from level 3 to 5 in about 1600 turns, mostly unattended between hand-overs.
- **Levelling decisions** (Acrobatics/Spry, Freezing Ray 3, Multiple Legs 3) fit what hurt us: bites and
  being outpaced.

## The churn (why this can't be the recording)

Most of the wall-clock went to fixing the bot mid-run. By kind:

**Stuck without anyone noticing** (the worst for a recording):
- A WALK sent at the moment plan.json changed was swallowed (the remote stage recounted the inbox);
  walk.py waited 5 minutes. Fixed: live/inbox_played.json.
- The bot "held its spot" for prey, which never comes; then held for glowpads that never leave their pool;
  then my fix flip-flopped (our own steps counted as them closing in). Three rounds of fixes.
- The long-fight timer counted a chain of kills as one fight.
- CmdAttack at a flying dragonfly, 40 times, ignored by the game, caught by nothing. Fixed: step.py's
  no-progress failsafe (6 identical answers with nothing changing hands over); flying prey skipped.
- Stops used to end the run, so both sides waited. Fixed: stops hold in the remote stage and bump
  live/handover.json; tools/watch_handover.py wakes the LLM (also on a stopped run).

**My own mistakes:**
- Gave both artifacts away unidentified while the user was asking about identifying them.
- Called the Amphibious water-pouring "unexplained" (known since run 1). Fixed: tools/known.py and
  game_knowledge "messages"; the look-up rule in memory.
- Claimed Red Rock's layout matched run 1's from a union map (it doesn't; the strata vary by world), and
  planned a sneak to stairs that don't exist in this world.
- Walked the world map to "survey" for dungeons when the user meant hunting inside the marsh zones.
- Asked the user how to spend points (my call).
- A half-finished two-step edit of step.py crashed the brain mid-run. Edit in one go.

**Slow, but working:** menus at one key per round trip (now bursts of 3 with a check), single-step manual
moves (now WALK, ~0.35 s a step).

## Lessons for the next character

1. Same opening: explore Joppa fully, quests, loot; Red Rock strata 1-2 for levels 2-3.
2. **Red Rock's strata differ by world**: no stairs positions carry over. If a hopeless creature (a
   King, a hero) stands on the way down, don't retry: go hunt the marsh zones next to Joppa at once.
3. **The marsh is a real levelling route**: crocs (75), glowpads (25), glowfish and dragonflies (prey).
   One at a time for stationary groups; leave prey that needs a swim or is flying.
4. Identify artifacts before giving or selling (examine, a tinker, or Gadget Inspector).
5. Budget water before spending it in trade (Amphibious pours a dram per world-map step).
6. Before recording: restart the game for mod v0.25 (creature ids, AIM), and watch one full session for
   new no-progress or hand-over gaps.

## Built late this run, not yet seen live

- Creature ids (mod v0.25) and id-keyed records; deaths by id.
- Breaking off autoexplore for prey in view; sweeping back for prey seen but not killed.
- Hunger delay (900 turns into Hungry before cooking); healing in place unless an enemy is adjacent.
- The no-progress failsafe and the watcher's stopped-run wake-up.
- tools/kill.py and tools/frontier.py (careful exploring).
