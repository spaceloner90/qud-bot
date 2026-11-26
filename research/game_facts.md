# Game facts and how-tos recovered from my own past replies (2026-11-26)

Mined from the full transcript of 2026-11-24/25 (four readers, each fact checked against the notes and
missing or code-only there). Imported by CLAUDE.md. Facts, not rules (rules are in lessons.md). Marked
"(unverified)" where it was an inference. Add to it as we learn; correct in place.

## Known bot defects

- **Explore never saw autoexplore steps** (the game doesn't consult the bot between them; no map call
  with autoact set in 8928 traced calls), so "break off to hunt prey in view" never fired. Fixed in mod
  v0.26 (needs a game restart): explore lists prey kinds in live/interrupt.txt and the mod interrupts
  autoexplore once per creature when one is in view; check log.jsonl for `autoact_interrupt` lines.
  Unverified live.
- Melee at prey that the game silently ignores (no hit, miss or penetration message) twice in a row: the
  fight routine leaves that creature for the zone and says so (2026-11-26; the user: dragonflies may only
  be reliably hittable when they come down to bite).
- Picking Charge or Freezing Ray while it cools down can leave the bot sitting in the abilities list.
- The threat estimate rated the two-handed iron long sword at 0.0 damage a turn against a 3-HP bat ("need
  60 turns") and handed over as "kite"; one swing killed it (Uumurem, 2026-11-26). Check threat.py's
  Cause: off-hand torch misses counted as the sword's, and 3 misses alone set its hit rate to 0. Fixed
  in threat.py (misses checked against the wielded weapon; observed rate blended with the computed one
  over PRIOR_SWINGS = 10); vet 0 failing. Hand-played swings still aren't recorded (no target in remote).
- Explore can report a false "stuck" after several pickups in a row (position unchanged): just resume.
- Autoexplore sometimes stalls with "no progress" after picking up a pile (not weight): restart it.
- Autoexplore won't move while a hostile is in view, so a hostile in an unreachable pool stalls it.

- An identical plan re-sent after a hand-over was ignored (step.py compared plan text only), so the run
  sat in the remote stage (2026-11-26). Fixed: plan.json's mtime counts too; tools/watch_handover.py
  reports HELD when a plan is ignored for 15 s.

## Creatures

- **Pools are groups**: hitting one glowpad or glowfish turns the whole pool hostile; the glowpads stay in
  the water, the glowfish come at you. Glowpads are not strictly rooted (a calm one moved a cell).
  Glowpad parts (stems, bud, leaf) sold for 0.01 drams total: not worth a detour.
- **Swarmers** (girshlings, snapjaws, feral dogs): each gets stronger with another swarmer beside it.
  Fight them one at a time.
- **Snapjaw warlord**: 20 HP, four or five attacks (steel war hammer, bites), Swarmer, tracks by smell,
  DV 11, 50 XP. Snapjaw scavenger: 3 HP, crits for up to 7, 10 XP (5 at level 5).
- **Snapjaw Kings** (heroes): the game's difficulty word ("Average") and the exported level (1) badly
  understate them; trust our estimate. Heightened Smell (they track through walls); Swarm Alpha makes
  nearby snapjaws stronger. One had 112 HP, a fleet-footed one 64 HP and faster than us.
- **Croc**: ~13 HP, bite 1d4, 75 XP at level 1 (37 at level 5); follows onto land but loses ground to
  speed 120. In water it's at home.
- **Giant dragonfly**: 6 HP, 25 XP; untargetable while flying; once it lands it's hittable but hard to
  hit in melee (6 HP lost for 1 damage): ray it.
- **Young ivory**: a trap creature hidden under bones; Look shows only the bones; it bursts out with
  damage and bleeding when walked over; doesn't move; resists cold 50%. Attack its cell on purpose.
- **Lurkers** (horned chameleon) and hidden creatures show as empty under Look, but the snapshot lists
  every creature in a visible cell with a `seen` flag (no code reads it yet).
- **Weeps** (acid, slime): peaceful fungi, 300 HP, pool acid. Leave them.
- Fork-horned gnus: a herd of ~18 at level 12 led by a legendary 158-HP gnu. Chitinous puma: level 12,
  45 HP, charge and flurry. Both far out of reach at low level.
- Web-toed creatures (girshlings) probably aren't slowed by water as we are (unverified).
- A creature whose name confusion garbles: read its parts (a plant with a fear aura is a dreadroot).
- Names like "glowfish and friend to fungi" / "and member of ..." carry an allegiance: killing may cost
  reputation (the bot leaves them).

## Fights and abilities

- **Freezing Ray** freezes for about a turn, then the target stays slowed by the cold for most of the
  fight. On a target standing in liquid it freezes the pool: the target is stuck and can't move, a real
  hold. It hits everything in its line.
- **Charge** from 2 cells has failed with "no clear line" every time (Yim, Uumurem x2): it likely needs the target 3+ cells away: from 4 cells it worked (Uumurem, centipede). Fixed: fight.py charges from 3-4 cells only (2026-11-26). It also fails if we slip on the ice our own ray left; can't be used while swimming (the list stays
  open); needs a straight line.
