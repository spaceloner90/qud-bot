# Goals

We go step by step: each goal is small, measurable from the snapshot, and set by the user. A goal is met only when the log shows it.

## Done: survive to level 2 (set and reached 2026-11-24)

- **Done when:** `player.level` reaches 2 (220 XP from level 1, as the sidebar shows) without dying.
- **Character:** Ushrorooshum, Mutated Human Marauder, Roleplay mode, starting in Joppa at turn 45925.
- **Measured in:** game turns from turn 45925 (my default until the user says otherwise). Wall-clock time and LLM calls get recorded too.
- **Death:** surviving is part of the goal, so a death means the attempt failed, even though Roleplay mode would let us continue.

### Attempt log

- **2026-11-24, explore Joppa** (turns 45925 → 46186, 260 turns, XP 0/220). The game's autoexplore covered the whole village and stopped at "There doesn't seem to be anywhere else to explore." Raw Space closed every `[press space]` popup.
  - People: Elder Irudad, Warden Yrame, Mehmet, Ctesiphus, Tam (dromad merchant), watervine farmers. None hostile. We haven't talked to anyone.
  - Quests: none. Autoexplore doesn't talk to anyone, so we didn't expect any.
  - Free items: autoexplore picked up a fractured microchip and 2 bent metal sheets from the ground, with no reaction from anyone. Two chests are unopened, and four signs are unread.
  - Lore: the shrine to Resheph added a Sultan Histories journal entry.
  - Unexplained: "You pour fresh water from your waterskin over yourself" happened without us asking. (Later explained: the Amphibious defect; see research/character.md.)
  - Assessment: exploring a peaceful village in full cost 260 turns for 0 XP. Whether autoexplore's route is efficient is unmeasured; `live/trace.jsonl` will record every step from the next run (ask_during_autoact on).

- **2026-11-24, talk in Joppa** (after reloading to the start; turns 45925 → 46217). A staged plan (explore, then remote) re-explored Joppa in 242 turns, then I drove the conversations by hand. **Two quests**: *What's Eating the Watervine?* (Mehmet: kill the vermin at Red Rock, 2 parasangs north, bring back a corpse; the Elder pays) and *Fetch Argyve a Knickknack* (an artifact from around Joppa). Details in `research/conversations.md`. XP still 0/220. Lesson: a restart in Roleplay mode reloads the last checkpoint, so progress since then (here, all of it) is lost. Town entries and exits are the save points to use.

- **2026-11-24, leave Joppa north** (turns 46217 → 46237). `CmdMoveFarN` to the edge, then one step: arrived in "outskirts, Joppa" (same parasang, next zone). The world map is a separate "Move up". Seen: a walled structure with a brinestalk gate, water, and a non-hostile giant dragonfly. Next: decide between walking zone by zone (about 6 zones) or going up to the world map (2 moves).

- **2026-11-24, to Red Rock on the world map** (turns 46237 → 46837). After restarting into the Joppa checkpoint (both quests kept), `CmdMoveU` went up to the world map, and two `CmdMoveN` steps went through salt marsh to **Red Rock at (11,20)**, 300 turns per step. Next: `CmdMoveD` to enter it; expect the vermin, so likely the first fight.

- **2026-11-24, into Red Rock** (turn 46837). `CmdMoveD` entered Red Rock's middle zone at night; arriving completed the quest step: **XP 50/220**. Ate bear jerky (status was Hungry). The torch lights about 4 cells. No creature in view yet.

- **2026-11-24, explore Red Rock's middle zone** (turns 46838 → 47183). Explore with hand-off, at night: no creatures, zone explored "from here" (rock formations with unreachable insides). Found a `>` at (67,11). The vermin weren't on the surface here; next lead is the way down (the Elder said *cave* vermin).

- **2026-11-24, down into Red Rock** (turn 47237). Walked to the stairs (they were at 66,11), went down to "Red Rock, 1 stratum deep". In view: a non-hostile bat, another way down, water. No vermin yet. Hungry again.

- **2026-11-24, first fights, Red Rock stratum 1** (turns 47242 → 47307). Ate 2 servings (one left us Hungry). Explore stopped twice for a **jilted lover** (hostile thorny plant, Look: Average). Killed both by hand: the first in one blow (no damage taken), the second in three (took 8 damage, HP 18 → 10). **XP 100/220.**

