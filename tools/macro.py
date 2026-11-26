"""Play a sequence of keys/commands through the remote stage, checking the screen only where it matters
(the user, 2026-11-24: batch menu navigation, validate once before confirming).

  python tools/macro.py "CMD CmdInventory" "?Inventory" "KEY k" "KEY Space" "?a) eat" "KEY a"

Steps:
  KEY / CMD / GOTO ...  played; consecutive ones go out together in one batch (fine in menus; on the
                        map only the first action of a batch counts, so put map actions alone)
  ?text                 wait for the screen to show text (case-sensitive, anywhere on screen); if it
                        doesn't, stop there and print the screen (nothing after it is played)
  !text                 the same, but the screen must NOT show text
Prints the final screen's key lines (or the whole screen with --screen).
"""
import json, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def speak(text):
    """A line for the narrator: the LLM's own driving should be heard too (the user, 2026-11-24)."""
    subprocess.run([sys.executable, str(ROOT / "tools" / "say.py"), text], cwd=ROOT, capture_output=True)


def state():
    return json.loads((ROOT / "live" / "state.json").read_text(encoding="utf-8-sig"))


def screen(s):
    return "\n".join((s.get("screen") or {}).get("rows", []))


def send(lines):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "send.py"), *lines], cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        print(r.stdout + r.stderr)
        sys.exit(r.returncode)


def check(step, timeout=3.0):
    want, text = step[0] == "?", step[1:]
    deadline = time.time() + timeout
    while True:
        shown = text in screen(state())
        if shown == want:
            return True
        if time.time() >= deadline:
            return False
        time.sleep(0.2)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    full = "--screen" in args
    steps = [a for a in args if a != "--screen"]
    batch = []
    for step in steps + [None]:
        if step is None or step[:1] in "?!":
            if batch:
                send(batch)
                batch = []
            if step is None:
                break
            if not check(step):
                speak("A menu did not go as expected; looking at the screen.")
                print(f"stopped: expected {'' if step[0] == '?' else 'no '}'{step[1:]}' on screen")
                print(screen(state()))
                sys.exit(3)
        else:
            parts = step.split(None, 1)
            if parts and parts[0] in ("KEY", "CMD") and len(parts) < 2:
                # An empty key stops the whole run in the mod (2026-11-24): refuse it here.
                print(f"refused: empty step {step!r}")
                sys.exit(4)
            batch.append(step)
    s = state()
    p = s.get("player") or {}
    print(f"turn {s.get('turn')} wait {s.get('wait')} HP {p.get('hp')}/{p.get('maxhp')} at ({p.get('x')},{p.get('y')}) {p.get('zoneName')}")
    if full:
        print(screen(s))
    else:
        print("messages:", " | ".join((s.get("messages") or [])[-3:]))


if __name__ == "__main__":
    main()
