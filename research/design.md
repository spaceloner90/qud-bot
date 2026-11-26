# Design

## I/O (2026-11-24)

**Why a mod and not pixels and keys.** We tried the raw window first (`tools/win.py`). Capturing the window with PrintWindow works with the game in the background, but frames flipped between the modern and classic main menus. Keys sent as window messages are ignored (Unity). Real key presses need the game in the foreground, and Windows refused to bring it forward while another app had focus. The mod approach matches the Shogun Showdown project.

**Hook points found in the game code** (`research/types.txt`, `research/il_*.txt`):
- `ConsoleLib.Console.Keyboard.GetNextKey` is where the game blocks for a key: on the map (`XRLCore.PlayerTurn` → `CommandBindingManager.GetNextCommand` → `getmeta` → `GetNextKey`) and in classic popups and menus. A prefix there runs on the game thread just before every wait. Menus and popups block there with an empty queue. **The map doesn't:** `PlayerTurn` loops `kbhit()` → `Keyboard.IdleWait()` (a `KeyEvent.WaitOne`) and only calls `GetNextCommand`/`GetNextKey` once a key is queued, so the same prefix also runs before `IdleWait` (found 2026-11-24: F1 started a run in the world but the brain was never asked).
- `Keyboard.PushKey(XRLKeyEvent, bool)` is where key presses enter the queue (Unity thread). The mod pushes its keys through it, and also watches it for the control keys F1 (run), F7 (step) and F8 (report). The game binds F1 (Help, target lock), F2, F5 and F9.
- `Keyboard.PushCommand(string, object)` queues a named command (`CmdMoveN`...).
- `TextConsole.CurrentBuffer` is the 80x25 `ScreenBuffer` the classic UI draws. `ConsoleChar.Char`/`ForegroundCode` give the text and colours (or `BackupChar` when a cell shows a tile).
- `The.Player`, `GameObject.hitpoints/baseHitpoints/Level/CurrentCell`, `Zone.ZoneID/DisplayName`, `The.Game.Player.Messages.Messages`.
- `Options.ModernUI` (`OptionModernUI`): with modern UI on, many screens are Unity UI that never calls `GetNextKey`. The bot needs it off.

**Control flow.** Keys the game has bindings for never reach `Keyboard.PushKey` as keys: `GameManager.UpdateInput` (every frame) turns them into commands (`PushCommand` → `PushMouseEvent("Command:...")`). F1 is bound to CmdHelp, so a PushKey hook never saw it (found 2026-11-24 when F1 did nothing). So a postfix on `UpdateInput` reads F1/F7/F8 straight from the Input System keyboard, and the mod drops F1's raw key and its CmdHelp/CmdLockUnlock commands while it is held. It then pushes the unbound F6, whose arrival wakes the waiting `GetNextKey`; on the next wait the prefix finds the queue empty, calls the brain and pushes its keys. During a run, any other key press stops it (raw keys are also dropped). Control key presses are logged as `control` lines. A brain can answer WAIT to be asked again without playing anything; the `remote` script uses this so the LLM can drive a run live. A run stops on STOP, a brain error, or after max_calls_per_run (100000 in bridge.json; remote mode answers about once a second). An answer with nothing to play is PASS on the map and WAIT off it (step.py, 2026-11-26), never a stop.

**Focus.** `PlayerTurn` starts each input loop with `while (!GameManager.focused) Sleep(200)`; `focused` is set by Unity's OnApplicationFocus. So no map input is processed while the game window is in the background (found 2026-11-24: keys sent while the user was in another window did nothing). During a run the mod reports the game as focused.

## Input findings (2026-11-24, hands-off tests with v0.7)

Each test compared snapshots before and after, with nobody touching the game and the window in the background.

- `CMD CmdMoveN`: (37,22) → (37,21), turn 45925 → 45926. **Commands work.**
- `KEY UpArrow`: no change. **Raw keys for bound actions do nothing on the map**: the game takes its bindings from the Input System and acts on named commands, not on the legacy key codes in the queue. (Raw keys may still matter in menus and popups; not tested yet.)
- `CMD CmdMoveE` + `CMD CmdWait` in one answer: moved east, but only one turn passed, and the wait was gone. `CMD CmdWait` on its own: +1 turn. **On the map an action clears whatever input is queued behind it**, so scripts give one action per brain call. The brain is asked again before every action anyway.
- Command names are the IDs in the game's command bindings (CmdMoveN/S/E/W/NE/NW/SE/SW, CmdWait...).

## Conversation and movement findings (2026-11-24)

- `CMD CmdTalk` opens "Talk [Select a direction]" (wait `key`); you have to stand next to the person first. `KEY Escape` cancels.
- `CMD CmdMoveTo` opens a cell picker ("Move where? Space-select") that dims the map to points of interest. `XRL.UI.PickTarget.ShowPicker` loops on `Keyboard.kbhit()` and reads a key only once one is queued, so the bot wasn't asked there and the run hung. Since v0.11, `kbhit` asks the brain while a picker is open (wait kind `picker`).
- `GOTO x y` (v0.11) plays one step of the game's own path (`AutoAct.TryFindPathStep`, which Move to uses) as a `CmdMove<dir>` command. It replaces the picker for walking.
- F1/F7 now say so in the message log ("Bot: run started").

## Mod changes in v0.12 (in game since 2026-11-24 02:50)

Seen working: the quest log and game ID in the snapshot, and going up to the world map plus two world-map steps with the game in the background (no stall). Not yet seen: a zone change by walking off an edge in the background. The per-turn trace works (live/turns.jsonl, every turn including autoexplore steps; corrected 2026-11-26).

- Quest log in the snapshot enumerates `StringMap.Values` (the `IDictionary` cast threw "Specified method is not supported").
- Line breaks in screen text and glyphs become spaces (conversation text showed `♪`).
- **Run in background:** confirmed cause of the zone-change stall (2026-11-24: a step south stalled for 45+ s and went through the moment the user clicked into the window). Unity stops its frame loop when unfocused, and a zone change waits on it. During a run the mod sets `Application.runInBackground = true` and restores the game's own setting afterwards.
- **Per-turn trace:** a begin-player-turn callback appends `{turn, zone, x, y, hp, autoact}` to `live/turns.jsonl` during runs, including every autoexplore step.

## Travel findings (2026-11-24)

- **Zone IDs** look like `JoppaWorld.11.22.1.1.10`: world-map cell (parasang) 11,22, zone 1,1 within it (each parasang is 3x3 zones, Joppa is the middle one), depth 10 (the surface).
- **Walking off an edge** goes to the neighbouring zone of the same parasang: north of Joppa is `JoppaWorld.11.22.1.0.10`, "outskirts, Joppa" (you arrive on its south edge). It never leads to the world map. `CmdMoveFarN` ("Move to northern edge") walks to the edge with the game's pathing.
- **The world map** is a deliberate "Move up": `CmdMoveU` (keys `<`, numpad minus, `s`); `CmdMoveD` goes down into the cell's zone. On the world map the zone is the world's own ID (`JoppaWorld`, "Qud, surface"), the player's x,y is the parasang, and the 80x25 map is the whole world with every cell visible. `CmdMove*` moves one parasang.
- **A world-map step costs 300 turns** (46237 → 46537 → 46837). Walking a parasang zone by zone may be cheaper or dearer: compare once the per-turn trace works.
- **Tile names aren't in the snapshot** (it lists creatures, items, doors and stairs). The game names the tile you enter in the message log: "You pass by some salt marsh.", "You pass by Red Rock.". Red Rock is at (11,20), two parasangs north of Joppa (11,22), as the quest said.
- **Travel uses water:** "You pour fresh water from your waterskin over yourself" came on every world-map step (and sometimes in Joppa).
- **Re-entering a town saves** (Roleplay checkpoint): after stepping back into Joppa, a restart resumed there with both quests (user, 2026-11-24).

