"""The LLM drives directly: plays answer lines appended to live/inbox.txt, in order.

With nothing new in the inbox:
- on the map it waits up to `map_poll_seconds`, then answers PASS. The mod returns to the game, which
  redraws and idles, then asks again. (Holding the game in the hook while waiting froze the display:
  the game thread that draws the map is the one the hook runs on.)
- in a popup or menu it waits up to `poll_seconds`, then answers WAIT: a popup asks only once, so
  the mod has to keep asking inside the hook.
tools/send.py appends lines and prints the screen that results.

args: {"poll_seconds": 10, "map_poll_seconds": 1}
"""
import json, re, time
from pathlib import Path

INBOX = Path(__file__).resolve().parents[2] / "live" / "inbox.txt"
ACTIONS = {"KEY", "CMD", "GOTO", "STOP", "WAIT", "PASS"}


PLAYED = INBOX.parent / "inbox_played.json"


def played_count():
    """Inbox lines already played (live/inbox_played.json); the first time, everything there now counts
    as old, so nothing from before is replayed."""
    try:
        return json.loads(PLAYED.read_text(encoding="utf-8"))["done"]
    except (FileNotFoundError, ValueError, KeyError):
        n = len(read_inbox())
        save_played(n, None)
        return n


def save_played(done, seq):
    PLAYED.write_text(json.dumps({"done": done, "played_at_seq": seq}), encoding="utf-8")


