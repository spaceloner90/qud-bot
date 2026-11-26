# Standing lessons (from every user message, 2026-11-24 to 2026-11-26)

Recovered from the full transcript after a compacted conversation dropped them (the owner,
2026-11-26: "a lot of in memory info that was not written into proper learnings"). Required reading
from AGENTS.md (CLAUDE.md loads it into every Claude session). "The user" below is the project's owner.
Dates point back to the owner's words. Add to it; don't trim. Nothing lives only in an agent's memory.

## How to find the answers (the user's review of Uumurem, 2026-11-26)

Ways of looking, not item rules. Each came from something available that went unused.
- **Evaluate every new thing on first sight, not only creatures**: each new liquid, terrain feature,
  item kind and object gets a quick "what is it, what could it do for us (drink, fill, sell, use), is it
  worth a detour now" (look it up if unknown). Missed: a cider weep and a wine weep on a peaceful surface
  could have filled every container and solved money at the start.
- **Inventory review at every decision point** (level-up, take stock, checkpoint, before a hard fight):
  every item in the pack, not only what the gear check flags, gets "what could this do for us now".
  The gear check compares melee weapons and armour only. Missed: a bow and arrows from the first fight.
- **Ability review at every hard fight and escape**: go through the whole abilities list and ask which
  applies here (move, escape, control, damage). Missed: Sprint, never used, though escapes mattered.
- **In town, read every shop's full stock and judge it against the character**: what would widen our
  combat options (a ranged attack, an empty armour slot, a better weapon), raise our stats or keep us
  alive (food, water, healing), for what we can afford. And use what the town gives free and safely
  (a camp meal when hungry, rest, refills). Missed in Joppa: a ranged weapon and the free meal while
  Hungry. Learnings are meant to be universal like this; past runs' logs are for when we're stuck or
  diagnosing, not a script to follow (the user, 2026-11-26).
- **When I drive by hand, the bot's background routines stop** (auto-eat, auto-cook, status checks, gear
  checks). In hand-driven stretches (towns, travel), do those checks myself.
- **Know what an estimate leaves out before trusting it**: our threat estimate doesn't model skill to-hit
  bonuses (Axe Proficiency +2) and compared a weapon's observed record against a computed chance for
  another. A small estimated edge isn't evidence; the game's own numbers and a measured test are.
- **Data is keyed by what it describes**: per character (skills, levels change hit rates) and per item
  (by id), not pooled by name across characters. Weapon records were shared game knowledge by name,
  mixing five characters' swings.
- **Readable for a human viewer** (recordings): a set-up that only works because the bot reads hidden
  data (fighting in the dark with no torch) is fine for one moment, not as the default. Light for
  exploring; switch weapons for the fight, then switch back.

## Fights

- **Hard or chancy fights: one turn at a time**, re-examining the board each turn, until it's
  comfortable to defer to the scripts again; the trade-off is to be honed (11-25). No batched attack or
  move loops, no multi-step auto-pathing mid-fight; there is a time and place for step by step (11-24).
- **Hand over** when close to death unexpectedly, in close fights, when a new enemy joins (11-25).
- **Strategy is judgment, not scripts**: a hard fight at our level warrants waiting for every cooldown
  and opening with Freezing Ray; the desperate option is a ray every 20 turns from behind a corner (11-25).
- **Pursuers follow across zone edges**; out of sight is not safe. Don't stop and start a new fight in
  the next zone (11-24, Maggatum).
- **No safe retreat: sticking it out can be best.** Never conclude "never engage" a group; it bars the
  area for good (11-24).
- **Escaping**: blind running pulls more enemies; beeline in a feasible direction that avoids them;
  don't corner yourself (11-24).
- **Standing still regenerates** even when the game won't rest, and an enemy coming to us is a better
  position than charging in (11-24).
- **Kite only when the enemy is slower and dangerous**; otherwise we wait forever on a 20-turn ray or
  waste ammo (11-24). Chip-and-back-off can farm a risky enemy (the amoeba) when progression is locked;
  with the stairs in sight there's room to manoeuvre (11-24).
- Freezing isn't guaranteed: check it worked before closing (11-24).
- **Terror, daze, confusion: wait them out safely**; never take turns freely while confused, it garbles
  input (11-24, two deaths). So witchwood bark (confuses) is not a mid-fight heal; "no need to eat bark"
  when not desperate (11-24).