- **Teleport** with AIM sets the centre, but the uncertainty radius (12 at rank 1) still applies.
- With AIM set, abilities fire with no targeting screen: back on the map with the ability's message
  means it worked. Cooldowns show in the list ("[15 turn cooldown]"); trying anyway gives "You must wait
  N rounds"; Escape out costs no turn.
- **Sprint** costs an action to switch on: next to an enemy at low HP that can be fatal.
- **Terror steers movement**: a step away can become a step into the enemy. Tuber terror lasts ~10
  turns (the dreadroot aura ~4); a tuber also satiates partly.
- A crit can daze us (AG, IN, DV and speed drop briefly) or crack our armour (AV down for the fight).
- Witchwood bark: confusion ~15 turns when it comes, but not always; part of the heal can come as a
  lingering "healing" effect.
- Musket: kept for range 2+ (point-blank shots go wild); shots into a pool hit brinestalk and glowpads
  in the line. Whether a shot plus reload costs ~2 turns is unmeasured.
- HP gain per level-up is rolled: 2-5 with Toughness 18 (HP at level 5 ranged 29-35).
- XP shrinks as we level well before the wiki's "out-tier by a lot" (croc 75 -> 37 by level 5).
- Our sturdy steel battle axe's crit "cleaves through" armour (lowers the target's AV).

## Terrain and movement

- **Water**: over 2000 drams is swimming depth (deep: -50% move, +500 action cost); shallower is wading
  (-20% move, fine). The game asks "Move again to enter it and start swimming". `~` can be a deep pool,
  not only `≈`: read the snapshot's features. Liquids coat equipment; water does no damage.
- **Sap pools** make you stuck for a few turns.
- **"There are hostiles nearby!"** can come from a hostile out of sight, even behind the zone edge;
  moving a couple of steps away and retrying cleared it.
