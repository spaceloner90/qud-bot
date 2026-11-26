# Qud bot: guide for agents

This is the single entry point for any agent (or person) working on this project. Everything needed
lives in this repo; nothing depends on an agent's private memory. "You" is the agent; "the owner" is
the person running the game and setting the goals. Read this file in full before acting, and again after
any loss of context (a compacted conversation is a lossy digest: it once dropped the route, the town
conversations and several rules, and a recording had to restart).

Also required reading, always: [`research/lessons.md`](research/lessons.md) (every standing lesson) and
[`research/game_facts.md`](research/game_facts.md) (facts and how-tos, known bot defects).

## What this is

A bot that plays Caves of Qud by reading the game and pressing keys. A thin C# mod (`mod/`) snapshots the
game at each key wait and plays the keys a Python brain (`brain/step.py`) answers. The brain runs the
plan in `brain/plan.json`: stages of scripts (`brain/scripts/`: explore, fight, cook, remote...) that
hand over to you whenever they meet something they shouldn't decide. You assess, decide, write the next
plan, play hard fights by hand, and keep improving both the plan and the scripts. Details and history of
every design choice: [`research/design.md`](research/design.md).

**Goal so far:** new characters with the same build (Mutated Human Marauder, Roleplay mode) taken to level
5 smoothly enough to record. The first recording is published (see the README); that character, Uumurem,
is held at level 5 on Red Rock stratum 4 and can be continued (`runs/9b6c18ef-.../recording.json`). The
owner sets each next goal.

## Ground rules

- **Don't launch the game yourself.** The owner starts and restarts it, creates characters, and presses
  F1 to start a run.
- **Find our own way.** No strategy guides or walkthroughs. The wiki is fine for mechanical questions
  (what an effect does, how a skill works).
- **Game code is read only for input/output hooks**, never for strategy or content. Decompiled code stays
  out of the repo.
- **The mod stays thin:** mechanisms only (read state, push input, wait, log). Decisions go in `brain/`
  Python or `brain/bridge.json`, which need no restart. Every mod change costs the owner a full game
  restart (a new game from the menu doesn't reload it): batch them, and add snapshot fields generously.
- **Any run, not this run.** The game is procedurally generated: scripts never hard-code coordinates, zone
  ids, names or routes. They work from the snapshot. Facts about one run go in its world file or research
  notes, never in scripts. Judge every creature from its live stats, not another character's verdict.
- **Never delete records**: logs, runs, retros, research notes. Correct in place, with a dated note.
- **Privacy:** keep the owner's personal details out of external requests and out of the repo. Machine
  paths go in the git-ignored `local/paths.json`. Before every push, scan what's being committed (email,
  names, usernames in paths, folder names) and commit with the GitHub noreply identity set in the repo's
  git config, not a personal email.
- **Stop at the owner's goal.** When the explicit goal is reached (e.g. level 5), finish the encounter you're
  in, then stop and hand over with a summary. Choosing the next goal is the owner's.
- **When things go badly** (sharp HP loss, near death, the same failure twice, a routine misbehaving):
  make the character safe, then stop and talk it through. Don't keep patching and pushing on.
- **Within a goal, decisions are yours**: points and skills (record the reasoning in
  `research/points_plan_<character>.md`), town trips, purchases, sequencing. Don't ask the owner which
  points to spend.

## Setup and controls

- Game setup: Options > UI > "Enable modern UI" off. The game's install folder is in `local/paths.json`
  (see the README); `tools/deploy_mod.ps1` compile-checks and installs the mod.
- In game: **F1** starts/stops a run, **F7** asks the brain once, **F8** writes a report, **F9** toggles
  the narrator voice (`live/voice_on`), **F10** the bot panel. The key that stops a run is swallowed.
- **Saving (Roleplay):** entering or leaving a town is a checkpoint; a death or a restart without
  Save and Quit reloads it. Save and Quit (system menu) saves anywhere. Checkpoint when progress is worth
  keeping and town is cheap to reach.
- Character creation is the owner's; the bot starts in the world.

## The working loop

1. Write `brain/plan.json` (label, objective, goal, stages). A plan rewrite is always picked up, even
   with identical text.
2. **Start `python tools/watch_handover.py` in the background every time** (`--live` while waiting for
   F1). It wakes you at a hand-over, a stop, a stall or a held plan. Never leave a plan running unwatched.
3. At a hand-over: read `live/state.json`, `live/narration.log` and the reason (it ends with
   "[new to evaluate: ...]" when new liquids or features are pending), run the decision-point checklist
   below, act, write the next plan, restart the watcher.
