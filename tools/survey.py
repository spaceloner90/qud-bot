"""Survey the world-map tiles around a centre (Joppa) for dungeons, one step at a time (the user,
2026-11-24: when the obvious dungeon is blocked, other dungeons in the marshes around Joppa can get a
character to level 5; never go further out, it's far too dangerous there).

Small sites aren't named on the world map until noticed: stepping onto a tile sometimes pops up "You
notice some ruins nearby. Would you like to investigate?". This walks a ring of tiles and stops at
anything that needs a decision.

  python tools/survey.py                       the 8 tiles around Joppa (11,22), nearest first
  python tools/survey.py --radius 2            the 24 tiles within 2
  python tools/survey.py --center 11,22 --skip 11,20

Stops (exit 2, printing why) at: any popup or prompt (a "notice ... investigate?" is reported as a
find), leaving the world map (getting lost puts us in a local zone), HP dropping, or food at Famished.
Each tile stepped on is noted in the run's world file. Needs a live run in the remote stage.
"""
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STEP = {(0, -1): "N", (0, 1): "S", (-1, 0): "W", (1, 0): "E",
        (-1, -1): "NW", (1, -1): "NE", (-1, 1): "SW", (1, 1): "SE"}


def state():
    return json.loads((ROOT / "live" / "state.json").read_text(encoding="utf-8-sig"))


def run(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")


def say(text):
    run(str(ROOT / "tools" / "say.py"), text)


def popup(s):
    return " / ".join(x.strip("│ ▌▐").strip() for x in (s.get("screen") or {}).get("rows", []) if "▌" in x and x.strip("▌▐ █│"))


def on_world(s):
    return (s.get("player") or {}).get("zone", "").count(".") <= 1


def route(center, radius, skip, start):
    cx, cy = center
    tiles = [(cx + dx, cy + dy) for dx in range(-radius, radius + 1) for dy in range(-radius, radius + 1)
             if (dx, dy) != (0, 0) and (cx + dx, cy + dy) not in skip]
    order, here = [], start
    while tiles:
        nxt = min(tiles, key=lambda t: (max(abs(t[0] - here[0]), abs(t[1] - here[1])), t))
        order.append(nxt)
        tiles.remove(nxt)
        here = nxt
    return order


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--center", default="11,22")
    ap.add_argument("--radius", type=int, default=1)
    ap.add_argument("--skip", nargs="*", default=[])
    a = ap.parse_args()
    s = state()
    if not on_world(s) or s.get("wait") != "map":
        print("not on the world map (or a popup is open)")
        return 2
    center = tuple(int(v) for v in a.center.split(","))
    skip = {tuple(int(v) for v in t.split(",")) for t in a.skip} | {center}
    p = s["player"]
    hp0 = p.get("hp")
    todo = route(center, a.radius, skip, (p["x"], p["y"]))
    print("route:", " ".join(f"{x},{y}" for x, y in todo))
    say(f"Surveying {len(todo)} tiles around Joppa for other dungeons, one step at a time.")
    for tx, ty in todo:
        while True:
            s = state()
            p = s["player"]
            here = (p["x"], p["y"])
            if here == (tx, ty):
                break
            dx, dy = (tx > here[0]) - (tx < here[0]), (ty > here[1]) - (ty < here[1])
            r = run(str(ROOT / "tools" / "send.py"), f"CMD CmdMove{STEP[(dx, dy)]}")
            if r.returncode != 0:
                print("send failed:", (r.stdout + r.stderr).strip()[:200])
                return 2
            s = state()
            p = s["player"]
            last = (s.get("messages") or [""])[-1]
            print(f"{s.get('turn')} at {p['x']},{p['y']} HP {p.get('hp')} {p.get('food')} | {last[:90]}")
            text = popup(s)
            if s.get("wait") != "map":
                if "notice" in text.lower() and "investigate" in text.lower():
                    print(f"FIND at {p['x']},{p['y']}: {text[:200]}")
                    run(str(ROOT / "tools" / "world.py"), "note", f"world map ({p['x']},{p['y']})",
                        f"Survey find at turn {s.get('turn')}: {text[:160]}")
                    say("Found something: the game asks whether to investigate. Stopping to decide.")
                else:
                    print(f"POPUP at {p['x']},{p['y']}: {text[:200]}")
                return 2
            if not on_world(s):
                print(f"LEFT the world map (lost?) in {p.get('zoneName')}")
                return 2
            if hp0 is not None and (p.get("hp") or 0) < hp0:
                print(f"HP dropped {hp0} -> {p.get('hp')}")
                return 2
            if p.get("food") == "Famished":
                print("Famished: eat before travelling on")
                return 2
        run(str(ROOT / "tools" / "world.py"), "note", f"world map ({tx},{ty})",
            f"Surveyed at turn {state().get('turn')}: nothing noticed. {last[:80]}")
    print("survey done: nothing noticed")
    say("Survey finished; nothing noticed on those tiles.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
