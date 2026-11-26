# Points plan at level 3 (2026-11-24)

Unspent: **1 attribute point, 2 mutation points, 132 skill points.** Character: ST 22, AG 18, TO 18, IN 14, WI 16, EG 16; mutations Freezing Ray 1, Multiple Legs 1, Teleportation 1, Amphibious (defect). Skill texts: `skills_level2.md`; abilities: `abilities_level2.md`. Mechanics below are from the game's own screens where possible, otherwise from the wiki (marked; numbers may differ by version).

## What the points do (mechanics)

- **Attributes** (wiki): Strength → melee damage and penetration, carry weight. Agility → to-hit (melee and ranged), dodging (DV). Toughness → HP and HP regeneration (retroactive). **Intelligence → skill points: +4 SP per level for each point above 10, retroactive**, and many skills need IN 15+. Willpower → activated-ability cooldowns (the wiki's Freezing Ray cooldown table depends on WI), HP regeneration, mental armour. Ego → mental mutation levels, persuasion, prices. Modifiers change every 2 points, so a single point often only matters when it crosses a skill requirement.
- **Mutation levels** (wiki): Freezing Ray damage is (level)d3+1, so level 2 roughly doubles the dice (avg 3 → 5), and the freeze gets stronger with level; its cooldown depends on WI, not level. Multiple Legs: move speed and carry capacity scale with level. Teleportation: higher level means a more precise landing (smaller random area).
- **Skills** (screen + wiki): a skill needs its points *and* its attribute requirement; the tree's root may need buying first (unconfirmed for skills the class gave us).

## Options and recommendation

### Attribute point → **Intelligence 14 → 15** (recommended)

- Unlocks the IN-15 skills: **Mind's Compass** (world-map travel twice as fast; our biggest turn cost is 300 turns per world step), **Meal Preparation** (cook meals at a campfire, which restore hunger fully; vinewafers turned out not to be food), **Harvestry** (harvest usable parts from plants; the user wants terrain resources harvested).
- +4 SP per level, retroactive (+12 now if the wiki is right): 132 → ~144.
- Alternative: **Willpower 16 → 17** unlocks Fasting Way (half hunger and thirst, good for Amphibious), but that also needs the Self-discipline tree (150) + 50 = 200 SP, two levels away. Better as the *next* attribute point.

### 2 mutation points → **Freezing Ray 1 → 2**, then **2 → 3** if the game allows

- The ray is our best tool: it freezes (the frozen spider didn't act), it's used automatically by the fight routine, and more damage plus a stronger freeze directly reduce how hard fights hit us (the amoeba, the vine).
- If the game won't raise it twice (there may be a cap tied to character level), the second point goes to **Multiple Legs 1 → 2**: faster running suits our escape-and-rest pattern (the amoeba) and shortens walks.
- Not Teleportation: we only use it in emergencies.

### Skill points (~144 after IN) → **save for Cleave (150)**, then the IN-15 utility skills

- **Cleave** (Axe, 150, ST 19): each axe hit has a 75% chance to give the target −1 AV, stacking (up to half the ST modifier). Many of our blows didn't penetrate; this compounds in longer fights. We'd be ~6 short after IN, so it comes with the next kill or two.
- Then **Wayfaring** (100, if the root needs buying) + **Mind's Compass** (0), and **Cooking and Gathering** (100) + **Meal Preparation** (0) / **Harvestry** (50).
- Alternative order if travel time matters more than fight speed: Wayfaring + Mind's Compass now (~100), Cleave after two more levels.

## How to carry it out (each step read before acting)

1. Character sheet (`CMD CmdCharacter`): cursor on Intelligence, Space, confirm the value and the SP total.
2. Same sheet: cursor on Freezing Ray (right column), Space; again if allowed. Read the level after each.
3. Skills (`CMD CmdSkillsPowers`): nothing bought until Cleave is affordable, or the user prefers the travel order.

## Done (2026-11-24, approved by the user)

- Intelligence 14 → 15: skill points 132 → 140 (+8 at once, less than the wiki's +12).
- Freezing Ray rank 2: the rank-up screen shows this rank vs next (damage 1d3+1 → 2d3+1; melee cools −1d4 → −2d4 degrees; range and cooldown unchanged). Rank 3 refused: "You may not advance this mutation's rank yet" (a cap tied to level).
- Multiple Legs rank 2 (the second point): +20 → +40 move speed, +6% → +7% carry capacity.
- 140 SP kept for Cleave (150): buy it at the next level-up (or as soon as 150 is reached).
- How: `CMD CmdCharacter`, cursor to the stat or mutation, `KEY Space` shows a confirmation with this/next rank, `KEY y` confirms.
