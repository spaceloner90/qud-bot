"""One brain call: the mod pipes the game snapshot (JSON) in, and reads the answer lines out.

Answer lines:
  KEY <key>      press a key: "a", "A", "Escape", "Return", "Keypad8", "ctrl+s", "shift+Tab"...
  CMD <command>  push a named game command, e.g. CmdMoveN, CmdWait. On the map this is the
                 only way to act (raw keys for bound actions are ignored), and it is one action per
                 call: an action clears whatever is queued behind it.
  SAY <text>     a line in the bot panel's log (live/narration.log)
  VOICE <text>   a line for the narrator's voice (live/voice.log), separate from the panel log
  STOP <reason>  end the run (the keys above are still played)
  GOTO <x> <y>   one step towards that cell of the current zone, along the game's own pathfinding
                 (the step is played as a CmdMove command; stops the run if there's no path)
  WAIT           nothing yet: ask again soon (the remote script uses this)
  PASS           play nothing now, but keep the run going

Mod settings (when to ask, call limits, timeouts) are in brain/bridge.json, reread on change.

What to do comes from brain/plan.json, which names a script in brain/scripts/ and its arguments.
That file is where top-level decisions go; scripts are the routines that carry them out over many
calls. A new process runs per call, so anything to remember between calls goes in `memory`, which
is saved to live/memory.json. Changing the plan resets memory.
"""
import importlib, json, sys, traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "brain" / "plan.json"
MEMORY = ROOT / "live" / "memory.json"
SAY_TO_GAME_LOG = False
NO_PROGRESS_CALLS = 6  # identical answers with nothing changing in the game before handing over
IDLE_WAIT_CALLS = 25  # waits in a row at full HP with nothing hostile in view before handing over
PACE_CALLS = 12  # step answers in a row on at most two cells (while turns pass) before handing over
sys.path.insert(0, str(ROOT / "brain"))


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


HANDOVER = ROOT / "live" / "handover.json"


def pacing(memory, state, acts, in_remote):
    """The pacing failsafe: a reason to hand over when the last PACE_CALLS step answers (GOTO, CmdMove)
    all landed on at most two cells while game turns passed, else None. Any other kind of answer resets
    it. Only scripts' answers count, not the LLM's remote stage."""
    steps = [l for l in acts if l.startswith(("GOTO", "CMD CmdMove"))]
    if not steps:
        memory.pop("_trail", None)
        return None
    if in_remote or state.get("wait") != "map":
        return None
    p = state.get("player") or {}
    trail = (memory.get("_trail") or [])[-(PACE_CALLS - 1):] + [[p.get("x"), p.get("y"), state.get("turn") or 0]]
    memory["_trail"] = trail
    cells = {(c[0], c[1]) for c in trail}
    if len(trail) >= PACE_CALLS and len(cells) <= 2 and trail[-1][2] > trail[0][2]:
        memory.pop("_trail", None)
        return (f"pacing: {PACE_CALLS} steps between {' and '.join(map(str, sorted(cells)))} over "
                f"{trail[-1][2] - trail[0][2]} turns")
    return None


def signal_handover(state, reason):
    """Mark a hand-over for the LLM: tools/watch_handover.py (run in the background) exits on a change,
    which wakes the LLM."""
    try:
        n = load_json(HANDOVER, {}).get("n", 0) + 1
        # Every hand-over carries the liquids and features still to evaluate (features.py, 2026-11-26),
        # so they're in front of the LLM at each decision point until it records a verdict.
        try:
            import features, world as _world
            reason = reason + features.pending_text(_world.CURRENT)
        except Exception:
            pass
        HANDOVER.write_text(json.dumps({"n": n, "turn": state.get("turn"), "reason": reason}), encoding="utf-8")
    except Exception:
        sys.stderr.write(traceback.format_exc())


def hand_over(memory, state, reason):
    """Hold the plan in the remote stage until plan.json is rewritten, instead of ending the run."""
    memory["_hold"] = reason
    memory["_stage"], memory["stage"] = 0, {}  # the hold plan is the remote stage alone
    signal_handover(state, reason)
    return [f"SAY !! Stopped: {reason}", "SAY Over to the LLM for a decision (the run stays live).",
            "VOICE handoff: Pausing to think: " + reason.split(":")[0] + "."]


