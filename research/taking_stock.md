# Taking stock (LLM routine, not a script)

A routine check done by the LLM, from live/state.json, the run's world.json and the inventory. It's a
judgement call, so it isn't scripted. Its conclusion goes into the world file as a note about the
character, so the next check can compare.

## When

- Before going deeper (a new stratum), and after arriving in a new zone.
- After a level-up, a hand-off for low HP, or a fight that cost more than a third of max HP.
- Before resuming after a save and reload.
- Otherwise every ~1000 turns of exploring.

## Questions

1. **Body:** HP vs max, effects (bleeding, poisoned, confused, ill), hunger and thirst level, turns
   until the next hunger or thirst step (see the world note "hunger").
2. **Supplies:** hunger food servings (and what else satiates: witchwood bark does), drink (drams of fresh
   water, vinewafers), healing, light (torches), and how many turns they last at the current rate.
   Anything worth selling, and what the nearest merchant sells that we need.
3. **Way back:** the chain of exits from here to the nearest safe place (a settlement): each zone's
   stairs or edge, where we arrive in the next zone, the distance, and the world-map steps (300
   turns each). Every leg must be known: an unknown leg is a risk, said so.
4. **Threats on the way back:** known hostiles alive near any leg (avoid verdicts, ranged, unknown
   kinds), when they were last seen, and whether they move. Fast or ranged ones near the line count
   most.
5. **Threats here:** what's known alive in this zone and its verdicts, what we can't fight, and
   unexplored parts (could hold anything).
6. **Margin:** can we make it back from here with the worst plausible hit on the way (the biggest
   max_hit among the kinds around, several turns of it)? If not, go back now or rest first.
7. **World file hygiene:** creatures that died but show alive (names scrambled while confused,
   state words), stale positions, missing notes. Fix them with queued edits.
8. **Goal check:** is the current goal (level, quest) still the right one for the risk, or do we
   go back, buy, or switch areas?
9. **Town trip vs alternatives** (sequencing is the LLM's call, the user, 2026-11-24): what going back
   costs (turns, water, the risk on the way) against what it buys (food, selling loot, gear, and a
   **save**). A save matters in proportion to what we'd lose without it: turns spent since the last
   save, and luck (close calls survived, rare loot, levels). Settlements checkpoint on entry and exit;
   Save and Quit saves anywhere but isn't a fallback after death. Compare with pressing on (what's left
   to gain here, how risky it is now) and say which and why.

10. **Fight review** (the user, 2026-11-24: re-evaluate our own fights; incremental improvement):
    `python tools/fights.py --since <last review turn>`. For each flag (HP low, more taken than dealt,
    wasted actions, reloads at fight start, effects suffered, hand-offs), decide: a change to the
    routine, a world-file note, or an explicit accept. Write it in research/fight_reviews.md. Also ask
    what could have been gamed out beforehand (the dreadroot: a hazard left standing).

## Log

- 2026-11-24, turn 49529 (Red Rock stratum 2): see the world note on Ushrorooshum. Food was the issue:
  Hungry, no hunger food left except 2 witchwood bark.

## Food rule (the user, 2026-11-24)

- **Stockpile food before adventuring** (the user). Since turn 50999 cooking makes this cheap: Make Camp + "Whip up a meal" gives a free full meal (design.md); keep a snack or two in reserve for when camping is impossible (Famished blocks world-map travel: "You're too famished to travel long distances").
- Last resort when out of food: travel locally (zone by zone, no world map) in the right direction, hoping to find something edible; corpses can be eaten when Famished.
