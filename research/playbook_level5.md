# Playbook: a new character to level 5 (draft from run 1, 2026-11-24)

> **Refined (the user, later that day): "the things we know, we know."** Use what's known about fixed
> places like Joppa (people, wares, quests); still explore it fully for XP and loot; just don't narrate
> references to earlier playthroughs.
>
> **Not a script (the user, 2026-11-24, after run 2's death).** Each character plays as if new: explore
> the starting region as usual, talk to people, decide from what is seen in this world. Don't assume
> things happen as they did in an earlier run (even where the game isn't randomized, e.g. Joppa), and
> don't mention earlier runs in narration. This file is background: what tends to be worth doing, and
> what cost time. Danger is judged live from the creature's stats against ours (fight.py), never from an
> earlier character's verdict.


The user's goal: a second character with mostly the same setup, to level 5 as fast as possible, along
run 1's trajectory, repeated until the first five levels go smoothly: few thinking pauses, and proper
narration while thinking. That run is meant for the project's first YouTube recording.

Built from **one** run, so these are milestones with options, not a fixed script. Each run should
update this file: what was the same, what the seed changed, where time went.

## What to observe at creation

Run 1: Ushrorooshum, Mutated Human Marauder, Roleplay mode (checkpoints on town entry/exit).
At level 2: ST 22, AG 18, TO 18, IN 14, WI 16, EG 16; HP 21. Mutations: Freezing Ray, Multiple Legs,
Teleportation, Amphibious (defect: pours our water over us, so water is a core resource). Skills from
the calling: Axe Proficiency, Dismember, Butchery, Charge, Make Camp.

Record for run 2 (to learn what's random): name, attributes, starting HP, starting equipment and drams,
mutation choices and ranks, skills, where we start in Joppa, and whether Joppa's people stand in the
same places (run 1: Elder Irudad (38,3), Mehmet (42,19), Argyve (6,19)).

## XP budget to level 5 (1975 XP)

Run 1's sources up to level 5: Red Rock arrival +50; kills (jilted lover 25, vine 25, cave spider 50,
giant centipede 125, croc 75, amoeba 25-ish, girshling 90, snapjaws 10); the vermin quest steps (+100
find, +90 kill, +100 corpse). **Not used before level 5 in run 1: the turn-in, +750**, plus whatever
Argyve's knickknack pays. With the turn-in taken as soon as the corpse is in the pack, level 5 should come
on the walk back to Joppa or at the turn-in itself, well before run 1's turn 52560 (6600 turns in).

## Milestones (order flexible)

1. **Joppa, quests only.** Talk to Mehmet (What's Eating the Watervine?) and Argyve (Fetch a Knickknack);
   the Elder pays for the vermin. Don't explore Joppa (run 1: 260 turns for 0 XP). Check food and water;
   refill skins (Amphibious). Leave by the north edge (the exit is a checkpoint).
2. **Red Rock** (run 1: 2 world-map steps north of Joppa, (11,20); +50 on arrival). Seed may move it; the
   quest text says where.
3. **Strata 1-2** (levels 2-3 in run 1): jilted lovers, seed-spitting vine (ranged: Freezing Ray from
   range, not melee), cave spiders, giant centipedes. Collect loot (books from shelves sell well).
4. **Gear decision.** Run 1 went back to Joppa at level 4 for chain mail, an axe and a musket (books
   $104, a bronze ingot $100). Options: go back as soon as there's loot worth ~$150, or push to the vermin
   first and do one town trip for turn-in + shopping. Decide by HP trouble: the giant amoeba nearly killed
   us twice with AV 2. **Fill every armour slot** when shopping (run 1 left five empty).
4b. **Blocked on the way down?** (run 2, Shwyragaun: the Snapjaw King on stratum 3, hopeless by the
   estimate.) Red Rock's strata differ by world, so nothing about their layout carries over. Don't retry:
   hunt the salt-marsh zones in the tiles next to Joppa, zone by zone on foot (crocs 75 XP, glowpads 25,
   glowfish and dragonflies as prey). That took run 2 from level 3 to 5 in ~1600 turns. Never survey the
   world map for sites (low chance, a dram of water and 300 turns a step).
5. **Strata 3-4: the vermin** (run 1: web-toed defanged girshlings on stratum 4, the slime field). Two at
   once took us from 27 to 4. Fight them one at a time, musket first.
6. **Back to Joppa: turn in at once** (+750), sell, shop, eat. Level 5 here at the latest.

## Rules carried over (from reviews and the user)

- Fights: hold a position that works, let them come; regenerate standing still; pursuers cross zones;
  escape step by step in one feasible direction; Teleport only when death is otherwise near-certain (aim
  15-20 cells). Kill dreadroots on sight (ray or axe, no ammo). Shoot only what's dangerous; reload in
  downtime.
- Death vs resources: near a checkpoint, dying can be cheaper than burning every salve.
- Food: stockpile before leaving town; cook free meals at Famished (Make Camp) when safe.
- Loot everything while weight allows; examine before selling.
- Stop at the user's goal (level 5), once the encounter around us is over.

## Smoothness (what the recording needs)

Where run 1 lost wall-clock time, and what's already fixed or still to do:
- Menus one key per round trip: fixed with tools/menu.py (item, trade). Trade not yet tested live.
- Conversations by hand: still manual (one key per screen, read each). Candidate for a talk macro.
- World-map travel: one call per step; popups (ruins, lost) need reading. A travel macro would help.
- Thinking pauses: narrate each decision as it's made (narrate skill + the 25 s reminder hook).
- Stale plan after a reload: fixed (the brain holds the plan when the turn goes backwards).
- New run starts knowing every creature kind run 1 learned (brain/game_knowledge.json).

## Run 2 (claudio2, game 19c1443b, started 2026-11-24)

Creation, compared with run 1: identical. ST 22, AG 18, TO 18, IN 14, WI 16, EG 16; HP 18 at level 1;
Freezing Ray 1, Multiple Legs 1, Teleportation 1, Amphibious (D); furs (AV 2), bronze battle axe (1d2),
lit torch; 3 waterskins (32 drams), 10 torches, bear jerky x10, witchwood bark x3. What differed: the
name (the user's), the calendar (start turn 109525 vs 45925) and the start cell (Joppa 37,22).
Auto-start fired on arrival; a key press stopped it once, F1 restarted it.

- **Hunt harmless neutral critters for XP** (the user, 2026-11-25: we did it with bats, then forgot). Explore's
  `hunt` is now on by default; turn it off only in towns. Mark a kind `prey` when it is small, low level and
  unimportant (glowfish, giant dragonflies, glowpads in the salt marsh); the fight gate still checks each one.

## From the two retries (Uubas, Oshwoshwuur; 2026-11-25)

The route that worked twice (Shwyragaun, Oshwoshwuur): Joppa (quests, explore) -> Red Rock by the world map (up, north, down)
-> strata 1-3 on foot (no world-map steps between them: they get us lost) -> good loot (steel hand axe, studded leather, caps) -> an
impasse on stratum 3 (a Snapjaw King, faster or far stronger) -> Joppa for a checkpoint at level 4, Argyve's
two knickknack quests (+225; a broken artifact is accepted), sell the spare gear (64 drams), a musket ->
the marsh zones between Red Rock and Joppa for the rest.
- Hard fights are played by the LLM at hand-overs: wait for Freezing Ray and Charge before engaging; use
  doorways and corridors so one enemy at a time can reach; the ray hits everything in its line.
- Teleport with AIM sets the centre, but the uncertainty radius still applies (landed 12 cells off the stairs once, and off target with Siwur): aim so anywhere nearby is safe.
- Autoexplore walks into a known King's area: after one sighting, leave that level.
- Checkpoint (Joppa) after every level or two when it's cheap.
- Hunger: cook ~450 turns after Hungry (Famished came ~740 after); walk to open ground for the camp.

## Uumurem (the recording, 2026-11-26): level 5 in ~6,060 turns, no deaths

The full route worked: Joppa explore + Elder, Mehmet, Argyve -> world map to Red Rock (lost once: talk to
any villager to clear it) -> strata 1-3 -> Joppa checkpoint at level 4 (sell the spares to Tam) ->
back down -> stratum 4, the defanged girshling as the level-5 kill (left its corpse; +750 at the turn-in).
- Take the two-handed iron long sword when it shows up, even underground: the torch adds about one cell
  of sight; the sword one-shots most of strata 1-4. Ray first, sword second.
- Freezing Ray 2 at level 2 and 3 at level 4; Long Blade at level 3 (Defensive Stance); Dueling Stance
  needs Intelligence 17.
- Vines out of view: step towards the hit's direction one cell per call; they die to one swing.
- A hard fight goes on only at full HP with the ray ready; otherwise back off (kiting slower enemies) and
  come back. Teleport only when cornered and losing.
