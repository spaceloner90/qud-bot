"""Explore carefully, one short leg at a time, towards the unexplored part of the zone and away from a
known danger (the user, 2026-11-25: on Red Rock stratum 3 with the Snapjaw King's whereabouts unknown, go
step by step towards the unexplored section, keep away from the explored one, stop as soon as the King
is spotted).

  python tools/frontier.py --stop-on "Snapjaw King" [--avoid 34,5] [--radius 12] [--legs 30]

Each leg: the nearest frontier cell (explored floor next to unexplored), skipping any within --radius of
a danger (--avoid cells, plus hostiles the world file knows alive in this zone), walked to with the walk
tool, which stops for anything unexpected. Between legs:
  - a creature matching --stop-on in view: stop at once (exit 3)
  - stairs down in view: stop (exit 0), reporting where
  - a rooted hostile in view (dreadroots...): killed with tools/kill.py --rooted
  - any other hostile in view, or a walk ending for any reason but arrival: stop (exit 2)
Needs a live run in the remote stage.
"""
import argparse, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "brain"))
# brain/world.py, imported before walk/send put tools/ (which has its own world.py) first on the path
import world as W  # noqa: E402
import walk as _walk  # noqa: E402
import kill as _kill  # noqa: E402

BLOCKED = set("▒ #")


def say(text):
    subprocess.run([sys.executable, str(ROOT / "tools" / "say.py"), text], cwd=ROOT, capture_output=True)


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def frontier(rows):
    h = len(rows)
    out = []
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            if c in BLOCKED:
                continue
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= ny < h and 0 <= nx < len(rows[ny]) and rows[ny][nx] == " ":
                        out.append((x, y))
                        break
                else:
                    continue
                break
    return out


def dangers(s, extra):
    pts = list(extra)
    try:
        wld = W.load(s, apply=False)
        pts += [(c["x"], c["y"]) for c in wld.threats((s.get("player") or {}).get("zone"))]
    except Exception:
        pass
    return pts


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--stop-on", action="append", default=[])
    ap.add_argument("--avoid", action="append", default=[])
    ap.add_argument("--radius", type=int, default=12)
    ap.add_argument("--legs", type=int, default=30)
    a = ap.parse_args()
    extra = [tuple(int(v) for v in t.split(",")) for t in a.avoid]
    rooted = _kill.rooted_kinds()
    failed = set()
    for leg in range(a.legs):
        s = _walk.state()
        p = s.get("player") or {}
        me = (p.get("x"), p.get("y"))
        objs = (s.get("map") or {}).get("objects", [])
        stop = [o for o in objs if o.get("creature") and any(t.lower() in o["name"].lower() for t in a.stop_on)]
        if stop:
            o = stop[0]
            print(f"SPOTTED {o['name']} at ({o['x']},{o['y']}), {cheb(me, (o['x'], o['y']))} away; we're at {me}, HP {p.get('hp')}")
            say(f"Spotted {W.kind_name(o['name'])}, {cheb(me, (o['x'], o['y']))} cells away. Stopping.")
            return 3
        stairs = [o for o in objs + (s.get("map") or {}).get("features", []) if "stairs down" in o["name"].lower()]
        if stairs:
            o = stairs[0]
            print(f"STAIRS DOWN at ({o['x']},{o['y']}); we're at {me}")
            say(f"Stairs down in sight at {o['x']}, {o['y']}.")
            return 0
        hostile = [o for o in objs if o.get("creature") and o.get("hostile")]
        if hostile and all(W.kind_name(o["name"]) in rooted for o in hostile):
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "kill.py"), "--rooted"], cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8")
            print(r.stdout.strip())
            if r.returncode != 0:
                return 2
            continue
        if hostile:
            o = min(hostile, key=lambda o: cheb(me, (o["x"], o["y"])))
            print(f"HOSTILE {o['name']} at ({o['x']},{o['y']}), {cheb(me, (o['x'], o['y']))} away; we're at {me}")
            return 2
        danger = dangers(s, extra)
        cells = [c for c in frontier((s.get("map") or {}).get("rows") or [])
                 if c != me and c not in failed and all(cheb(c, d) >= a.radius for d in danger)]
        if not cells:
            print(f"no frontier left outside {a.radius} of {danger}; we're at {me}")
            return 2
        cells.sort(key=lambda c: (cheb(me, c), -min([cheb(c, d) for d in danger] or [99])))
        for c in cells[:6]:
            reason, s2 = _walk.walk(*c)
            p2 = s2.get("player") or {}
            print(f"leg {leg + 1}: to {c}: {reason}; now at ({p2.get('x')},{p2.get('y')}) HP {p2.get('hp')}")
            if reason == "arrived":
                break
            if reason.startswith(("no path", "blocked")):
                failed.add(c)
                continue
            if reason.startswith("hostile in view"):
                break  # handled at the top of the next leg
            say(f"Careful exploring stopped: {reason.split(':')[0]}.")
            return 2
        else:
            continue
    print(f"done {a.legs} legs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
