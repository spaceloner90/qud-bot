"""Walk next to a named creature (or to a cell) during a remote run, one GOTO step at a time.

  python tools/approach.py "Mehmet" 42 19     walk towards Mehmet (last known at 42,19) until adjacent
  python tools/approach.py "" 10 5            walk to cell 10,5

Prints each step and, when adjacent, the direction key to talk to them (e.g. "KEY RightArrow").
Stops if the run doesn't answer, a popup or menu opens, or it isn't getting closer.
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR_KEYS = {(0, -1): "UpArrow", (0, 1): "DownArrow", (-1, 0): "LeftArrow", (1, 0): "RightArrow",
            (-1, -1): "Keypad7", (1, -1): "Keypad9", (-1, 1): "Keypad1", (1, 1): "Keypad3"}


def state():
    return json.loads((ROOT / "live" / "state.json").read_text(encoding="utf-8"))


def send(line):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "send.py"), line], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode == 2:  # no run active: stop at once rather than wait out every step
        print(r.stdout.strip())
        sys.exit(2)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    name, tx, ty = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    best, stalls = None, 0
    for i in range(80):
        s = state()
        p = s["player"]
        if s.get("wait") != "map":
            print(f"stopped: wait is {s.get('wait')} (a popup or menu is open)")
            return
        who = next((o for o in s["map"]["objects"] if name and o["name"] == name), None)
        if who:
            tx, ty = who["x"], who["y"]
        dx, dy = tx - p["x"], ty - p["y"]
        dist = max(abs(dx), abs(dy))
        if (name and who and dist <= 1) or (not name and dist == 0):
            key = DIR_KEYS.get((dx, dy))
            print(f"arrived: you ({p['x']},{p['y']}), target ({tx},{ty}), turn {s['turn']}" + (f", talk key: KEY {key}" if key else ""))
            return
        if best is None or dist < best:
            best, stalls = dist, 0
        else:
            stalls += 1
            if stalls >= 6:
                print(f"not getting closer: you ({p['x']},{p['y']}), target ({tx},{ty})")
                return
        print(f"step {i}: you ({p['x']},{p['y']}), target ({tx},{ty}){' in view' if who else ' last known'}")
        send(f"GOTO {tx} {ty}")
    print("gave up after 80 steps")


if __name__ == "__main__":
    main()