- **Lost**: going up is refused ("You are lost!"), even inside Joppa. **Talking to any humanoid clears it at once** ("You ask about your location and are no longer lost", 2026-11-26, Mehmet); otherwise a 20% chance per new zone entered (wiki). Each world-map step risks getting lost; the drop can be any zone nearby (Uumurem landed in Joppa's south outskirts going north). Before: walk zone by zone. Walking north from near Joppa reached
  Red Rock's outskirts and the +50 arrival step anyway. Reaching a known town clears it.
- Going down onto a world-map tile asks "a) Current location (N)" or "b) Center"; Joppa is the centre
  zone, so pick Center to enter the town.
- Rust wells: world tiles (16,22) and (16,24). Small marsh dungeons only show as a "notice some ruins"
  prompt on their tile.
- **Two-handed weapons cost the torch**: the iron long sword (1d8, pen 7) unequips it, and underground the
  visible cells dropped from 19 to 9 (Uumurem, Red Rock stratum 1). That's only about one cell less sight radius,
  and the sword one-shot a 5-HP giant amoeba that the iron dagger did 1 a hit to (pen too low): the sword
  wins even underground (revised the same day). Equipping a torch from the stack lights it.
- A blazing torch lights about 3 cells underground (about 4 on the surface at night).
- The snapshot map: unexplored cells blank, remembered cells show terrain but no creatures, creatures
  only in cells in view now (indoors you see nobody outside).

## Quests, NPCs, economy

- **Watervine turn-in**: Mehmet sends you to Elder Irudad; pick "its fangs removed" (defanged corpse),
  then "I am sorry to cause pain, Elder". Reward: +750 XP, an ubernostrum injector, 3 salve injectors, a
  weird artifact, +200 Joppa reputation. The girshling corpse weighs ~54 lb.
- **Argyve**: his "Choose an artifact to give" list counts injectors (ubernostrum, salves) as artifacts,
  so pick deliberately; the ubernostrum was accepted (+150 XP). A broken artifact is accepted too.
  Follow-up quest: Weirdwire Conduit (200 feet of wire from the rust wells). After his quests he trades
  with us (bought spare gear for 64 drams). His hut: walls (3-12, 17-21), gap in the north wall at (7,17).
- **Identifying artifacts**: Tam "doesn't have the skill"; Argyve offered none (vendor examine untried).
  Examining one ourselves can break it. Unidentified, a trader pays less than a dram; Tam's $85 was his
  asking price.
- Elder Irudad: Tab ("Tab - Trade") didn't open a trade; he points to his daughter Nima Ruda.
- Tam: musket $48.57 (Bows & Rifles), slugs $0.03; musket + 40-52 slugs ~50 drams. Leather boots AV 1.
- Gear seen: studded leather AV 3 DV -2; leather apron AV 1 (body slot); cloth robe AV 1; painted bark
  armour AV 2 DV -1 (worse than leather); quilted shawl -1 DV; sandals nothing. Leather whip pen 7 1d4;
  bronze battle axe pen 5 1d2; steel hand axe pen 7 1d3+1, one-handed (the torch stays lit). Leather
  armour's own AV: replies disagreed (2 or 3), check in game.
- Shields add AV only on a successful block (~1 in 4 without the Block skill); the DV penalty always
  applies.
- Camp meal ("whip up a meal") works with Make Camp alone, no Cooking skill. Make Camp next to an old
  campfire offers to walk to it (old fires stay lit). "You can't cook with hostiles nearby" counts
  hostiles out of sight.
- Carry capacity: ~369 lb at Strength 23.
- Leads: Duramur "9 parasangs west of the Yd Freehold"; Maggatum (3 parasangs east of Joppa), held by the
  Third Ithri-Sehian Family, linked to "Recover Analogucus Ithri-Sehfriend at Old Shekish". The journal's
  Locations tab has a collapsed "Historic Sites" entry with directions (Escape collapses, doesn't close).

## Driving the game through the bot

- Dismiss the "health below 40%" popup before the next command: it blocks it (CmdAbilities didn't open).
- Space on an item's popup takes the default action (for food: eat). Read before Space.
- Equipment screen: Space on a slot opens the equipped item's own menu; the slot's letter asks what to
  put in; remove = cursor to the row, Space, "r) remove". Equip from the inventory ("e) equip (auto)").
- A small pile box left on screen keeps the inventory from opening: close it first. Inventory rows cut
  long names, so match a shorter part; a digit key doesn't scroll.
- Escape didn't leave the character screen's Skills tab; a following Space bought/clicked a skill.
- Picking from a pile: the item's letter, then "g) get", then Escape (the list stays open). Rows carry
  stat glyphs, so match by name prefix.
- Keypad5 in a direction prompt is our own cell.
- Never press Space while `wait` is `picker` (it selects a cell); Escape cancels without a turn. The
  picker's screen text doesn't show the map; Escape and reopen resets the cursor to the player.
- The Look card vanishes when the cursor is on an empty cell; it stays on the player if it didn't move.
- F1 toggles a run (twice = start then stop). Alt, Ctrl, Shift, Win and Tab don't stop it; presses
  while unfocused or within 0.5 s of refocusing are ignored; the key that stops a run is swallowed.
- Death screen: View final messages, Reload from checkpoint (Roleplay), Retire, Quit to main menu.
- Mod changes need a full game restart; a new game from the menu doesn't reload the mod.
- The game id is the save folder's name (runs/<game id> matches it).

## Tools and editing

- tools/next_zone.py <N|S|E|W>: walk to the edge, cross, start explore-and-hunt; exits 2 on failure.
  Run it in the foreground and start the watcher separately (a `&&` chain left no watcher when it failed).
- tools/profile.py: records the character sheet into runs/<id>/profile.json; run after each level-up.
- brain/world.py and tools/world.py share a name: a tool importing both must load the brain's first.
- Kind and food edits go to the shared queue brain/game_edits.jsonl, applied by whichever run calls next.
- Explore/fight args beyond design.md: `stay`/`stay_turns` (hold a cell with nothing in view),
  `ignore_far`, `assess_radius` (12), `outnumber_radius` (3: only enemies this close count toward
  max_hostiles), `auto_start` in bridge.json (start the run once in a zone).
- Editing: no backslash escapes through shell heredocs into code (`\b`, `\n` got mangled; a backspace
  in a C# string froze the game); don't rewrite files through PowerShell (garbled UTF-8, wiped a
  section); keep .ps1 ASCII; compile before the bot can run it; brain output is UTF-8, inputs utf-8-sig.
- Harmony fails if a patched method name has several overloads: check it's unique first.
- Before adding a key to world.SHARED (shared game knowledge), check the world files don't already use
  that key for per-run data: "features" did (per-cell map features), and a save copied 3,507 of them out of
  Uumurem's world.json (2026-11-26, repaired; a unit check now guards it). Back up both files before
  touching shared keys, and round-trip load/save to check.