## Inventory, food and light findings (2026-11-24)

- **Quest steps give XP:** arriving at the place a quest step names completed the step with a popup, "You have finished the step ... You gain 50 XP!". So XP comes from progress, not only kills.
- **Hunger** shows in the sidebar status line ("Wet,Hungry" → "Wet,Sated"). Eating: `CMD CmdInventory`, the item's letter (moves the cursor), `KEY Return` (action menu: a) eat, d) drop, e) equip...), then the action's letter. Eating closes the inventory and shows a popup.
- **The inventory screen tells more than the snapshot list:** categories (Food, Light Sources, Meds, Scrap, Water Containers), servings, drams of water, weights. `CMD CmdEquipment` shows the body slots and item stats (`→5 ♥1d2`, `♦2`).
- **The snapshot's item names drop states:** it showed "torch" while the equipment screen said "lit torch (blazing)". The snapshot uses `DisplayNameOnlyStripped`; next batch, use a fuller name.
- **Night vision:** a blazing torch lit about 4 cells around the player on a surface zone at night.
- One key per screen also applies here: eating closed the inventory, and the next two keys landed on the map (harmless that time).

## Stairs and depth findings (2026-11-24)

- `CmdMoveD` off the stairs asks "Would you like to walk to the nearest stairway down? [Yes] [No]"; `KEY y` walks there (the game's pathing), then `CmdMoveD` again goes down.
- Down is the same zone ID with the depth +1: `...11.20.1.1.10` (surface) → `...11.20.1.1.11` "Red Rock, 1 stratum deep". You arrive on the up-stairs `<`.
- Stairs show in `map.objects` once in view ("stairs down", "stairs up"). Not seeing them at night was just darkness, not a detection gap.
- Hunger came back about 400 turns after eating (Hungry at 47236, ate at 46838).

## Combat findings (2026-11-24, first fights)

- **Look before fighting** (`CMD CmdLook`, no game time): the cursor starts on you; raw arrow keys (`KEY DownArrow`, `KEY Keypad3`...) move it (`CMD CmdMove*` doesn't). A card shows the description, physical features, and a footer: **health** (Perfect, Wounded...), **difficulty for us** (Average...), and **attitude** (Hostile, Friendly). `KEY Escape` closes it. Mid-fight, Look tells how hurt the enemy is.
- **Melee:** `CMD CmdAttack<dir>`. Combat messages give the outcome with the roll in brackets: "You hit (x3) for 5 damage ... [9]", "misses you ... [3 vs 6]" (its roll vs our DV), "doesn't penetrate your armor ... [14]".
- **Adjacent hostiles strike when you step next to them** (the lover attacked as we arrived).
- **Kills give XP:** jilted lover, rated Average, +25 XP each. The quest-step arrival gave +50.
- The game is turn-based: nothing happens while the bot thinks or looks.
- **Resting:** `CmdWaitUntilHealed` healed 10→18 HP in about 40 turns. The game refuses to rest with a hostile in view ("...so you refrain from resting", a popup); step out of sight first.
- **Mobile enemies** (cave spider) can hover out of reach; waiting doesn't force them in, so close in. The spider bit twice a turn for 2 each and took about 10 damage to kill (+50 XP, twice a plant's).
- **Some plants grab** ("You are grabbed by a jilted lover!").
- The off hand attacks too ("You hit ... with your lit torch").
- Look mid-fight showed the progression Perfect → Wounded → Badly Wounded.
- **The fight routine** (`brain/scripts/fight.py`, explore arg `fight: true`, since 2026-11-24 afternoon) does what we did by hand. It fights kinds whose verdict in the world file is "fight" (attack when adjacent, otherwise one GOTO step), records kills, XP and hardest hits per kind, and rests after the fight. It raises the agent for: a new enemy kind, a kind marked avoid/ask, more than 2 hostiles, HP under 50%, a message that's neither ordinary combat text nor a known effect of the kind, a fight over 20 turns, and starting on an immobile target under 70% HP (rest first instead). Replaying last session's logged fights through it reproduced our hand-made decisions.
- Verdicts come from the LLM's Look assessment: `tools/world.py kind "<name>" fight difficulty=Average mobile=no effect="You are grabbed by"`. Kinds are keyed by name without state words ("wet giant centipede [wading]" → "giant centipede").
- **Danger zones** (2026-11-24): `world.threats(zone)` = hostiles last seen alive (kills mark them dead). Explore won't autoexplore within 12 of a live threat that is avoid/unassessed/ranged, rests only with no live threat within 15, and raises at once when shot from out of view ("hits you ... from the", "shooting at you"). Autoexplore itself still can't be steered mid-run: a per-step check would need the mod (a danger-cell list the begin-turn callback checks, interrupting autoact).
- **Ranged enemies** shoot from out of view and stop resting/waiting ("You stop waiting because something is shooting at you"). Kinds can carry `ranged` and their own `engage_hp_fraction`.
- **Auto-eat** (`brain/scripts/eat.py`, explore arg `auto_eat`): inventory → approved food line → Return → "eat" letter → dismiss, one key per call with each screen checked; up to `max_servings`; raises if no approved food or a screen looks wrong. Approved foods: `tools/world.py food add "<name>"`.
- **Healing:** witchwood bark ("Heals and confuses when eaten") took 8/18 to full at once. **Confusion scrambles names, even in the snapshot** ("Uherchuummuh"), so while confused the fight routine would see unknown kinds; it should raise (or wait) while confused rather than trust names.
- **Tool edits are queued** (`runs/<id>/edits.jsonl`): the live bot rewrites world.json every call and overwrote direct edits once.
- (Superseded note) First routine worth scripting later: a known, immobile, Average creature → step adjacent, attack, Look between blows, step away under half HP.

## Installed, waiting for the next restart (2026-11-24 afternoon)

- Background running: the mod now keeps Unity running in the background during runs and otherwise follows the game's own option **"Keep Caves of Qud active in background"** (Options → App Settings, needs advanced options; `OptionMusicBackground`). Before, it restored the startup value between runs, overriding that option.

- **Ignore the game's own input while unfocused:** with background running on, the Input System kept reading the keyboard globally, so typing in other windows reached the game as commands (user, 2026-11-24). A prefix on `GameManager.UpdateInput` skips it unless `Application.isFocused`; F1/F7/F8 also need focus.
- Display on a second screen: Unity in **Fullscreen** (`OptionDisplayFullscreen`, default on) isn't redrawn while another window has focus, regardless of runInBackground; use windowed mode.

## Items, quests and saving (2026-11-24)

- **Examine items before giving, selling or dropping them** (user): inventory → item → Return → "l) look" shows the description. We handed Argyve an unexamined "weird artifact" that might have been useful. Record what each item is in the world file.
- Quest turn-in: talk → "[give artifact]" → pick the item → "You have finished the step..." (+75 XP for Argyve's knickknack) → "You have completed the quest..." → Argyve offered a follow-up ("Fetch Argyve Another Knickknack").
- **Save and Quit saves anywhere** (confirmed 2026-11-24): quitting in the salt marsh at (4,7), turn 48540, while the checkpoint was "outskirts, Joppa", reloaded right there with the XP intact. So we can save in the field (system menu → s) before risky moves or restarts; checkpoints are only the fallback after a death.
- **Manual checkpoint:** `CMD CmdSystemMenu` → "k) Set Checkpoint" (in a settlement). The menu also has Restore Checkpoint, Save and Quit, Quit Without Saving. Raw Escape does nothing on the map; the menu needs the command.
- Brackish pools in the caves are salt water. The Elder offers Joppa's freshwater; the auto-pour (Amphibious) uses fresh water from the skins.

## Mod changes in v0.14 (installed 2026-11-24 15:48, loads on restart)

- Snapshot player: `food` and `water` (Stomach.FoodStatus/WaterStatus text) and `effects` (active effects by name). Python prefers these to reading the sidebar.
- Snapshot map: `features`, named terrain and features in view (pools with their liquid, furniture, plants; every terrain cell on the world map). Walls and things already in `objects` are left out. The world file keeps them per cell (`world.find_features(zone, "fresh water")`).
- Inventory/equipment names are full names ("lit torch", "waterskin [24 drams of fresh water]", "bear jerky [2 servings]").
- Also loaded with this restart (installed earlier): ignore game input while unfocused, F1/F7/F8 need focus, follow the "Keep active in background" option between runs.

Findings that led here: glyphs don't say what terrain is (`≈` in Argyve's hut was "strange furniture"; Joppa's `~` pools are "pool of 500 drams of salty water"); fresh water in Joppa isn't found yet; the sidebar was missing from a frame and auto-eat read that as "not hungry".

## Trade findings (2026-11-24)

- **Prices are in drams of fresh water** (`$`): the trade screen shows both inventories with prices and our balance ("$24").
- **Trade controls are named commands, not raw keys** (like the map): `CMD CmdTradeOffer` offers. "=" did nothing as a raw key; other commands: `CmdTradeAdd`, `CmdTradeRemove`, `CmdTradeAllItems`, `CmdTradeToggleAll`, `CmdVendorLook` (look at item), **`CmdVendorExamine` (ask the vendor to identify)**, `CmdVendorRepair`, `CmdVendorRecharge`. Raw digit keys do pick a quantity for the selected line ("0-9 Pick"). `RightArrow` switches to our column.
- Flow: talk → "Let's trade. [begin trade]" → select lines (digit = quantity) → `CmdTradeOffer` → "Tam will have to pony up 5 drams ... Agreed?" → `KEY y` → "Trade complete!".
- **Water viability:** Amphibious costs about 1 dram per 300 turns; 3 pieces of scrap sold for 5 drams (24 → 29). Food is nearly free (vinewafer $0.03). An unidentified "weird artifact" sells at $85.71 from Tam: artifacts are valuable; examine/identify before giving them away.
- **Rounding goes the merchant's way** (water comes in whole drams): selling 5.25 paid 5, buying 0.42 cost 1, so 0.83 drams lost in two trades. Combine buying and selling in one trade so only the net is rounded, aim purchases at whole drams, avoid tiny trades.
- **Inventory management stays with the LLM for now** (user, 2026-11-24): what to keep, sell, buy and when involves too many judgement calls (identification, value, rounding, weight) to script yet. Scripts only eat approved food.
- Open: the game window still doesn't redraw while unfocused, even with runInBackground on and the "Keep active in background" option (user: not the end of the world). Possibly the game skips drawing when it thinks it's unfocused; not pursued.

## Food findings (2026-11-24, wiki)

- Hunger levels: Sated → Hungry → Famished. **Hungry has no penalty; Famished costs 10 quickness.** Auto-eat now acts at Famished only.
- **Vinewafers are hydration, not satiation** (+500 hydration vs 10,000 per dram; no hunger value). Auto-eat had eaten them for hunger and stayed Hungry. Food is now approved per purpose; vinewafer removed from the hunger list.
- Snacks (bear jerky) give partial satiation; cooked meals at a campfire (Make Camp, owned; Meal Preparation, 0 sp) restore hunger fully. Butchery (owned) turns corpses into ingredients.

## Ability findings (2026-11-24)

- Abilities are used from `CMD CmdAbilities` (cursor to the line, `KEY Space`), which opens a **cell picker** (wait kind `picker`) whose top line names the ability: "Freezing Ray  Space-select | unlock (F8)". Escape cancels without spending a turn. Freezing Ray and Charge come **locked** ("unlock"); Teleport comes unlocked ("lock"), cursor on the player.
- **The lock is the game's current target, `XRL.UI.Sidebar.CurrentTarget`** (ShowPicker reads it; PlayerTurn sets it, e.g. when you attack). `brain/scripts/ability.py` drives the screens; `fight.py` uses Freezing Ray (2–9 cells, cooldown 20) and Charge (2–3 cells, cooldown 15) as openers. Teleport is never scripted (user: too dangerous; the LLM uses it only when death is otherwise near certain).
- First live test (salt marsh croc, turn 48387): no ability fired, because the safety rule "only creature in view" never held: harmless glowpads and a glowfish were in view. The routine still won in melee (21 → 14 HP, +75 XP). Fix: put the current target in the snapshot and fire only when it's our hostile.

## Pending mod changes (batch for the next restart)

- (installed as v0.15, 2026-11-24 ~16:20; loads on restart) Snapshot: `target` = `Sidebar.CurrentTarget` (name, x, y) when set and in the zone. The fight routine then uses targeted abilities only when the lock is on its hostile, regardless of other creatures in view. (Restart at the next settlement: a restart in the field loses everything since the last checkpoint.)

## Any run, not this run (rule, 2026-11-24)

The game is procedurally generated, and the bot has to play **any** run, not the current character or world.

- Scripts in `brain/` never contain coordinates, zone IDs, NPC or item names, or routes from a particular run. They take targets from the snapshot (objects in view, the quest log, messages, screen text) or from plan arguments the LLM fills in for the run at hand.
- Matching the game's own interface wording is fine ("[press space]", "anywhere else to explore", "[Accept Quest]"): it's the same on every seed.
- **Run-specific facts go in the run's world file**, `runs/<game id>/world.json` (`brain/world.py`). It's updated from every snapshot: zones, creatures and objects at their last known place, and the quest log. Notes go in by hand (`tools/world.py note`) or from scripts. Scripts may rely on it: "where did we last see the quest giver", "what's in this zone". `research/` keeps the mechanics and the reasoning.
- **Assume anything can be randomized** (user, 2026-11-24): creature types, abilities, item effects, costs. What we learn about a creature or item is a fact about *this run* (world file) until another run shows the same thing; only then does it become general knowledge in the scripts.
- **React to what's in front of us.** Seeing a monster starts an assessment (what it looks like, what the game says about it, our HP and gear), not a lookup. At first the LLM makes those calls in the remote loop, recording the outcome in the world file. Scripts take over the cases that turn out routine.
- We iterate with checkpoints: Roleplay mode saves on entering and leaving towns, and quitting or dying resumes from there. That lets us replay a situation and improve the rule rather than the run.
- The LLM narrates in the game with `SAY` lines ("Bot: heading north for the vermin quest"), so the player can follow its reasoning in the message log.

## Mod vs brain (rule, 2026-11-24)

The mod provides **mechanisms only**: read the game, push input, wait, log. Every **decision** lives in Python (`brain/`) or in `brain/bridge.json`, which the mod rereads whenever it changes. A fix to a decision then never needs a game restart. (Learned the hard way: "don't ask the brain while autoexplore runs" was in C#, froze the bot at a shrine popup, and cost a restart to fix.)

- `brain/bridge.json`: `ask_during_autoact` (default false: while the game's own automatic action runs on the map, the brain isn't asked), `max_calls_per_run`, `brain_timeout_ms`. Each reload is logged as a `config` line.
- Answers: `KEY`, `CMD`, `SAY`, `STOP <reason>`, `WAIT` (ask again soon), `PASS` (play nothing now, keep the run going).
- The snapshot carries `wait` (`map` or `key`) and `autoact` (the running automatic action, or null), so the brain can decide with the same facts the mod has.
- Still needs a restart: new snapshot fields, new hooks, control keys.
- **Don't hold the game thread on the map.** The hooks run on the game thread, which also draws the map, so a brain that keeps answering WAIT on the map freezes the display (the user tabbed in and saw it half-drawn, 2026-11-24). On the map, answer PASS after a short wait and let the game idle and redraw. Keep WAIT for popups and menus, which ask only once.

## Decision layers

1. **Scripts** (`brain/scripts/`) play many turns cheaply, one brain call per key wait.
2. **The plan** (`brain/plan.json`) picks the script and its arguments.
3. **The LLM** is called occasionally: when a script stops, or between runs. It reads the log, assesses, and edits both the plan and the scripts. Both levels keep improving over time.

## Not yet checked in game

- That F6 reaching the game is harmless on every screen.
- (Settled: raw Space closes `[press space]` popups, raw digits pick conversation options, raw arrows/keypad give Talk its direction and move the Look cursor, raw `y` answers Yes/No, raw letters move the inventory cursor; trade controls need commands.)
- What `CurrentBuffer` holds on each screen with modern UI off.

## In-game bot panel (2026-11-24)

- The mod draws live/panel.txt (written by brain/panel.py after every brain call: plan, stage, HP/level/XP, current action, last hand-off/stop, recent SAY lines) in a Unity IMGUI window over the game. F10 shows/hides it.
- Drag it anywhere inside; resize from the grip in the bottom-right corner. Place and size persist in live/panel_layout.json (delete it to reset). Kept on screen and at least 220x90.
- A click that starts on the panel (press, hold, release) or the wheel over it makes the UpdateInput prefix skip the game's input handling that frame, so it doesn't reach the map. Hovering alone doesn't block, so the keyboard still works with the mouse resting on it.
- Text that doesn't fit is clipped (no scrolling yet).

## Hunting non-hostiles (2026-11-24)

- The user's rule: non-hostile critters may be attacked too, as long as they don't look dangerous or important (no quest givers, named NPCs, members of other factions).
- How: the LLM marks a kind `prey` (`tools/world.py kind "bat" fight prey=yes`). With explore's `hunt` arg, the fight routine treats prey in view like hostiles, but only while HP is at least rest_fraction of max. Capitalised names (people) are never prey. Only set `hunt` away from settlements.
- Narration (SAY) now goes to the bot panel and live/narration.log only, not the game's message log (step.py SAY_TO_GAME_LOG).

## Looting (2026-11-24)

- The user's rule: note all items and grab them while carrying capacity isn't a problem.
- The game's own Autoget (Options.xml, defaults) already takes food, trade goods, nuggets, artifacts, scrap, ammo, fresh water, special items and weightless items while autoexploring; not books, primitive ammo, from adjacent cells, or with hostiles nearby. The actual settings haven't been read (only the defaults).
- brain/scripts/collect.py (explore arg `collect`): once the game says the zone has nothing left to explore, walk to each object the world file remembers in the zone and `CMD CmdGet` on its cell. Skips furniture, terrain, corpses and junk (SKIP regex) and kinds in world `loot` marked skip (learned automatically when a pickup fails); stops at `max_load` (0.8) of capacity from the sidebar "#cur/max". Not run live yet.
- Food with side effects (the dreadroot tuber terrifies) is fine to eat somewhere safe: auto-eat now also needs no hostile known alive within safe_radius (15).

## Bot panel log (2026-11-24, mod v0.17)

- Header (live/panel.txt) plus a scrolling log of live/narration.log: SAY lines, "!!" hand-offs/stops, "> " action changes (single steps left out). The mod keeps it scrolled to the newest line unless scrolled up; the wheel scrolls it.

## Economy: water, food and loot (2026-11-24)

- **Water use:** 28 drams at turn 48322 → 21 at 50049 (Amphibious pours it over us, plus 2 world-map steps): about **1 dram per 250 turns, ~4 per 1000**.
- **Food use:** hunger rises 1 per turn; Hungry below 0, Famished about 740 turns after Hungry (measured 2026-11-25; the wiki's −1200 didn't hold). A **snack** (starapple, jerky serving, lover's blossom) takes ~200 off; a **cooked meal** resets it. From full Sated (bark, turn 47539) to Famished took ~2500 turns (50075). Snacks at Tam's (starapple $0.29) cost ~1.5 drams per 1000 turns.
- **Total upkeep ≈ 5–6 drams per 1000 turns.**
- **Income:** nuggets have fixed values (copper $10, silver $50, gold $200; wiki). We carry 2 copper + 2 silver = **120 drams**, plus 3 books, a bronze ingot, a lover's blossom (tinkering ingredient), and stratum 3's floor items (weapons, armour). Scrap sold for 5 drams earlier. Loot outpaces upkeep many times over; the limits are **water capacity** (3 waterskins × 64 = 192 drams) and merchants' stock.
- **Butchery** (Butcher Corpses toggled on) has produced nothing so far: no butchering message in the logs. Unknown what triggers it (walking onto a corpse?).

## Cooking solves food (2026-11-24, turn 50999)

- Bought Cooking and Gathering (100; Meal Preparation came with it) and Harvestry (50). 60 SP left.
- **Make Camp** (ability, asks a direction for the fire) → interact with the campfire (`CmdGetFrom` + direction → campfire → Space → `c) cook`) → **`m) Whip up a meal`**: "You gather some fixings: a dram of water, ... You toss them in a pot and stir." → **Sated**, and **nothing was used up** (still 26 drams, 11 vinewafers, the starapple). A full meal for free wherever we can camp. Other campfire options: i) choose ingredients (meals with status effects), r) recipes, f) preserve fresh foods (vinewafer → 3 vinewafer sheaf).
- So food is no longer a reason to go back to town or to stockpile; snacks are only an emergency reserve (Famished blocks world-map travel).
- **Butcher Corpses** and **Harvest Plants** are toggles that act on what you move over ("You butcher corpses you move over"); autoexplore doesn't walk onto corpses, which is why butchery never happened. Watervines spawn ripe 1 in 20 and never ripen later (wiki); ripe ones are harvested when walked over.
- Gear bought from Tam (sold 3 books for $104.65 and the bronze ingot for $100; nuggets kept, $120): **chain mail** (AV 3, DV −1), **sturdy steel battle axe** (penetration 7, 1d3+1, can't break), **musket** (penetration 8, 1d8, low accuracy, 25 lb; "You reload your musket with a lead slug") with 47 lead slugs. Sold furs and the bronze axe for 4. Water 26 drams.
- Joppa's other traders: Nima Ruda (the elder's daughter, east door, (45,2)) sells herbs and medicine: bandages $2.86, yuckwheat stems $28.57, honey, a vinewood sap mask. Elder Irudad: "You may drink of our freshwater" (where: not found yet).
- **Camping rules (the user: be careful until we know better):** the basic meal is free by design and sates even when Famished; you can't camp or cook in combat (2017 patch notes); a lit campfire burns whatever is put on it (wiki). So `auto_cook` (brain/scripts/cook.py) cooks only at **Famished** (Hungry has no penalty; a meal lifts the meter only a little: Hungry again ~600 turns after one, with two world-map steps), only with no hostile in view and none known within safe_radius, and **puts the fire out** afterwards. Not yet run live end to end.
- **Harvesting:** no script. The Harvest Plants toggle takes ripe plants we walk over; a forum post says autoexplore routes over harvestables (unverified). Ripe plants are rare (watervine 1 in 20, never re-ripen). Check the logs for harvest messages before adding anything.

## Musket (2026-11-24, mod v0.18)

- `CMD CmdFire` opens the missile weapon's own picker, `MissileWeapon.ShowPicker` (not PickTarget's): it polls `Keyboard.kbhit` like the cell picker, so the mod now counts it as a picker (wait kind "picker"). Before that fix the bot was never asked inside it.
- The picker opens locked ("Space-select | unlock (F8)") on the nearest hostile; `KEY Space` fires. First shot: "You hit the giant amoeba (x3) with a lead slug for 22 damage! The giant amoeba dies!" (+25 XP; the turn counter didn't move). Then "[empty]"; `CMD CmdReload` reloads ("You reload your musket with a lead slug.").
- The fight routine fires when loaded and the target is the nearest hostile (a tie is fine: either is a target we're fighting), and reloads when empty with the target 2+ away (explore arg `missile`, default on).
- The mod's own notes (run started/stopped, step, report) now go to live/narration.log (the panel log), not the game's message log (from mod v0.18's next start).
- **Musket use policy (the user: don't spend ammo on what the axe kills easily):** shoot only kinds marked `shoot`, dangerous kinds (avoid, ranged, a hit of 5+, or 8+ in one turn), or when we're under 60% HP; never at what can't reach or shoot us; keep a reserve of 10 slugs (unless hurt). A shot or ray that hits something else (a wall: "You critically hit the shale") or a ray that drops back to the abilities list means no clear line: hold fire at that target for 10 turns.
- **XP is per creature, not per danger** (wiki): each creature has a base XP value, reduced as we out-level it (wiki: a level-21 creature gives full XP up to level 24), and in practice it shrinks well before that: a croc gave 75 at level 1 and 37 at level 5, feral dogs and a scavenger 5 at level 5 (corrected 2026-11-26). The giant amoeba is worth 25 (giant centipede 125), so its danger to us came from our low AV, not its level.
- **Verdict `ignore`** (2026-11-24): kinds left out of fights, stops, rest and cooking checks. Not used for the dreadroot after all (the user: hazards on the map should be killed, not ignored); it is `fight` + `harmless` (terror with only harmless kinds in view is waited out, up to 25 turns). The dreadroot's terror comes from its own aura when we're within ~3 cells, not from attacking or walking over it.
- **Shot from out of view** (2026-11-24): "A seed whizzes past from the northwest" / "hits you from the ..." now hands over to the LLM at the first such shot, with the direction if the game gives one; misses ("whizzes past") count. The old walk-toward-the-shooter search is gone (its code in explore.py is dead; corrected 2026-11-26). The direction comes in the hit message, not in "You stop exploring because ...". Creature names with extra prefixes ("slimy sappy salt-encrusted dreadroot") resolve to the longest known kind they end with (world.kind).
- **GOTO with no path** used to stop the whole run (the mod's stopReason). From mod v0.19 it plays nothing and reports `goto_failed` in the next snapshot; a WALK ends with "no path". Until the game restarts with v0.19, only WALK to explored cells.
- **Panel as a train of thought** (the user, 2026-11-24): header OBJECTIVE / GOAL / NOW / status, from plan.json's `objective` and `goal` fields (the LLM keeps them current). The log holds reasons, not commands: the scripts' SAY lines are phrased as why ("The musket is empty and nothing is around: reloading now..."), hand-offs read "!! Handing over to the LLM: ...", and the LLM writes its own decisions with `python tools/think.py "..."` (shown with "* ").
- **Voice narration** (built 2026-11-24, Windows SAPI; Anthropic has no TTS API): a channel separate from the panel log (the user: what's spoken needn't be what's written; only interesting notes, never over itself, never repeated).
  - `tools/narrator.ps1` (run in the background) speaks new lines of **live/voice.log** one at a time, skipping to the newest when behind, only while **live/voice_on** exists. Toggle: **F9** in the game (mod v0.19) or `python tools/voice.py on|off`.
  - Lines come from `VOICE <event>: <text>` in script answers (brain/voice.py filters them) and `python tools/say.py "..."` (the LLM). **brain/voice.json** (edit live) switches events on or off (llm, milestone, handoff, zone, engage, hurt) and sets repeat_turns (no line repeated within that many turns). Milestones (level-ups, quest steps) are taken from the game's messages.
  - Script lines today: entering a zone, first engaging a kind, a fight that leaves us under 60% HP, pausing to think (hand-offs other than zone explored / goal).
  - The script must stay ASCII: Windows PowerShell 5.1 reads BOM-less .ps1 files as ANSI.

## Reading armour during a fight (2026-11-24, after the Maggatum death)

- The user: knowing how hard a target is should come from the game, dynamically, not only from per-kind notes.
- From messages (no restart): track each creature's announced states ("tightens his carapace" / "carapace loosens", frozen, dazed, stuck in a frozen pool) and the share of our blows that "don't penetrate" it; choose weapon and timing from that (hit a loosened carapace, ray when shelled, walk away from a tightened one: it can't chase while tightened).
- From the mod (proposal, needs a restart): per-creature AV, DV, resistances, mutations and active effects in the snapshot. More than a player sees numerically (Look shows only a difficulty word).
- Carapace (wiki): AV bonus 3 + level/2, heat/cold resistance 5 + 5*level; tightening doubles the AV bonus at -2 DV while the creature stays still.
- **Menu macros** (`tools/menu.py`, 2026-11-24): `item "<name>" <action>` (inventory → item by name → menu action, popups read and dismissed; 3 s) and `trade <dir> --sell ... --buy NAME[:QTY] ... --examine NAME` (columns read once, cursor moves batched, totals and offer checked before `y`). send.py and macro.py refuse malformed lines (an empty KEY stops the run in the mod).

## Reloads hold the plan (2026-11-24)

F1 starts the brain on whatever brain/plan.json holds, and after a reload that is the plan from before
it (after the Maggatum death, explore re-ran Joppa at once and opened a resident's drawer). step.py keeps
the last turn it saw; when a snapshot's turn is lower (a reload), it holds the plan: the remote script
runs instead (the LLM decides), the panel and voice say "Game reloaded". Writing a new plan.json clears
the hold.

## Game knowledge vs world knowledge (2026-11-24)

The user: some knowledge is about the game and is shared between runs; some is about one world (seed)
and isn't. `brain/game_knowledge.json` is the only copy of the shared part: creature kinds and foods safe
to eat on our own. `brain/world.py` reads it on load and writes it back on save; `runs/<id>/world.json`
keeps places, people, sightings, notes, loot and quests, and no longer stores kinds or food.

Within a kind there are two sorts of fact. **Observations** (max_hit, max_turn_damage, xp, effects,
mobile, ranged, freeze_turns, notes) hold for any character. **Verdicts** (verdict, shoot, harmless,
difficulty from Look) are judgments for this build, level and gear (the user: what's dangerous changes a
lot with build, level and gear). Not an issue while run 2 copies run 1's build; a different build should
re-judge verdicts from the observations rather than trust them.

## Live threat estimate (2026-11-24, after run 2's level-1 death)

The user: all evaluations dynamic; work out mechanics before the fight, not after. `brain/threat.py`
compares turns-to-kill both ways from the live snapshot (creature hp/av/dv, our hp/av/dv, weapons) and
game knowledge of what each kind did to us. Rules read from the game's code:
- Penetration (XRL.Rules.Stat.RollDamagePenetrations): triplets of exploding 1d10-2 + min(bonus, cap)
  against the defender's combat AV; 1 success = 1 penetration, 3 successes = another triplet at bonus-2.
- Melee bonus (Combat.MeleeAttackWithWeaponInternal): weapon PenBonus + Strength modifier, capped at
  PenBonus + the weapon's MaxStrengthBonus.
- **The displayed PV is the capped bonus + 4** (RuleSettings.VISUAL_PENETRATION_BONUS, display only).
  The starting bronze battle axe ("→5") rolls +1: against AV 3 that's 1.1 penetrations of 1d2. The
  formula with -4 reproduces the logged multipliers (bronze 1.11 vs 1.15 seen, steel 1.95 vs 2.00).
- Enemies' weapons aren't visible: their effective bonus is solved from the mean multiplier they got at
  our AV then, and re-applied at our AV now.
- The game option DebugDamagePenetrations prints every penetration roll, if we ever need to check live.

fight.py hands over before and during a fight when the estimate says we'd lose: "kite" when the
creature also moves slower than us (mod v0.21 exports Speed and MoveSpeed), "too strong" otherwise. Kite
only when slower *and* dangerous (the user): anything we can beat is fought normally, so no waiting out
the ray's cooldown or spending slugs on easy kills. `trust_estimate: false` in the plan overrules it.
Backtest on the logs: the level-1 amoeba (16 turns vs 2: lose), dogs, snapjaws, crocs, lovers (win),
level-1 cave spider and level-5 guard dog (even: hand over).

## Blocked objectives: giving up and going elsewhere (sketch, 2026-11-24; not built)

The user, after Kamet met a 74-HP snapjaw hero camped at Red Rock stratum 2's stairs: when something
that strong stands in the way, the reasonable thing is to give up that quest for now and go elsewhere;
we don't know how to do that yet.

1. **Recognise a blocker.** The live estimate says we'd lose by a wide margin (not a close trade we can
   swing with ray, barks or position), it isn't slower than us (no kite), and it sits on the way on (the
   only stairs, the only exit), or it came back to camp there after we left.
2. **Record it as world knowledge** (the run's world file): which objective it blocks, where, the
   creature, and our level and the estimate at the time. Then re-estimate on each later visit instead of
   remembering "never".
3. **Choose elsewhere.** Leads we already collect: other quests and their hints (Argyve: "the surface of
   the marsh, the rust wells east, the Desert"), places noted on the way (ruins we declined, the
   Durqumish Sphere in run 1), unexplored world-map tiles near town. Rank by: safety of the trip (food,
   water, getting lost), what the quest givers said, and distance. The LLM makes the call; scripts only
   travel and explore.
4. **New skills this needs:** world-map exploration (step onto unknown tiles, read "you notice ...
   would you like to investigate?" prompts and accept them when healthy), and entering a site that isn't
   a quest location. We haven't practiced either.
5. **Come back** when a level-up or new gear changes the estimate (the fight routine re-judges anyway).

### Reading an enemy's offence (2026-11-24, after Yaun's death; mod v0.22)

Until now the snapshot held only a creature's defence (HP, AV, DV, resists), and its damage was learned
only from hits it had already landed: no use against a first meeting. The mod now also exports, per
creature: `diff` (the game's own difficulty word, DifficultyEvaluation.GetDifficultyDescription, what
Look's footer shows; level-based), `lvl`, `str`/`agi` (stat modifiers) and `attacks` (every wielded or
natural melee weapon: damage dice, PenBonus, MaxStrengthBonus, HitBonus, body part). threat.attacks_dpt
turns those into expected damage per turn against our AV and DV by the same rules as ours (best attack
in full, others a third: an assumption). Observations replace it once a kind has 3 attacks on record.
The fight routine also hands over when HP <= 2x the largest hit seen this fight (replayed on the
baboon: it stops at HP 9 after the first bite of 9).

## Confusion and safe waiting (2026-11-24, after Oshwoshwuur's death)

The user: confusion is extremely dangerous (it garbles our input); don't take multiple turns freely while
it's on unless sure nothing is happening. The scripts already stop ("confused with a hostile in view");
both deaths of this kind came from my hand-written loops. Rules:
- Every wait goes through `tools/wait.py` (one turn at a time; stops on any HP drop, a new or closer
  hostile, an adjacent one, a popup; while confused with anything in view, one turn at most). No
  hand-written wait or step loops during fights or bad effects.
- Witchwood bark heals fully but confuses: with other creatures around it means fighting confused, so it
  is a last resort there; prefer anything that heals without confusion.
- While confused, ability pickers may not lock onto the target (one aimed at ourselves): move the
  cursor to the target explicitly before confirming.

### Parts, descriptions and "find out" (2026-11-24, mod v0.23, after the tumbling pod)

The mod exports each creature's game parts (minus engine boilerplate) and its description text. Parts
named like BurstOnDeath, SplitOnDeath, ExplodeOnHit, AcidCorpseExplosion, DischargeOnDeath... say what it
does beyond melee. threat.estimate flags them (SPECIAL_PART) and reports the game's difficulty word. The
fight routine hands over once per kind with **"find out: ..."** when there are flags, or when the game
rates the creature Tough or worse while our estimate says easy. It's a prompt to learn (read the parts
and description, engage at range first, step away before a killing blow) rather than a ban (the user:
learning beats avoiding everything); `accept_kinds` lets the routine carry on once the LLM has decided.

### Loot and rooted enemies (2026-11-24, Shwyragaun)
- The explorer empties containers autoexplore opens ("Examining a ..." or "Opening a ..."): Take all.
- The early gear grab runs whenever nothing that can move is within 3 and nothing is adjacent (rooted
  things in view don't block it; the user: we stood on a pile with an iron long sword and skipped it).
- Rooted creatures get one world record per cell (seven dreadroots stay seven); a rooted record whose cell
  is in view without it is dead. Before a zone counts as done, the explorer walks back to any rooted kind
  we fight that's still alive (the user: we walked past two dreadroots to the stairs).
- **Books: read before selling** (the user): `tools/menu.py item "<book>" read`, then sell.

### Aiming with AIM x y (2026-11-24, mod v0.24)
Batched cursor keys in a target picker were dropped (a teleport aimed 18 east landed 10 west; another
"failed" with the cursor still on us). `AIM x y` makes the next cell picker (PickTarget.ShowPicker:
Teleport, rays, throwing, Move to) return that cell directly; the game still applies its own rules
(range, line of fire, the teleport's uncertainty radius). Use: send `AIM x y`, then the ability's keys
(CmdAbilities, its letter); no cursor keys and no confirming Space. Missile weapons have their own
picker (MissileWeapon.ShowPicker) and aren't covered yet.

### Food rules (the user, 2026-11-24)
No reason not to eat toward Sated while food is readily available, and camp to Sated whenever it's safe
while Hungry. cook.py now cooks at Hungry (not only Famished) when nothing hostile is near; eat.py eats
at Hungry while the pack holds more than 3 servings (always at Famished). A jerky serving is only a snack
(it moved us Hungry -> Famished -> Hungry), so camp meals are the main source.

### Level-ups hand over (the user, 2026-11-24)
The explorer stops at every level-up, once nothing hostile is in view, so the LLM reconsiders points
and plans then (not only at the goal level).

### Identify artifacts before giving or selling them (the user, 2026-11-25)
Two unidentified "weird artifact"s were both handed to Argyve blind (+75, +150 XP), though Tam prices
artifacts from $57 to $514. Unidentified, the game shows them all at the same price. Rule: before giving
or selling an artifact, get it identified (no Joppa trader has offered it: Tam "doesn't have the skill" and Argyve offered no identifying; trade's CmdVendorExamine with Argyve untried), or examine it
ourselves only when its loss wouldn't matter (an INT check; a failure can break it). Then give away the
least valuable one.

## Hand-overs and menu speed (2026-11-25)

**Stops hand over.** A script's STOP used to end the run, so the bot sat stopped while I waited for it
(the user: "so often its stuck on both sides"). Now brain/step.py turns a script's STOP (and "plan
finished") into a hold: the run stays live in the remote stage until plan.json is rewritten. Every
hand-over (a hold, or a NEXT into a remote stage) bumps live/handover.json; tools/watch_handover.py,
run in the background after giving the bot a plan, exits on that change (or when snapshots stop for
--idle seconds), which wakes the LLM. `--live` waits for a run to start (the user's F1). A STOP the LLM
sends itself still ends the run.

**Menu speed, measured.** A manual key cost ~0.33 s (Python start for send.py + a brain call of ~0.28 s
median; the brain's own work is ~50 ms), about the same as an explore step. Menus felt slow because
each key was one round trip and I recovered failures by hand. In the inventory, exactly 3 cursor keys
land from one answer (3, 5 and 8 sent all moved 3 rows; the rest are dropped, not delayed). So
tools/menu.py `select()` sends bursts of up to 3 and looks where the cursor went, correcting overshoot
(header rows can be skipped), searching up as well as down when the row is off screen. menu.py now calls
send.py's `play()` in process. A row ~10 down: ~1 s (was ~3-4 s). Moves: tools/walk.py (WALK) takes
~0.35 s a step, so use it for any move of more than one step instead of single CmdMove sends.

**Menu fixes.** `item` picks "e) equip (auto)" over "E) Equip (manual)" and reports only messages the
action produced (a failed equip printed "done" with older messages); `trade` works from an already open
trade screen; the camp meal counts · (dirt path, packed dirt floor) as free ground.

**Not unexplained (corrected the same day):** walking to Tam the game poured a dram of our water over us. That is the Amphibious defect, known since run 1 (research/character.md), which I failed to look up and called a mystery. Explained messages now live in game_knowledge.json "messages", and `tools/known.py <text>` searches it plus research/ before anything is called new.

**Red Rock's strata are not fixed (checked 2026-11-25).** Comparing run 1's and run Shwyragaun's
snapshots of "Red Rock, 3 strata deep" cell by cell: walls and floors agree on 151 of 234 shared cells
(no better at a one-column shift), about chance; stairs up at (12,24) in run 1, (16,5) now. I had first
told the user the layouts matched, from a map built as a union of both runs (the later run overwrote the
earlier, so the overlap matched by construction). Compare runs separately, never through a union.

**Careful exploring vs a roaming danger (2026-11-25, Red Rock stratum 3).** tools/frontier.py kept 12
cells from the Snapjaw King's last known spot, but that record was 1900 turns old and she was in the
arrival room, which we had explored; she came into view 3 cells off on the fourth leg. A mobile danger's
last position stops meaning anything after a while: treat it as anywhere, and keep an escape route (the
stairs) closer to us than to it. She followed us up the stairs (adjacent when we climbed) with a hunter
and five scavengers; our move rate (120 vs 100, Multiple Legs) outran the pack to the next stairs with no
damage. GOTO steps one per send (no walk stops) were the right tool for running.

**First live survey (2026-11-25, Shwyragaun).** tools/survey.py walked the 8 tiles around Joppa
(turns 435401 -> 438626, 9 world-map steps, 11 drams of water at one a step plus the time): no "notice
... investigate?" find, no popup, not lost. The world map's own features name only Joppa (11,22) and Red
Rock (11,20) within 4 tiles. Noticing hidden sites seems to be a chance per step, so one pass proves little,
and each pass costs water (Amphibious).

**Swallowed lines and kick-backs (2026-11-25).** Writing plan.json resets the stage memory, and the remote
script then counted the whole inbox as already played, so a WALK sent at the same moment was never
played; walk.py waited out its 300 s timeout ("stuck and failing to catch again?"). The played count now
lives in live/inbox_played.json, which plan changes don't touch; send.py waits on it. And tools kick back
instead of waiting (the user: observe that the game doesn't change when we expect it to): send.py
returns 3 after 8 s with no new snapshot, menu.py fails on that, and walk.py ends a walk as "stalled"
when turn and position haven't changed for 8 s.

**Hunger delay and healing in place (2026-11-25, the user).** Camping at the first "Hungry" was too
frequent: cook.py and eat.py now act at Hungry only after cook.REALLY_HUNGRY_AFTER = 450 turns in it
(Famished came about 740 turns after Hungry, measured; the 900 from the wiki was wrong), tracked per game in live/hunger.json;
Famished still acts at once. And mid explore-and-fight, a hurt character heals before going on unless a
hostile is adjacent: explore rests (CmdWaitUntilHealed) when nothing hostile is in view or known within
15, otherwise waits a turn at a time; the fight routine regenerates in place before walking to a target
that isn't coming (prey, or a hostile that stays put); explore's rest_fraction default is now 1.0, which
also means prey is hunted only at full HP.

**The bot's own no-progress failsafe (2026-11-25).** The explore stage sent CmdAttackW at a flying giant
dragonfly (prey) 40 times; the game ignored each one and no check noticed (the user: "another stuck that
has failed to be caught by every failsafe"). The kick-backs so far only covered my tools. Now
brain/step.py hands over when NO_PROGRESS_CALLS (6) answers in a row carry a game action while turn,
position, HP, wait state, last messages and (off the map) the whole screen stay the same; the LLM's own
remote stage is exempt. Flying prey is skipped until it lands. tools/watch_handover.py also wakes the LLM
as soon as the run stops (a brain crash, a key press), instead of after the idle timer. The crash itself
came from my half-finished edit of step.py (a constant used before it was added): edit in one go.

**Creature ids and hunting during explore (2026-11-25, mod v0.25).** The user: reference creatures by
id. The mod now exports the game's GameObject.ID for each creature (live after a game restart);
world.py keys creature records "zone|id:<id>" when there is one, so every glowpad is its own record, and a
death message marks only the one that just vanished from view. explore.py breaks off the game's
autoexplore when prey is in view within hunt_radius (12) and we're at full HP (ask_during_autoact is on,
but this never fired: checked 2026-11-26, the trace has no map call with autoact set in 8928 calls, so
the game doesn't consult the bot between autoexplore steps. Fixed in mod v0.26: explore writes
live/interrupt.txt every call (radius, then the prey kinds while hunting at full HP; step.py empties it in
any other stage), and the mod's begin-turn callback calls AutoAct.Interrupt once per creature per zone when
a listed kind is visible within the radius; each one is logged as kind autoact_interrupt in log.jsonl;
unverified live), and before
calling a zone done it walks back to prey records last seen alive (prey_max_walk 60 steps each; a cell in
view without it marks it moved).

**Ranged vs melee, and vetting (2026-11-25, Oshwoshwuur).** The hold ("let it come to me") was used on
a seed-spitting vine, which shoots and never moves: 18 -> 8 HP. The user: treat ranged and melee enemies
differently, and vet new logic like the wait-to-come against the suite of known enemies. fight.tactic():
hold = mobile melee (let it come), close = ranged (close in or open with an ability; never wait in its
line, and no regenerating in it), siege = rooted melee. A hit "hits you (xN) with <missile>" marks the kind
ranged (snapjaw hunters shoot wooden arrows: marked). tools/vet_fight.py runs fight.engage offline on every
kind in game_knowledge.json (logged sample stats or a stand-in), at distance 1 and 5, full and 40% HP, with
the abilities ready and on cooldown, and flags answers that break the tactic. Run it after every change to
the fight logic. Note: edit game_knowledge.json only through tools/world.py (the queue); a direct edit is
overwritten by the brain's next save.

**When a fight becomes the LLM's (2026-11-25, the user).** The routine now hands a fight over (and only
decides *when*; what to do is the LLM's judgment, played a turn at a time while it's chancy, batched when
it's decided, handed back when it's routine again):
- close fight: the estimate says we win but ttk_them / ttk_us > close_fight_ratio (0.45), for mobile or
  shooting hostiles (rooted melee is the siege's; prey is left alone), once per target;
- faster than expected: HP lost since the estimate > twice its per-turn damage and at least 4 or a
  quarter of max HP;
- a new enemy joins: a hostile id not in the fight before, within join_radius (6), not harmless.
Every such hand-over is appended to live/fight_handovers.jsonl with HP, the estimate and fight length,
to hone the thresholds (too eager = slow, too late = deaths). Vetted: tools/vet_fight.py 0 of 348 failing,
plus offline cases for each trigger.

## Fixes from Uumurem's retro (2026-11-26)

- **Charge** only from 3-4 cells (from 2 it failed every time with "no clear line"; from 4 it worked).
- **Stuck in a pool** (asphalt, sap): explore struggles free with moves towards the cell with the fewest
  pools (explore.free_direction) instead of taking "nowhere else to explore from here" as the zone done.
- **Weapon records are per character**: "weapons" is no longer shared game knowledge (the old pooled
  records stay in game_knowledge.json untouched); they live in each run's world.json, keyed
  "<name>#<item id>" once the mod sends ids (v0.27: `inventory_ids` and `equipped_ids`, parallel to the
  name lists), by name until then.
- **To-hit from the game's own rolls**: every one of our attack messages shows the roll with all bonuses
  ("[17]", "[2 vs 10]"); the weapon record keeps rolls/roll_n and threat.to_hit_bonus is the mean roll
  minus 10.5, blended (PRIOR_SWINGS) with Agility + a weapon-class proficiency from the profile (Axe or
  Cudgel Proficiency, +2). Replaces the hit/miss blend.
- **Hand-played swings are recorded**: the remote stage passes our attack messages to threat.observe
  with the one adjacent hostile as the target.
- **Gear check**: a missile weapon when the missile slot is empty gets a hand-over listing the ammo in
  the pack.
- **New liquids and features** (brain/features.py): each base liquid and each feature kind is evaluated
  once, ever ("liquid_kinds", "feature_kinds" in game knowledge; never the key "features", which is the
  world file's per-cell map features: a collision copied 3,507 of them out on 2026-11-26, repaired). New
  ones are said by explore and appended to every hand-over reason until recorded with
  `python tools/world.py evaluate liquid|feature "<kind>" "<note>"`; `world.py pending` lists them.
  Seeded: the liquids seen so far with verdicts, the feature kinds seen so far as mundane.
- Tests: tools/replay_tests.py (multiline matching; `known_bug` cases) and tests/unit_checks.py.

## After the Gemini/Antigravity handover (2026-11-26)

- **Feature kinds are world-neutral.** The game keeps capitals on proper names, so `feature_kind` ends
  the kind where one starts ("shrine to Nathritafa, the Cerulean Bane of Namritara" -> "shrine"). A name
  that is only a proper name is "named place". Passing states are dropped like the liquid mixers are
  ("frozen", "sap-and-blood-stained", "salt-encrusted"). The liquid test also matches "frozen deep pool of"
  and "painted vase [...]". Game knowledge's 63 feature kinds were re-keyed to 49: watervine and
  brinestalk variants merged, shrines merged, two frozen pools moved to the liquid water. World-specific
  detail goes in the run's world notes. Proper-name-only kinds evaluated before the fix
  ("duhummcalummmah"...) stay, because their original capitals weren't kept.
- **`tools/brief.py`**: the hand-over digest in one call, in the order of the decision-point checklist.
  Read-only, so it's safe with or without a run.
- **`--say` / `--think`** on send, walk and next_zone (`say.take_narration`): the narration plays before
  the action, in the same call. say.py and think.py are importable (`say()`, `think()`).
- **`tools/help.py`**: the tools index, generated from the docstrings. **`research/controls.md`**: the
  core moves (game shortcuts and tools), required reading.
