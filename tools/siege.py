"""Fight a group of creatures that never move (glowpads in their pool, rooted plants), one at a time, and
step out of their reach to regenerate when hurt (2026-11-25, Uubas at level 1: an even fight per the
estimate, but they can't follow, so hit-and-heal makes it safe).

  python tools/siege.py glowpad [--floor 10]

Each round: stand on a free cell next to exactly one of them and attack it; under --floor HP, walk to a
cell out of reach of all of them and wait one turn at a time until full. Stops (exit 2) when one of them
moves (then they aren't stationary), another hostile shows up, a popup opens, or HP drops below 5.
Targets by the game's creature id (mod v0.25). Needs a live run in the remote stage.
"""
import argparse, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "brain"))
import world as W  # noqa: E402  (brain/world.py, before tools/ goes on the path)
sys.path.insert(0, str(ROOT / "tools"))
import walk, send  # noqa: E402

D = {(0, -1): "N", (0, 1): "S", (1, 0): "E", (-1, 0): "W", (1, -1): "NE", (-1, -1): "NW", (1, 1): "SE", (-1, 1): "SW"}
BLOCKED = set("▒ #~≈")  # walls, unknown, and water (2026-11-25: a siege step left us swimming)


def ch(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def say(text):
    import subprocess
    subprocess.run([sys.executable, str(ROOT / "tools" / "say.py"), text], cwd=ROOT, capture_output=True)


def free_cells(s, near, count):
    """Free floor cells c with exactly `count` of the group within reach (count=0: out of reach of all),
    among the cells around the given points."""
    rows = s["map"]["rows"]
    occ = {(o["x"], o["y"]) for o in s["map"]["objects"] if o.get("creature")}
    out = set()
    for (x, y), r in near:
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                c = (x + dx, y + dy)
                if 0 <= c[1] < len(rows) and 0 <= c[0] < len(rows[c[1]]) and rows[c[1]][c[0]] not in BLOCKED and c not in occ:
                    out.add(c)
    return out


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("kind")
    ap.add_argument("--floor", type=int, default=10)
    ap.add_argument("--max-steps", type=int, default=600)
    ap.add_argument("--others-radius", type=int, default=6)
    ap.add_argument("--radius", type=int, default=12)
    a = ap.parse_args()
    kind = W.kind_name(a.kind)
    start = {}
    kills = 0
    retreated = False
    last_turn, same = None, 0
    for _ in range(a.max_steps):
        s = walk.state()
        p = s["player"]
        me = (p["x"], p["y"])
        # The game ignoring us (a swim prompt, a blocked step): the turn stops moving.
        same = same + 1 if s.get("turn") == last_turn else 0
        last_turn = s.get("turn")
        if same >= 4:
            print("no progress: the turn hasn't moved in 4 actions;", (s.get("messages") or [""])[-1][:120])
            return 2
        if s.get("wait") != "map" and ("health has dropped" in " ".join(s["screen"]["rows"]) or "You are famished" in " ".join(s["screen"]["rows"])):
            send.play(["KEY Space"], check_run=False)  # the low-health warning: we retreat below the floor anyway
            continue
        if s.get("wait") != "map":
            print("popup:", " / ".join(r.strip("│ ▌▐") for r in s["screen"]["rows"] if "▌" in r)[:200])
            return 2
        # Only the hostile ones near us: a calm one drifting across the zone isn't part of this siege
        # (2026-11-25: a non-hostile glowpad 60 cells off moved a cell and stopped everything).
        grp = [o for o in s["map"]["objects"] if o.get("creature") and o.get("hostile") and W.kind_name(o["name"]) == kind
               and ch(me, (o["x"], o["y"])) <= a.radius]
        # Other hostiles count once they're within --others-radius: far ones (fish keeping to their pool)
        # don't stop the siege.
        others = [o for o in s["map"]["objects"] if o.get("creature") and o.get("hostile") and W.kind_name(o["name"]) != kind
                  and ch(me, (o["x"], o["y"])) <= a.others_radius]
        if others:
            print("another hostile:", others[0]["name"], others[0]["x"], others[0]["y"])
            return 2
        for o in grp:
            k = o.get("id") or f"{o['x']},{o['y']}"
            start.setdefault(k, (o["x"], o["y"]))
            if start[k] != (o["x"], o["y"]) and ch(me, (o["x"], o["y"])) < ch(me, start[k]):
                print(f"{o['name']} moved towards us {start[k]} -> ({o['x']},{o['y']}): not stationary")
                return 2
        if not grp:
            print(f"done: {kills} killed; none left in view; HP {p['hp']}/{p['maxhp']}")
            return 0
        if p["hp"] < 5:
            print("HP below 5")
            return 2
        pts = [((o["x"], o["y"]), 1) for o in grp]
        reach = lambda c: sum(1 for o in grp if ch(c, (o["x"], o["y"])) <= 1)
        adj = [o for o in grp if ch(me, (o["x"], o["y"])) == 1]
        if p["hp"] < a.floor or (adj and p["hp"] < p["maxhp"] and len(adj) > 1):
            if not adj:
                if p["hp"] < p["maxhp"]:
                    retreated = True  # below the floor: regenerate to full before going back in
                    send.play(["CMD CmdWait"], check_run=False)
                    continue
            else:
                safe = [c for c in free_cells(s, [(me, 3)], 0) if reach(c) == 0]
                if not safe:
                    print("no cell out of reach nearby")
                    return 2
                c = min(safe, key=lambda c: ch(me, c))
                say(f"Down to {p['hp']}: stepping out of reach to regenerate.")
                retreated = True
                send.play([f"GOTO {c[0]} {c[1]}"], check_run=False)
                continue
        if not adj and p["hp"] < p["maxhp"] and retreated:
            send.play(["CMD CmdWait"], check_run=False)  # regenerate to full before going back in
            continue
        retreated = False
        if len(adj) == 1:
            o = adj[0]
            before = len([m for m in s.get("messages") or [] if "dies!" in m])
            send.play([f"CMD CmdAttack{D[(o['x'] - me[0], o['y'] - me[1])]}"], check_run=False)
            s2 = walk.state()
            if not any((x.get("id") or "") == (o.get("id") or "-") for x in s2["map"]["objects"]) and o.get("id"):
                kills += 1
            continue
        cells = [c for c in free_cells(s, pts, 1) if reach(c) == 1]
        if not cells:
            print("no cell next to only one of them")
            return 2
        c = min(cells, key=lambda c: ch(me, c))
        send.play([f"GOTO {c[0]} {c[1]}"], check_run=False)
    print("step limit reached")
    return 2


if __name__ == "__main__":
    sys.exit(main())