- **Teleport is near-suicidal**: only when death is otherwise near-certain; no script invokes it (11-24).
- **Dangerous fixtures (dreadroots): chop them down**, don't walk past them mid-exploration (11-24).
- **Musket** only for what's dangerous; **reload in downtime**, not at the next fight (11-24).
- **Ranged and melee enemies need different tactics**; vet any new fight logic against the suite of known
  enemies (11-25).
- **Never assume an enemy will do something** without safeties and wake-ups (11-25).
- Pause sooner when projectiles come from out of view (11-24).
- In explore-and-fight, heal before going on unless an enemy is adjacent (11-25).
- **Death can be cheaper than burning every resource** near a checkpoint; case by case (11-24).
- Finish the encounter before anything else (a level-up mid-fray isn't a stop); once clear, a level-up
  hands over to reconsider points (11-24).
- **Learning over avoiding** (11-24): when the game rates something harsher than our estimate, something
  is unmodelled. Read more first (its parts and description), then engage at range and watch; record a
  tactic ("kill from range, never adjacent"), not a ban. Pure avoidance is for what's hopeless by the
  numbers. When something hopeless blocks the way, go elsewhere (hunt the local zones) rather than retry.
- **Evaluate every enemy dynamically** from its stats; danger depends on build, level and gear (11-24).
  Work out damage and resistances from the game's numbers up front, not after the fact (11-24).
- **Fill every armour slot**; being hit hard by basic enemies means we're under-armoured (11-24).
- Non-hostile critters can be hunted unless dangerous or important (quest givers, named NPCs, faction
  members); farm neutral prey; evaluate every new critter (11-24, 11-25).
- Review our own fights afterwards, autonomously, and turn each finding into a change (11-24).

## Moving around

- **Know where hostiles are even out of view**; rest only somewhere safe (11-24).
- **Pay attention to terrain** (11-24); deep water: -50% move, +500 action cost (11-25).
- **Walking the overworld or random wilderness isn't profitable**: sparse or deadly, costs time and
  water. Hunt inside the marsh zones near Joppa, zone by zone (11-24, 11-25).
- **Don't go far from the starting area** at low level; it's all far too dangerous (11-24).
- **Something too strong in the way: give up that goal and go elsewhere** (11-24).
- Getting lost far away was doom (11-24); each world-map step risks it.
- In-zone movement never reaches the world map; that's its own key (11-24).
- Town entry and exit are checkpoints (Roleplay); go back when progress is worth preserving and it's
  cheap (11-24, 11-25).
- **Take stock routinely** (resources, safe way back, threats here, retreat route): an LLM judgment, not
  a script (11-24).
- The walk tool must stop for every danger explore stops for (11-24).

## Items and resources

- **Loot everything** while weight allows; note all items; pick up and equip a clear upgrade at once
  (11-24).
- **Read books before selling; identify artifacts before handing them over** (11-24).
- Water is the currency; Amphibious pours our water over us (the defect, known) (11-24).
- **Food**: stockpile before leaving town; eat to Sated when food is at hand; camp when safe, not as soon
  as Hungry (track Sated -> Hungry, then wait); walk to open ground for a camp rather than eat the jerky
  (11-24, 11-25). Camping isn't free of danger (11-24).
- Valuable things on the ground, including terrain, are worth harvesting or remembering (11-24).
- Inventory decisions are mine; menus by macros with one validation before confirming; fuzzy key presses
  that observe the expected state (11-24).

## Running the bot

- A stop keeps the run live and wakes me; observe "no game change when one was expected" and kick back
  (11-24, 11-25).
- Every skipped popup is interpreted later; a warning (Famished) is never pressed past (11-24).
- One cursor failure isn't a reason to give up: find out why (11-24).
- When things go badly, end the turn and discuss (11-24). Answer the user's messages; don't charge ahead
  past them (11-24).
- Stop at the user's explicit goal and hand over (11-24).
- Look things up before calling them unexplained; the wiki is fine for mechanics (11-24).
- Track experience and profile per character; no global counts in the log (11-25).
- Narration: hand-off first, then the decision; brief updates about every 20 s; only interesting lines;
  the panel is a thought train (objective, goal, reasons) (11-24).
- Each character plays fresh (no references to earlier runs), but the things we know, we know; explore
  Joppa fully for XP and loot (11-24).
- World knowledge (per run) vs game knowledge (shared) (11-24).