4. Drive by hand through the remote stage: `tools/send.py`, `tools/walk.py`, `tools/menu.py`,
   `tools/wait.py`, `tools/next_zone.py`. Read each tool's docstring before using it; never call one from
   memory.
5. Narrate while the voice is on (`live/voice_on`): `tools/say.py` for what you're doing and why,
   `tools/think.py` for decisions (the panel reads as a thought train: objective, goal, reasons, not
   commands). The rules are in `.claude/skills/narrate/SKILL.md`.

## At every decision point (hand-over, level-up, take stock, town visit)

Before deciding (lessons.md, "How to find the answers"):
- Anything new in view (creatures, liquids, features, items) evaluated? Record liquids and features with
  `python tools/world.py evaluate liquid|feature "<kind>" "<note>"`; creature kinds with
  `tools/world.py kind ...` (never edit `brain/game_knowledge.json` directly: the brain's save overwrites
  it).
- The whole inventory reviewed for what it could do now? The whole abilities list?
- In town: every shop's stock read and judged against the character (combat options, stats, survival),
  and the town's free resources used (a meal when hungry, rest, refills)?
- Driving by hand: the bot's background checks done (food, status, gear)?
- Does the screen stay readable for a viewer (light when exploring)?
- Before calling anything new or unexplained: `python tools/known.py "<text>"` searches what we know.
- Past runs' logs are for when you're stuck or diagnosing, not a checklist.

## Playing a fight yourself

- **One action per call, then re-read the board** (HP, every hostile's position and effects, cooldowns)
  until it's routine enough to hand back to the scripts. No loops of attacks or moves, no scratch
  kite/flee scripts, no multi-step walking mid-fight. If a repeated move is worth automating, it becomes
  a vetted tool first.
- Think it through as a player first (difficulty at this level, cooldowns, cover, escape); write the read
  with think.py. Strategy stays judgment: don't turn it into script rules.
- Engage hard fights at full HP with the opener (Freezing Ray) and Charge ready; ray first, melee second.
- Pursuers cross zone edges: out of sight isn't safe. Flee in one clear direction that avoids enemies.
- Terrain from the snapshot's `features`, not glyphs; never path through deep water.
- Heal at every break in contact, not mid-fight; bark-style heals that confuse are for when no enemy is
  near. Teleport only when death is otherwise near certain. Death near a checkpoint can be cheaper than
  burning every resource.

## Changing the bot

- After any change to fight or decision logic: `python tools/vet_fight.py` (every known enemy kind) and
  `python tools/replay_tests.py` (frozen states from real runs plus `tests/unit_checks.py`); both must
  show 0 failing. Prefer not to change code during a recorded run; fix what blocks, note the rest.
- New behaviour goes in `research/unvetted.md` until a live run shows it working.
- Before adding a key to shared game knowledge (`world.SHARED`), check the world files don't already use
  it. Editing pitfalls (shell heredocs mangling backslashes, PowerShell rewriting files, .ps1 must stay
  ASCII, compile before the bot runs it) are in game_facts.md.

## Retrospectives (after a run, never during a live run)

1. Timeline from the logs, what went well, what failed and why; check each failure against lessons.md and
   game_facts.md (regression or new?). Write `research/retro_<character>.md`.
2. Every lesson from the owner goes into lessons.md, phrased as a general way of finding the answer, not
   an item rule; every new game fact into game_facts.md. Nothing stays only in a conversation or an
   agent's memory.
3. For each bug or bad bot decision, freeze that turn's state from `live/log.jsonl` into
   `tests/fixtures/cases/` with a rule for the expected answer (see `tools/replay_tests.py`); a case for an
   unfixed bug gets `known_bug`. Incrementally, as needed.
4. Fix, vet, replay, document (design.md), commit.
5. Review your own fights at each take-stock: `python tools/fights.py --since <turn>`; log changes in
   `research/fight_reviews.md`.

## Where things are

- `research/playbook_level5.md`: the route and options that have worked (background, not a script).
- `research/retro_*.md`: one per character; `research/conversations.md`: how talking works, Joppa's people.
- `runs/<game id>/`: each character's world file, profile, and (for published runs) `recording.json`.
- `brain/game_knowledge.json`: knowledge shared by all runs (creature kinds, food, liquid and feature
  kinds); `tools/world.py` reads and queues edits to it.
- `live/` (git-ignored): the current session's snapshots, call log, narration and voice files.
