"""Drive a remote run: send answer lines to the brain and print the screen that results.

  python tools/send.py "KEY Down" "KEY Return"   play these, wait for the next snapshot, print it
  python tools/send.py                            just print the latest snapshot
  --screen                                        print the text screen instead of the map
  -m "text"                                       also send a SAY line (goes to the bot panel and live/narration.log, not the game log)
  --say "line" / --think "line"                   narrate in the same call: the voice (tools/say.py) and/or
                                                  the panel's thought train (tools/think.py), before the keys play
Verbs accepted: KEY CMD GOTO AIM WALK SAY VOICE STOP WAIT PASS; lines with quote characters are refused, so pass each
key as its own plain argument.

Needs brain/plan.json set to the "remote" script and a run started in game (F1).
"""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "live"


def load(name):
    try:
        return json.loads((LIVE / name).read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def show(state, screen_too=False):
    if not state:
        print("(no snapshot)")
        return
    print(f"seq {state['seq']}  mode {state.get('mode')}  turn {state.get('turn')}")
    player = state.get("player") or {}
    if player:
        print("player", json.dumps(player))
    m = state.get("map")
    if m and not screen_too:
        for y, row in enumerate(m["rows"]):
            if y == player.get("y"):
                x = player["x"]
                row = row[:x] + "@" + row[x + 1:]
            print(row.rstrip())
        for o in m.get("objects", []):
            tag = (" HOSTILE" if o.get("hostile") else " creature") if o.get("creature") else ""
            print(f"  {o['glyph']} ({o['x']},{o['y']}) {o['name']}{tag}")
    else:
        for row in (state.get("screen") or {}).get("rows", []):
            print(row.rstrip())
    msgs = state.get("messages") or []
    if msgs:
        print("messages:", " | ".join(msgs[-5:]))


def run_status():
    """(active, why) from the end of live/log.jsonl: a run is active after a run-start control line
    and until a stop line or a game restart (heartbeat)."""
    try:
        with (LIVE / "log.jsonl").open("rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 200000))
            lines = f.read().decode("utf-8", "replace").splitlines()[1:]
    except FileNotFoundError:
        return False, "no log yet"
    for line in reversed(lines):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = e.get("kind")
        if kind == "stop":
            return False, "the run stopped: " + str(e.get("reason"))[:120]
        if kind == "heartbeat":
            return False, "the game was restarted since the last run"
        if kind == "control" and e.get("key") == "run":
            return bool(e.get("running")), "started" if e.get("running") else "stopping"
        if kind == "call":
            return True, "running"
    return False, "no run in the log"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    import say as _say
    screen_too = "--screen" in sys.argv
    args = _say.take_narration([a for a in sys.argv[1:] if a != "--screen"])
    lines = []
    while args:
        a = args.pop(0)
        if a == "-m" and args:
            lines.append("SAY " + args.pop(0))  # narration shown in the game's message log
        else:
            lines.append(a)
    if lines:
        code = play(lines)
        if code in (2, 4):
            sys.exit(code)
    show(load("state.json"), screen_too)


VERBS = ("KEY", "CMD", "GOTO", "AIM", "WALK", "SAY", "VOICE", "STOP", "WAIT", "PASS")


def play(lines, check_run=True):
    """Append the lines to the inbox and wait until they're played and a newer snapshot is out.
    Returns 0, or 2 (no run) / 4 (malformed) / 3 (timed out). Importable: tools/menu.py calls it in
    process, which saves a Python start per key (2026-11-25: menus felt slow)."""
    # An empty or malformed key stops the whole run in the mod (2026-11-24, twice): refuse it here.
    for l in lines:
        parts = l.split(None, 1)
        if not parts or parts[0] not in VERBS or (parts[0] in ("KEY", "CMD", "GOTO", "AIM", "WALK") and len(parts) < 2)                 or any(c in l for c in "\"'"):
            print(f"refused: malformed line {l!r}")
            return 4
    if True:
        if check_run:
            active, why = run_status()
            if not active:
                # Don't queue: the lines would play late, whenever a run starts again.
                print(f"NOT SENT: no bot run is active ({why}). Press F1 in the game first.")
                return 2
        inbox = LIVE / "inbox.txt"
        before = len([l for l in inbox.read_text(encoding="utf-8").splitlines() if l.strip()]) if inbox.exists() else 0
        with inbox.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        target = before + len(lines)
        deadline = time.time() + 8
        while time.time() < deadline:
            # The remote script records what it has played in live/inbox_played.json (not the stage memory,
            # which a plan change resets).
            mem = load("inbox_played.json") or {}
            state = load("state.json") or {}
            if mem.get("done", 0) >= target and state.get("seq", 0) > mem.get("played_at_seq", 1 << 30):
                break
            time.sleep(0.02)
        else:
            print("(timed out waiting: is a remote run going? showing latest snapshot)")
            return 3
    return 0


if __name__ == "__main__":
    import atexit, narrate_check
    atexit.register(narrate_check.remind)
    main()