def keep_asking(lines, state):
    """Nothing to play: PASS on the map, WAIT off it. The same for any script's own PASS (explore, cook and
    eat answer PASS in places): off the map, with nothing played, it becomes WAIT so the mod keeps asking."""
    if not lines:
        lines = ["PASS" if state.get("wait") == "map" else "WAIT"]
    if state.get("wait") != "map" and not any(l.split(" ", 1)[0] in ("KEY", "CMD", "GOTO", "STOP", "AIM", "WAIT") for l in lines):
        lines = [l for l in lines if l != "PASS"] + ["WAIT"]
    return lines


def plan_changed(memory, plan_key, plan_mtime):
    """A new plan: different text, or plan.json rewritten since (even with the same text)."""
    return memory.get("_plan") != plan_key or (plan_mtime is not None and memory.get("_plan_mtime") not in (None, plan_mtime))


def main():
    state = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    plan = load_json(PLAN, {"script": "idle"})
    memory = load_json(MEMORY, {})
    plan_key = json.dumps(plan, sort_keys=True)
    last_turn = memory.get("_last_turn", 0)
    last_game = memory.get("_last_game")
    # A rewrite of plan.json is a new plan even when its text is the same (2026-11-26: re-sending an
    # identical plan after a hand-over left the run held in the remote stage, passing for minutes).
    try:
        plan_mtime = PLAN.stat().st_mtime
    except OSError:
        plan_mtime = None
    if plan_changed(memory, plan_key, plan_mtime):
        memory = {"_plan": plan_key}
    memory["_plan_mtime"] = plan_mtime
    # A reload rewinds the game, but plan.json still holds the plan from before it (the user,
    # 2026-11-24: confusing that a restart acts at once without the brain hooking in). So when the
    # turn goes backwards, the plan is held and the run waits for the LLM (the remote script) until
    # plan.json is rewritten for the reloaded game.
    turn = state.get("turn") or 0
    # A different game id is a new character (the user, 2026-11-24: the bot takes over a new character
    # with an intro as soon as we're in); a lower turn in the same game is a reload. Both hold the plan.
    game_id = (state.get("game") or {}).get("id")
    new_game = bool(game_id and last_game and game_id != last_game)
    reloaded = not new_game and turn < last_turn
    if new_game:
        memory = {"_plan": plan_key, "_hold": f"new game {game_id}"}
    elif reloaded:
        memory = {"_plan": plan_key, "_hold": f"reloaded: turn {last_turn} -> {turn}"}
    memory["_last_turn"] = turn
    if game_id:
        memory["_last_game"] = game_id
    if new_game or reloaded:
        signal_handover(state, memory["_hold"])
    if memory.get("_hold"):
        plan = {"script": "remote", "args": {"poll_seconds": 10, "map_poll_seconds": 1},
                "objective": plan.get("objective"), "goal": plan.get("goal")}

    # The world file for this run: updated from every snapshot, readable by scripts as world.CURRENT.
    import world
    try:
        world.CURRENT = world.load(state)
        world.CURRENT.update(state)
    except Exception:
        world.CURRENT = None
        sys.stderr.write(traceback.format_exc())

    # A plan is one stage ({"script": ..., "args": ...}) or a sequence ({"stages": [stage, ...]}).
    # A script ends its stage by answering "NEXT <reason>"; the next stage then runs at once, with
    # fresh memory. After the last stage, NEXT stops the run.
    stages = plan.get("stages") or [plan]
    lines = []
    # A Look panel left open swallows every command while the snapshot still says "map" (2026-11-24: the
    # bot sent CmdWait for minutes and no turn passed). Its footer is "└<health>───<difficulty>, <attitude>─┘".
    import re as _re
    rows_text = "\n".join((state.get("screen") or {}).get("rows") or [])
    if state.get("wait") == "map" and _re.search(r"└(Perfect|Fine|Injured|Wounded|Badly Wounded|Dying)─+[A-Za-z ]+, (Friendly|Hostile|Neutral)─┘", rows_text):
        sys.stdout.buffer.write(("SAY A Look panel was left open; closing it.\nKEY Escape\n").encode("utf-8"))
        MEMORY.parent.mkdir(exist_ok=True)
        MEMORY.write_text(json.dumps(memory, indent=1), encoding="utf-8")
        return
    if new_game:
        name = (state.get("player") or {}).get("name") or "a new character"
        zone = (state.get("player") or {}).get("zoneName") or "the world"
        lines += [f"SAY New character: {name}, in {zone}. The goal: level 5. Waiting for the LLM to take over.",
                  f"VOICE milestone: A new character, {name}, steps into {zone}. The goal: level five. First, a look around."]
    if reloaded:
        lines += [f"SAY The game was reloaded (turn {last_turn} back to {turn}); holding the old plan until the LLM writes a new one.",
                  "VOICE handoff: Game reloaded. Holding the old plan and waiting for a decision."]
    try:
        while True:  # ends: each pass either breaks or moves to a later stage
            index = memory.get("_stage", 0)
            if index >= len(stages):
                lines += hand_over(memory, state, "plan finished")
                break
            stage = stages[index]
            if stage.get("script") != "explore":
                # Autoexplore interrupts (live/interrupt.txt, read by the mod) belong to explore alone.
                try:
                    from scripts import explore as _explore
                    _explore.clear_interrupts()
                except Exception:
                    sys.stderr.write(traceback.format_exc())
            script = importlib.import_module("scripts." + stage.get("script", "idle"))
            answer = list(script.act(state, memory.setdefault("stage", {}), stage.get("args", {})))
            stop = next((l for l in answer if l.startswith("STOP")), None)
            if stop and stage.get("script") != "remote":
                # A script's STOP used to end the run, leaving both sides stuck (the user, 2026-11-25:
                # the hand-over must trigger when these things happen): the run stays live, held in the
                # remote stage, and the LLM is signalled. A STOP the LLM itself sends still ends the run.
                lines += [l for l in answer if not l.startswith(("STOP", "NEXT"))]
                lines += hand_over(memory, state, stop[4:].strip())
                break
            done = next((l for l in answer if l.startswith("NEXT")), None)
            if done is None:
                lines += answer
                break
            memory["_stage"] = index + 1
            memory["stage"] = {}
            if index + 1 < len(stages) and stages[index + 1].get("script") == "remote":
                signal_handover(state, done[4:].strip())
            lines.append(f"SAY Stopping {stage.get('script')}: {done[4:].strip()}")
            full = done[4:].strip()
            reason = full.split(":")[0]
            if not reason.startswith(("zone explored", "goal")):
                # A few words of the detail too ("popup, your health has dropped below 40%"), without
                # screen clutter.
                import re as _re
                detail = _re.sub(r"[^A-Za-z0-9 ,.%'-]+", " ", full[len(reason) + 1:]).split()
                words = [w for w in detail if len(w) > 1 or w.isdigit()][:8]
                lines.append(f"VOICE handoff: Pausing to think: {reason}" + (", " + " ".join(words) if words else "") + ".")
    except Exception:
        err = traceback.format_exc().strip().splitlines()[-1]
        sys.stderr.write(traceback.format_exc())
        # A script that fails (a half-done edit, 2026-11-27: a NameError stopped the run and the owner had
        # to press F1) holds the run in the remote stage and wakes the LLM, rather than ending it. The
        # remote stage failing too is the one case left that stops.
        failed = (locals().get("stage") or {}).get("script")
        if memory.get("_hold") or failed in (None, "remote"):
            lines = ["STOP brain exception: " + err]
        else:
            lines = hand_over(memory, state, "brain exception: " + err)

    # No-progress failsafe for every script but the LLM's own remote stage (the user, 2026-11-25: a stuck
    # bot must be caught by observing that the game doesn't respond): the same game action answered again
    # and again while turn, position, HP, screen and messages stay the same means the game is ignoring it
    # (CmdAttack at a flying dragonfly, 40 times). Hand over instead of repeating it.
    acts = [l for l in lines if l.split(" ", 1)[0] in ("KEY", "CMD", "GOTO")]
    in_remote = memory.get("_hold") or (stages[min(memory.get("_stage", 0), len(stages) - 1)].get("script") == "remote")
    if acts and not in_remote:
        p = state.get("player") or {}
        sig = json.dumps([state.get("turn"), p.get("x"), p.get("y"), p.get("hp"), state.get("wait"),
                          (state.get("messages") or [])[-3:], ((state.get("screen") or {}).get("rows") or []) if state.get("wait") != "map" else None])
        same = memory.get("_same") or {}
        n = same.get("n", 0) + 1 if same.get("sig") == sig else 0
        memory["_same"] = {"sig": sig, "n": n}
        if n >= NO_PROGRESS_CALLS:
            memory.pop("_same", None)
            lines = [l for l in lines if l.startswith(("SAY", "VOICE"))] + hand_over(
                memory, state, f"no progress: {n} answers ({acts[0]}) and the game hasn't changed")
    else:
        memory.pop("_same", None)
    # Pacing failsafe, the same idea for walking: game turns pass, but the steps keep landing on the same
    # two cells (2026-11-27: a fight target and a gear walk took turns, and the fight routine's own pacing
    # check didn't see the gear steps; earlier a fight flip-flop ran 40 turns). Only step answers count.
    why = pacing(memory, state, acts, in_remote)
    if why:
        lines = [l for l in lines if l.startswith(("SAY", "VOICE"))] + hand_over(memory, state, why)
    # Idle failsafe: waiting turn after turn at full HP with nothing hostile in view is waiting for
    # nothing (2026-11-25: a "stay" hold went on 150 turns after the croc died; the user: never assume
    # enemies will do something without safeties and wake-ups). Hand over after IDLE_WAIT_CALLS.
    waits_only = acts and all(l.strip() in ("CMD CmdWait", "CMD CmdWait20") for l in acts)
    pl = state.get("player") or {}
    calm = (pl.get("hp") or 0) >= (pl.get("maxhp") or 1) and not any(
        o.get("hostile") for o in (state.get("map") or {}).get("objects", []) if o.get("creature"))
    if waits_only and calm and not in_remote:
        memory["_idle"] = memory.get("_idle", 0) + 1
        if memory["_idle"] >= IDLE_WAIT_CALLS:
            memory.pop("_idle", None)
            lines = [l for l in lines if l.startswith(("SAY", "VOICE"))] + hand_over(
                memory, state, f"idle: {IDLE_WAIT_CALLS} waits at full HP with nothing hostile in view")
    else:
        memory.pop("_idle", None)

    try:
        import panel
        panel.update(state, plan, memory, lines)
    except Exception:
        sys.stderr.write(traceback.format_exc())
    # Narration goes to the bot panel (and live/narration.log) only, not the game's message log
    # (the user's call, 2026-11-24). SAY plays nothing, so dropping it changes no action.
    if not SAY_TO_GAME_LOG:
        lines = [l for l in lines if not l.startswith("SAY ")]
    # The voice channel is separate from the panel log (the user, 2026-11-24: what's spoken needn't be
    # what's written): VOICE lines go to live/voice.log, read aloud by tools/narrator.ps1 when on.
    try:
        import voice
        voice.emit(state, [l[6:].strip() for l in lines if l.startswith("VOICE ")])
    except Exception:
        sys.stderr.write(traceback.format_exc())
    lines = [l for l in lines if not l.startswith("VOICE ")]
    # Nothing left for the game (only narration, e.g. cook.py's "Ate a cooked meal"): an empty answer
    # stops the run in the mod ("the brain gave no keys", 2026-11-24), so keep it going.
    # Off the map it must be WAIT, not PASS: a popup asks only once, so a PASS there handed control back
    # to a game that never asked again (2026-11-26: "There's nothing to take." after collect's "Did not
    # get" line sat for minutes, and no failsafe saw it because the brain was never called again).
    lines = keep_asking(lines, state)

    if world.CURRENT is not None:
        try:
            world.CURRENT.save()
        except Exception:
            sys.stderr.write(traceback.format_exc())

    MEMORY.parent.mkdir(exist_ok=True)
    MEMORY.write_text(json.dumps(memory, indent=1), encoding="utf-8")
    # The mod reads UTF-8; the Windows default (cp1252) can't write box characters and crashes.
    sys.stdout.buffer.write(("\n".join(lines) + "\n").encode("utf-8"))


if __name__ == "__main__":
    main()
