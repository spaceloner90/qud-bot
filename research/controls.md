# Core moves: how to do things in the game through the bot

Required reading from AGENTS.md (CLAUDE.md loads it). The game's own shortcuts and the bot's verbs, gathered
in one place on 2026-11-26. They were scattered across design.md, game_facts.md and the scripts, and an agent
starting fresh (Gemini, 2026-11-26) didn't know the game walks you to the nearest stairs itself. **Before
doing anything by hand step by step, check here whether the game or a tool already does it.** Tool flags:
`python tools/help.py` (generated from the docstrings). When you find a new shortcut, add it here.

## How the bot talks to the game

One brain call per key wait; the answer is lines (`brain/step.py`'s docstring has the full list):
- `CMD <command>`: a named game command (`CmdMoveN`...). **On the map this is the only way to act**: raw keys
  for bound actions are ignored, and one action per call (an action clears what's queued behind it).
- `KEY <key>`: a raw key, for menus, popups, prompts and pickers (`KEY y`, `KEY Escape`, `KEY Keypad3`).
- `GOTO x y`: one step of the game's own path towards a cell. `WALK x y` (remote stage, `tools/walk.py`):
  the whole walk, stopping for anything explore stops for.
- `AIM x y`: the next cell picker (abilities, throwing, Move to) returns that cell directly; then the
  ability's keys, no cursor keys and no confirming Space. Missile weapons have their own picker (not covered).
- `SAY` / `VOICE`: the panel log and the narrator. `WAIT` (ask again soon), `PASS`, `STOP`.
- `wait` in the snapshot says where the game is waiting: `map`, `key` (menus, popups, prompts), `picker`.
  Never press Space while it's `picker` (it selects a cell); Escape cancels it without a turn.

## Moving

| To do this | Use | Notes |
|---|---|---|
| **Go up or down a level** | `CMD CmdMoveD` / `CMD CmdMoveU` anywhere in the zone | Off the stairs the game asks "Would you like to walk to the nearest stairway down? [Yes] [No]" (or up): `KEY y` walks there with its own pathing, then the same command again takes the stairs. No need to find or walk to the stairs yourself. You arrive on the opposite stairs. |
| Go to the world map | `CMD CmdMoveU` on the surface | One world-map step (`CmdMoveN`...) is a parasang and costs 300 turns, plus water and a chance of getting lost. |
| Enter a world-map tile | `CMD CmdMoveD` | A town tile asks "a) Current location" or "b) Center": the town is the centre zone. |
| Walk to a zone edge | `CMD CmdMoveFarN` (S/E/W) | The game's pathing to that edge; walking off it enters the next zone of the parasang. `tools/next_zone.py` does edge, crossing and the next explore plan. |
| Walk to a cell | `tools/walk.py x y` | Stops for hostiles, HP loss, popups, shots from out of view. `tools/approach.py` walks next to a named creature. |
| Explore the zone | the explore script, or `CMD CmdAutoExplore` | Autoexplore won't move with a hostile in view. "Nowhere else to explore" can also mean stuck (tar, a web): try a move first. |
| Deep water | read `map.features`, not glyphs | Over 2000 drams is swimming (-50% move, +500 action cost); the game asks "Move again to enter it and start swimming". |

## Resting, waiting, healing

| To do this | Use | Notes |
|---|---|---|
| Rest to full HP | `CMD CmdWaitUntilHealed` | Refused with a hostile in view (a popup); hostiles out of sight can also block it. Step out of sight first. |
| Wait safely | `tools/wait.py --turns N` / `--until-clear <effect>` | Stops on any HP drop, popup or new hostile. Never wait in hand-written loops. |
| One turn | `CMD CmdWait` | |
| Eat, apply, equip, drop, look at an item | `tools/menu.py item "<name>" <action>` | By hand: `CMD CmdInventory`, the item's letter, then the action's letter. Space takes the default action (for food: eat). |
| A free meal | Make Camp, then the campfire's "Whip up a meal" | The cook script does it (`auto_cook`). Needs no Cooking skill; refused with hostiles nearby (even out of sight). Next to an old campfire, Make Camp offers to walk to it. |

## Fighting

| To do this | Use | Notes |
|---|---|---|
| Look at something (free) | `CMD CmdLook`, raw direction keys move the cursor | The card: description, health, difficulty for us, attitude. Escape closes it; a Look panel left open swallows commands. |
| Melee | `CMD CmdAttack<dir>` (N, NE, ... ) | Messages carry the rolls: "[17]" ours, "[2 vs 10]" theirs vs our DV. |
| An ability | `CMD CmdAbilities`, cursor to it, `KEY Space`; with `AIM x y` first for targeted ones | The list shows "[N turn cooldown]" while one cools; Escape out costs no turn. The fight script fires Freezing Ray and Charge itself. |
| Shoot | `CMD CmdFire`, `CMD CmdReload` | Reload in downtime. |
| Kill rooted enemies | `tools/kill.py <kind>` / `--rooted`; groups that never move: `tools/siege.py <kind>` | |
| Pick things up | `CMD CmdGet` on the item's cell (the collect script does it) | Several things there open "Select an item": the item's letter, "g) get", then Escape. |
| Use an adjacent object | `CMD CmdGetFrom` | How the cook script opens the campfire's menu. |

## People, trade, quests, saving

| To do this | Use | Notes |
|---|---|---|
| Talk | stand next to them, `CMD CmdTalk`, a direction key; options are digit keys | One key per screen: options change. Talking to anyone clears "lost". `research/conversations.md`. |
| Trade | `tools/menu.py trade <dir> --sell ... --buy ... --examine ...` | Trade controls are commands (`CmdTradeOffer`, `CmdVendorExamine` to identify...). Prices in drams of water; rounding goes the merchant's way. |
| The quest log | `CMD CmdQuests`; the snapshot's `quests` has it too | |
| Character sheet | `CMD CmdCharacter`; `tools/profile.py` records it | Run profile.py after every level-up. |
| Save | system menu (`CMD CmdSystemMenu`): Save and Quit saves anywhere; "k) Set Checkpoint" in a settlement | Roleplay: entering or leaving a town is a checkpoint; a death reloads it. |

## Reading the game without pressing anything

- `python tools/brief.py`: the hand-over digest (character, abilities and cooldowns, map, creatures with
  verdicts and estimates, items, features to evaluate, the whole pack, quests, messages, narration).
- `python tools/send.py` with no lines: the latest snapshot's map. `--screen`: the text screen.
- `python tools/known.py "<text>"`: what we already know about a message, creature or item.
