"""Walk up to a rooted enemy in view and kill it, confirming the kill (the user, 2026-11-25: walking over
to dreadroots and killing them must be reliable; earlier they were walked past, and a kill went
unreported).

  python tools/kill.py dreadroot          the nearest one in view
  python tools/kill.py --rooted           every hostile in view whose kind is known not to move and
                                          isn't marked avoid (dreadroots, rooted vines...)

Each target: walk to a free cell next to it (the walk ignores that kind but stops for anything else),
attack until it's gone from its cell, and confirm by the death message or the empty cell. Stops (exit 2)
when HP drops by more than --max-loss, a popup opens, a walk ends for another reason, or a target
survives --max-attacks blows. Needs a live run in the remote stage.
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "brain"))
# brain/world.py, imported before walk/send put tools/ (which has its own world.py) first on the path
import world as W  # noqa: E402
import send as _send  # noqa: E402
import walk as _walk  # noqa: E402

DIRS = {(0, -1): "N", (0, 1): "S", (1, 0): "E", (-1, 0): "W",
        (1, -1): "NE", (-1, -1): "NW", (1, 1): "SE", (-1, 1): "SW"}
BLOCKED = set("▒ #")


def state():
    return _walk.state()


def say(text):
    import subprocess
    subprocess.run([sys.executable, str(ROOT / "tools" / "say.py"), text], cwd=ROOT, capture_output=True)


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def rooted_kinds():
    g = json.loads((ROOT / "brain" / "game_knowledge.json").read_text(encoding="utf-8"))
    return {k for k, v in (g.get("kinds") or {}).items()
            if v.get("mobile") is False and v.get("verdict") not in ("avoid",)}


def targets(s, kinds):
    p = s.get("player") or {}
    me = (p.get("x"), p.get("y"))
    out = [o for o in (s.get("map") or {}).get("objects", [])
           if o.get("creature") and o.get("hostile") and W.kind_name(o["name"]) in kinds]
    return sorted(out, key=lambda o: cheb(me, (o["x"], o["y"])))


def neighbours(s, o):
    """Free cells next to o, nearest to us first."""
    p = s.get("player") or {}
    rows = (s.get("map") or {}).get("rows") or []
    taken = {(c["x"], c["y"]) for c in (s.get("map") or {}).get("objects", []) if c.get("creature")}
    out = []
    for dx, dy in DIRS:
        x, y = o["x"] + dx, o["y"] + dy
        if 0 <= y < len(rows) and 0 <= x < len(rows[y]) and rows[y][x] not in BLOCKED and (x, y) not in taken:
            out.append((x, y))
    return sorted(out, key=lambda c: cheb((p.get("x"), p.get("y")), c))


def kill_one(o, a, hp0):
    kind = W.kind_name(o["name"])
    cell = (o["x"], o["y"])
    blows = 0
    for _ in range(a.max_attacks * 3):
        s = state()
        p = s.get("player") or {}
        me = (p.get("x"), p.get("y"))
        if s.get("wait") != "map":
            return f"a popup is open: {' / '.join(r.strip() for r in s['screen']['rows'] if '▌' in r)[:150]}"
        if (p.get("hp") or 0) < hp0 - a.max_loss:
            return f"HP dropped {hp0} -> {p.get('hp')}"
        here = [c for c in (s.get("map") or {}).get("objects", []) if c.get("creature") and (c["x"], c["y"]) == cell]
        if not here or W.kind_name(here[0]["name"]) != kind:
            dead = [m for m in (s.get("messages") or [])[-8:] if kind in m.lower() and ("dies" in m or "destroy" in m or "kill" in m)]
            print(f"killed: {kind} at {cell} after {blows} blow(s)" + (f" ({dead[-1]})" if dead else " (its cell is empty)"))
            return None
        if cheb(me, cell) <= 1:
            if blows >= a.max_attacks:
                return f"{kind} at {cell} survived {blows} blows"
            _send.play([f"CMD CmdAttack{DIRS[(cell[0] - me[0], cell[1] - me[1])]}"], check_run=False)
            blows += 1
            continue
        # Not adjacent (we just arrived, or terror moved us away): walk to a free cell next to it.
        for nx, ny in neighbours(s, here[0])[:4]:
            reason, s2 = _walk.walk(nx, ny, ignore=kind)
            if reason == "arrived":
                break
            if not reason.startswith(("no path", "blocked")):
                return f"walk towards {kind} ended: {reason}"
        else:
            return f"no free cell next to {kind} at {cell} could be reached"
    return f"gave up on {kind} at {cell}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", nargs="?", default=None)
    ap.add_argument("--rooted", action="store_true")
    ap.add_argument("--max-attacks", type=int, default=12)
    ap.add_argument("--max-loss", type=int, default=5)
    a = ap.parse_args()
    kinds = rooted_kinds() if a.rooted or not a.kind else {W.kind_name(a.kind)}
    s = state()
    hp0 = (s.get("player") or {}).get("hp") or 0
    done = 0
    while True:
        ts = targets(state(), kinds)
        if not ts:
            break
        o = ts[0]
        say(f"Killing the {W.kind_name(o['name'])} at {o['x']}, {o['y']}.")
        why = kill_one(o, a, hp0)
        if why:
            print("stopped:", why)
            say(f"Stopped killing: {why.split(':')[0]}.")
            return 2
        done += 1
    print(f"done: {done} killed; none left in view" if done else "nothing to kill in view")
    return 0


if __name__ == "__main__":
    sys.exit(main())
