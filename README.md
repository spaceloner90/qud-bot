# Qud bot

A bot that plays Caves of Qud by reading the screen and pressing keys, with an LLM deciding the plan and playing the hard fights by hand at hand-overs. We work out our own way through the game: no strategy guides, only web searches for mechanical questions. The game's code is read only to find input/output hooks, never for strategy or content.

**Video:** [the first recording](https://www.youtube.com/watch?v=Fn8r-WRl4kI): a new character (Uumurem) from Joppa to level 5 through Red Rock, no deaths. Its run folder is `runs/9b6c18ef-2e3b-4573-99de-ed8d65ff19e8/` (`recording.json`, the world file and the character profile); the retrospective is [`research/retro_uumurem.md`](research/retro_uumurem.md).

Agents (and people) working on it start at [`AGENTS.md`](AGENTS.md): the ground rules, the working loop, and what to read.

This is an unofficial fan project, not affiliated with the game's developers. No game files or decompiled game code are included.

## How it works

- **`mod/`** is a Caves of Qud mod (C#, compiled by the game at startup, with Harmony patches). Before the game waits for a key, it can snapshot what the player sees (the 80x25 classic text screen with colours, plus player, zone and recent messages), run the brain, and put the brain's keys in the game's own key queue.
- **`brain/step.py`** is one brain call: snapshot in, key lines out. A new process runs per call, so brain edits apply on the next call with no restart.
- **`brain/plan.json`** is the top-level decision: which script to run, with which arguments. The LLM writes it after assessing the game, and also writes and refines the scripts.
- **`brain/scripts/`** are the routines that carry a plan out over many calls. They stop and hand back when they reach something they can't handle. So far: `explore` (the game's autoexplore, stopping at hostiles, popups, low HP, no progress, the turn budget or the goal; with `fight` it hands hostiles to `fight`), `fight` (routine melee against kinds the world file marks "fight"; raises the LLM for new enemies, low HP, unexpected messages, long fights), `remote` (the LLM sends keys live), `keys` and `idle`.
- **`runs/<game id>/world.json`** is the world file: what this run has shown us (zones, people and things at their last known place, quests, notes). Scripts may rely on it; `tools/world.py` shows it and adds notes.
- **`research/`** holds what we've learned: `lessons.md` (standing lessons), `game_facts.md`, `narrate.md`, `design.md` (the design and why), `playbook_level5.md`, the retros, and `unvetted.md` (changes not yet seen working in a live run).

The loop: the player presses **F1** in game, the bot plays until a script stops, and then the LLM reads `live/log.jsonl`, reassesses, and updates the plan and the scripts.

## Controls (in game)

Needs **Options > UI > Enable modern UI** turned off (it shows when advanced options are on). With modern UI on, many screens don't read keys through the queue the bot uses.

- **F1** runs: the brain is asked at every key wait until it says STOP, or you press any key. (F1 is the game's Help key; the mod swallows it, and Help stays on `?`.)
- **F7** asks the brain once and plays its answer.
- **F8** writes the snapshot and logs it, without playing anything. The confirmation goes to the in-game message log, so it doesn't show on menus.

With `brain/plan.json` set to the `remote` script, a run started with F1 plays whatever the LLM sends with `tools/send.py` (one line per key), and answers WAIT while nothing new has been sent.

## Files

- `live/` holds output from the current session: `state.json` and `screen.txt` (latest snapshot), `log.jsonl` (every call), `memory.json` (script memory).
- `tools/deploy_mod.ps1` compile-checks the mod and installs it in the game's Mods folder. `tools/dump_types.ps1` dumps the game's type signatures, or IL with `-IL -Filter`, to `research/`.
- `tools/analyze.py` turns the log into a findings report (progress, stops, zones, creatures, objects, quests, gear, messages), printed and written to `live/findings.md`. `--last-run` or `--since <seq>` narrow it.
- `tools/send.py` sends lines to a remote run and prints the resulting map, or the latest snapshot when given no lines.
- `tools/win.py` is the raw window capture/keys test from the first session. It is unreliable with the game in the background.
- `research/design.md` explains the design and why.

## Running it

Set up for one Windows machine. The game's install folder goes in `local/paths.json` (git-ignored), read by `tools/game_dir.ps1`; without it, `$env:QUD_GAME_DIR` or the usual Steam folder is used:

```json
{"game_dir": "D:\\Games\\Caves of Qud\\game"}
```

`tools/deploy_mod.ps1` compile-checks the mod against the game's DLLs and installs it, writing this folder's path into the installed copy. Needs Python 3.11 and the .NET compiler that ships with Windows.

Offline checks, run after any change to the bot's logic:

```bash
python tools/vet_fight.py       # every known enemy kind, several distances and HP levels
python tools/replay_tests.py    # frozen game states from real runs, plus tests/unit_checks.py
```