def read_inbox():
    try:
        return [l.strip() for l in INBOX.read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    except FileNotFoundError:
        return []


# A walk pauses for everything exploring pauses for (the user, 2026-11-25: walking blindly into danger has
# killed us before): the checks are explore's own, imported, so the two can't drift apart.
DANGER_RADIUS = 12  # explore's default danger_radius
# Starting to burn, stick, be poisoned or bleed; not "You stop bleeding" / "You take no damage from
# bleeding" (2026-11-25: both stopped walks for nothing).
FIRE = re.compile(r"catch fire|on fire|are burning|You are stuck|You are poisoned|You begin bleeding|You are bleeding|You start bleeding", re.I)


def threats_near(state):
    """{record key: distance} for hostiles the world file knows alive within DANGER_RADIUS (explore's
    known_threats), which may be out of view."""
    from scripts import explore
    return {f"{c['name']}@{c['x']},{c['y']}": d for c, d in explore.known_threats(state, DANGER_RADIUS)}


def walk_check(state, w):
    """Why a WALK should end now, or None to keep stepping."""
    from scripts import explore, fight
    p = state.get("player") or {}
    if state.get("goto_failed"):
        return "no path (" + state["goto_failed"] + ")"
    if state.get("wait") != "map":
        return "a popup or menu opened"
    if p.get("zone") != w["zone"]:
        return "the zone changed"
    if p.get("hp") is not None and p["hp"] < w["hp"]:
        return f"HP dropped to {p['hp']}"
    new = fight.new_messages(state, w.setdefault("seen", {}))
    shot = [m for m in new if explore.UNDER_FIRE.search(m)]
    if shot:
        return "under fire from out of view: " + shot[-1][:120]
    hurt = [m for m in new if FIRE.search(m)]
    if hurt:
        return "message: " + hurt[-1][:120]
    bad = [e for e in p.get("effects") or [] if e in explore.BAD_EFFECTS]
    if bad:
        return "effect: " + ", ".join(bad)
    import world as _w
    hostiles = [o for o in (state.get("map") or {}).get("objects", []) if o.get("creature") and o.get("hostile")
                # WALK x y <kind>: walking up to a rooted target to kill it (tools/kill.py), that kind doesn't stop us
                and not (w.get("ignore") and _w.kind_name(o["name"]) == w["ignore"])]
    # Hostiles already in view when the walk began don't stop it while they stay put and we don't get
    # closer (2026-11-25: walking away from glowpads that never leave their pool stopped every step);
    # a new one, one that moved, or getting nearer does (as tools/wait.py).
    me = (p.get("x", 0), p.get("y", 0))
    start = w.get("hostiles_at_start") or {}
    for o in sorted(hostiles, key=lambda o: max(abs(o["x"] - me[0]), abs(o["y"] - me[1]))):
        key, d = f"{o['name']}@{o['x']},{o['y']}", max(abs(o["x"] - me[0]), abs(o["y"] - me[1]))
        # A rooted melee kind 2+ cells off can't touch us (2026-11-25: a glowpad in its pool stopped the walk
        # to the zone edge, and the run sat there); only one next to us, or a shooter, matters.
        kd = (_w.CURRENT.kind(o["name"]) if getattr(_w, "CURRENT", None) is not None else None) or {}
        if kd.get("mobile") is False and not kd.get("ranged") and d >= 2:
            continue
        # Aquatic ones (glowfish) keep to their water: 2+ cells off they don't stop a walk either (2026-11-25:
        # a pool full of glowfish stopped every walk out of the zone).
        if "Aquatic" in (o.get("parts") or []) and not kd.get("ranged") and d >= 2:
            continue
        if key not in start or d < start[key] or d <= 1:
            return f"hostile in view: {o['name']} at ({o['x']},{o['y']})"
    # Known dangers out of view: one that wasn't within the radius when the walk began, or that we're
    # now closer to than then (walking towards it).
    for k, d in threats_near(state).items():
        if k not in w.get("threats", {}) or d < w["threats"][k]:
            return f"near known danger: {k}, {d} away"
    status = explore.needs_status(state, accept=w.get("status") or ())
    if status:
        return f"status: {status}"
    if (p.get("level") or 0) > w.get("level", 1 << 30):
        return f"level up: now level {p.get('level')}"
    if (p.get("x"), p.get("y")) == (w["x"], w["y"]):
        return "arrived"
    pos = [p.get("x"), p.get("y")]
    w["still"] = w.get("still", 0) + 1 if w.get("last") == pos else 0
    w["last"] = pos
    if w["still"] >= 3:
        return f"blocked at ({pos[0]},{pos[1]})"
    w["steps"] = w.get("steps", 0) + 1
    if w["steps"] > w.get("max", 150):
        return "too many steps"
    return None


def walk_start(line, state, memory):
    """WALK x y: walk there one step per call without asking the LLM, until something unexpected."""
    p = state.get("player") or {}
    parts = line.split()
    from scripts import explore
    memory["walk"] = {"x": int(parts[1]), "y": int(parts[2]), "zone": p.get("zone"), "hp": p.get("hp", 0),
                      "seq": state.get("seq"), "level": p.get("level") or 0,
                      # what's already known at the start doesn't stop the walk; anything new or closer does
                      "threats": threats_near(state), "status": (explore.needs_status(state) or "").split(","),
                      "seen": {"msgs": list(state.get("messages") or [])},
                      "ignore": parts[3].replace("_", " ") if len(parts) > 3 else None,
                      "hostiles_at_start": {f"{o['name']}@{o['x']},{o['y']}": max(abs(o["x"] - p.get("x", 0)), abs(o["y"] - p.get("y", 0)))
                                            for o in (state.get("map") or {}).get("objects", []) if o.get("creature") and o.get("hostile")}}
    memory.pop("walk_result", None)


def progress_note(acts, state):
    """A few words on what the LLM's keys are doing, from the first action and the screen."""
    a = acts[0]
    rows = " ".join((state.get("screen") or {}).get("rows", [])[:3])
    if a.startswith(("WALK", "GOTO")):
        return "Walking."
    if "CmdTalk" in a:
        return "Talking to someone."
    if "Trade" in a or "inventory ]" in rows.lower() and "$" in rows:
        return "Trading."
    if "CmdInventory" in a or "Inventory" in rows:
        return "Sorting the pack."
    if "CmdAbilities" in a:
        return "Using an ability."
    if "CmdFire" in a or "CmdReload" in a:
        return "Musket."
    if "CmdAttack" in a:
        return "Fighting."
    if "CmdMove" in a:
        return "On the move."
    return "Working through a menu."


def observe_swings(state, memory):
    """Hand-played melee swings go into the weapon record too (2026-11-26: only the fight routine's
    were recorded, so the long sword's record was all misses). The target is the one adjacent hostile."""
    try:
        import world as _w, threat
        from scripts import fight
        new = fight.new_messages(state, memory.setdefault("seen_swings", {}))
        if not any(m.startswith("You hit (") or m.startswith("You critically hit (") or m.startswith("You miss") for m in new):
            return
        p = state.get("player") or {}
        adj = [o for o in (state.get("map") or {}).get("objects", []) if o.get("creature") and o.get("hostile")
               and max(abs(o["x"] - p.get("x", 0)), abs(o["y"] - p.get("y", 0))) <= 1]
        if len(adj) == 1 and _w.CURRENT is not None:
            threat.observe(_w.CURRENT, new, state, adj[0])
    except Exception:
        pass


def act(state, memory, args):
    observe_swings(state, memory)
    on_map = state.get("wait") == "map"
    # The game's own automatic action (walking to a cell, autoexplore) is running: let it finish.
    if on_map and state.get("autoact"):
        return ["PASS"]
    # A WALK in progress: step on without the LLM; end it on anything unexpected (tools/walk.py waits
    # for memory["walk_result"]). HP regenerating up is fine; only a drop counts.
    w = memory.get("walk")
    if w:
        p = state.get("player") or {}
        if (p.get("hp") or 0) > w["hp"]:
            w["hp"] = p["hp"]  # regeneration raises the bar; any drop below it ends the walk
        why = walk_check(state, w)
        if why is None:
            return [f"GOTO {w['x']} {w['y']}"]
        memory.pop("walk")
        memory["walk_result"] = {"reason": why, "turn": state.get("turn"), "seq": state.get("seq"),
                                 "x": p.get("x"), "y": p.get("y"), "started_seq": w.get("seq")}
        return [f"SAY Walk to ({w['x']},{w['y']}) ended: {why}.", "PASS" if on_map else "WAIT"]
    # How many inbox lines have been played lives in its own file, not in the stage memory: a plan change
    # resets memory, and re-counting the inbox then swallowed a line sent at the same moment (2026-11-25:
    # a WALK sent right after writing plan.json was taken as old and never played).
    done = played_count()
    if not memory.get("greeted"):
        memory["greeted"] = True
        memory["done"] = done
        return ["SAY Over to the LLM for a decision.", "PASS" if on_map else "WAIT"]
    wait_for = args.get("map_poll_seconds", 1) if on_map else args.get("poll_seconds", 10)
    deadline = time.time() + wait_for
    while True:
        lines = read_inbox()
        if len(lines) > done:
            new = lines[done:]
            memory["done"] = len(lines)
            memory["played_at_seq"] = state.get("seq")
            save_played(len(lines), state.get("seq"))
            # A brief spoken note of what the LLM is doing, at most every progress_seconds (the user,
            # 2026-11-24: "a brief update in between actions up to once every 20 seconds").
            acts = [l for l in new if l.split(" ", 1)[0] in ("KEY", "CMD", "GOTO", "WALK")]
            # Only a fallback: if the LLM spoke for itself recently (tools/say.py writes live/voice.log),
            # no auto note.
            vlog = INBOX.parent / "voice.log"
            spoke = vlog.exists() and time.time() - vlog.stat().st_mtime < args.get("progress_seconds", 20)
            if acts and not spoke and time.time() - memory.get("voice_at", 0) > args.get("progress_seconds", 20):
                memory["voice_at"] = time.time()
                note = progress_note(acts, state)
                if note:
                    new = new + [f"VOICE progress: {note}"]
            walks = [l for l in new if l.startswith("WALK ")]
            if walks:
                walk_start(walks[-1], state, memory)
                new = [l for l in new if not l.startswith("WALK ")]
                w = memory["walk"]
                if on_map and not any(l.split(" ", 1)[0] in ACTIONS for l in new):
                    return new + [f"GOTO {w['x']} {w['y']}"]
            # Only narration (SAY)? Keep the run going instead of ending it for having no keys.
            if not any(l.split(" ", 1)[0] in ACTIONS for l in new):
                new.append("PASS" if on_map else "WAIT")
            return new
        memory["done"] = done
        if time.time() >= deadline:
            return ["PASS" if on_map else "WAIT"]
        time.sleep(0.1)