- **2026-11-24, clearing Red Rock stratum 1** (turns 47307 → 47437). Rested 10→18 in 45 turns. Explore stopped for a **seed-spitting vine** (ranged plant, Average: one blow, +25), a **cave spider** (mobile, skittish, 2 bites a turn; five exchanges, +50, not the quest's vermin) and a third jilted lover (it grabs; +25). The game won't rest with a hostile in view: step out of sight first. Level explored "from here". **XP 200/220**, HP 15/18. The vermin are still unfound: next is the second way down on this level (65,11), or Red Rock's other zones.

- **2026-11-24, level 2** (turns 47459 → 47557). Rested to 18, used the game's "walk to the nearest stairway down" to reach stratum 2, and explore stopped for a **wet giant centipede** (mobile, bites, Look: Average). Three exchanges (took 6 damage): **+125 XP, level 2**. XP 325/505 next. Level-up: +3 max HP (21), 66 skill points, 1 mutation point (unspent).

### Result

**Reached level 2 at turn 47557 without dying**, 1632 game turns after the start (turn 45925) on this timeline. About 300 of those were redone after a checkpoint reload; the 600 for two world-map steps were the biggest single cost. XP came from quest progress (50) and kills: jilted lover 25 each, seed-spitting vine 25, cave spider 50, giant centipede 125. The quest's vermin is still unfound. All fights were driven by the LLM by hand (Look, close in, attack, Look between blows, rest out of sight); no fight script exists yet.

- **2026-11-24 afternoon, replay to level 2 with the fight routine** (turns 46237 → 47540, from the world-map checkpoint). **The world came back identical**: Red Rock's surface, stairs, creatures and their spots were the same as before the reload, so this run's world file is reliable across reloads. The fight routine killed two jilted lovers on its own. The seed-spitting vine (rated Average) shot us from 18 to 8, then autoexplore walked back into its range and it shot us down to 6, firing from out of view; I fled and rested far away. We marked it avoid, added danger zones, safe rest, an under-fire raise and auto-eat, and went down. Auto-eat ate 2 jerky (Hungry → Sated). On stratum 2 the routine raised me at 8/18 against the giant centipede, which follows if you step back. Witchwood bark healed fully (and confused), and one blow killed it: **level 2 at turn 47540**, XP 225/505.

- **2026-11-24, back to Red Rock stratum 2 with abilities** (turns 48540 → 49229). Save and Quit confirmed to save anywhere (reloaded in the salt marsh). In the marsh the routine killed a croc on its own (+75); in the caves two cave spiders (+50 each), the second with an automatic Freezing Ray, which **freezes** (the frozen spider didn't act). Vinewafers turned out to be hydration food; auto-eat now waits for Famished. A **giant amoeba** rated Average took us 21 → 5 in three turns (4 + 7 in one turn); marked avoid; escaped by running straight for the stairs: it fell behind at once. XP 475/505, HP 15/21 at the stairs up.

- **2026-11-24, level 3** (turns 49229 → 49507). Rested at the stairs, went back to hunt the amoeba with hit-and-run; it had moved off and wasn't found (stale positions now stop blocking autoexplore). Exploring on, the routine fought a third cave spider with an automatic Freezing Ray; its bite caused **bleeding**, which raised me at 10/21 (unexpected message). Ate witchwood bark (full heal, confused), finished it by hand going by position: **level 3** at turn 49507. Unspent: 132 SP, 2 MP, 1 attribute point. Vermin still unfound.

- **2026-11-24, level 4** (turns 49529 → 50282). Took stock first (food was the issue). Stratum 2 explored to the end (bats as prey, books from shelves, the quest Visit Duramur), then a short look at stratum 3 (slime patch): three giant centipedes (+125 each), snapjaw scavengers (Easy, swarmers, +10), dreadroots (fear aura, no XP), jilted lovers, a young ivory (hidden trap). Fled one centipede at 8/25 step by step (it kept 2 behind, then lost us). A second **giant amoeba** nearly killed us: still terrified from eating a dreadroot tuber, a step away became a step into it, and one exchange did 21 (crit 6 that dazed, 8, 7): **Teleport** at HP 4 got us out (landed 25 cells away). Now explore waits out bad effects. Back on stratum 1 the seed-spitting vine died to one Freezing Ray from 4 cells (+25), and a cave spider finished by the ray gave **level 4 at turn 50282** (+2 HP to 27, +70 SP to 210, +1 MP). XP 1105/1975. Famished, no food but 2 bark and a lover's blossom (tinkering ingredient). Vermin still unfound (stratum 3 has a way down at 24,14).

- **2026-11-24, level 5** (turns 50282 → 52560). Joppa: sold 3 books ($104.65) and the bronze ingot ($100), bought chain mail (AV 3), a sturdy steel battle axe (1d3+1) and a musket (1d8) with 47 slugs; bought Cooking and Gathering + Harvestry (free campfire meals). Back at Red Rock: the musket one-shot a giant amoeba (22) and vines; stratum 3 fully explored and its loot collected (leather cap: AV 4). Stratum 4 (slime field): found the vermin, web-toed defanged girshlings (+100 Find, +90 kill, +100 Get a Corpse; corpse in the pack). Two girshlings together took us 27 → 10 → 4 (bark, then Teleport out), rested upstairs, came back: **level 5 at turn 52560** (+3 HP to 30, +70 SP to 130, +1 MP to 2; "genome excited" rapidly advanced Freezing Ray +3, capped at rank 3 by level). Many routine fixes (fight review, downtime reload, line of fire, prefixed names, voice narration). Stopped at Red Rock's surface (should have stopped at the goal on stratum 4). XP 1975/3340.

- **2026-11-24, Joppa → Maggatum → death at level 6** (turns 52631 → 54497). Joppa: quest turned in (+750), loot sold, a buckler bought by mistake (shield AV only on blocks), cooked a free meal. Maggatum (14,22): Visit Maggatum +250. Held by the Third Ithri-Sehian Family (feral dogs worth 5 XP, two giant amoebas, guard dogs); fled south into a desert canyon of irritable tortoises (level 5, carapace stops even musket slugs) and a horned chameleon (+125); a tortoise bled out (+125). Teleport landed one cell away; the ubernostrum and two salves bought time. **Level 6 at turn 54496** (an amoeba frozen to death), but still surrounded at HP 8: the user said to fight on until clear or dead; a guard dog bit for 8 at HP 5. **Died at turn 54497.** Review in research/fight_reviews.md.

- **2026-11-24, level 6** (reload at 53342, turns 53666 → 55003). After the reload the brain ran the stale explore plan in Joppa (fixed: a rewound turn now holds the plan). Maggatum again: +250 on arrival. Held the south edge with a wall at my back: two amoebas and four feral dogs died one at a time (one salve). Left the edge to rest and met the north group: HP 3, Teleport (landed 8 cells off, behind a wall, unseen), one salve, rested to full in a pocket. Stepped out to a full-HP guard dog: musket, Freezing Ray, axe: **level 6 at turn 55000** (guard dog +200), then finished the amoeba; clear at 55003, HP 29/33. Left: 1 salve, unspent SP and MP, five empty armour slots.

- **2026-11-24, home to Joppa** (turns 55003 → 56420). Points: Multiple Legs 3, Single Weapon Fighting (toggle on), 120 SP held for Weapon Expertise (research/points_plan_level6.md). Rested to full in Maggatum so Teleport was ready; "hostiles nearby" blocked the world map until we moved a few cells. On the world map: declined ruins at (13,22), then got lost in the rusty salt marsh; the explore routine killed a croc unhurt; walking west a zone found our bearings and the Durqumish Sphere (a ruin, noted). Arrived in Joppa at turn 56420, HP 34/34, Hungry.

## Next session: replay to level 2 from the checkpoint

The session of 2026-11-24 ended without a save, so the game resumes at the Joppa checkpoint (north edge, turn 46237, level 1, both quests). To replay with what we learned:

1. Start the game, Continue, press F1 (message log: "Bot: run started"). The plan in `brain/plan.json` explores, then hands over to remote mode.
2. `CmdMoveU` to the world map, then `CmdMoveN` twice to Red Rock (300 turns per step). Arriving at Red Rock gives +50 XP (quest step).
3. `CmdMoveD` into Red Rock. `CmdMoveD` again triggers "walk to the nearest stairway down?" → `KEY y`, then `CmdMoveD`.
4. Explore each cave level with `hand_off`. At each hostile: Look (`CmdLook`, arrow keys, read the footer), fight if Average, Look between blows, step back under half HP, rest out of sight (`CmdWaitUntilHealed`).
5. Eat when the sidebar says Hungry (twice if one serving isn't enough).

Last time it took 1632 turns, mostly travel and exploring. Red Rock may be generated differently this time; the world file's Red Rock entries are hints only.

Before or instead of replaying, worth deciding: script the fight routine (it's the same every time), and what to spend the level-up points on.

## Later (not decided)

The longer-term target (character level, story progress, depth, or the game's score), the clock, and how to treat deaths are still open.
