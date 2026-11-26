"""Walk to a cell of the current zone in one go, through the remote script's WALK: the brain steps on
its own every call (no LLM round trip per step) and stops at anything unexpected (a hostile in view,
HP dropping, a bad effect, a popup, a zone change, blocked, a known danger nearer, a shot from out of
view, a new status, a level-up) or on arrival. Prints why it stopped and what's around.

  python tools/walk.py <x> <y> [--ignore "<kind>"] [--timeout 300] [--say "<line>"] [--think "<line>"]

--ignore: a kind that doesn't stop the walk (walking up to a rooted one to kill it: tools/kill.py).
--say / --think: narrate in the same call (voice / panel thought), before the walk starts.
Importable: walk(x, y, ignore=None) -> (reason, state). Needs a live run in the remote stage.
"""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import send as _send  # noqa: E402


def memory():
    try:
        return json.loads((ROOT / "live" / "memory.json").read_text(encoding="utf-8")).get("stage", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def state():
    return json.loads((ROOT / "live" / "state.json").read_text(encoding="utf-8-sig"))


def walk(x, y, ignore=None, timeout=300, stall=8):
    """Walk to (x, y); returns (the reason it ended, the state then). Reason "send failed" if not sent."""
    before = memory().get("walk_result")
    line = f"WALK {x} {y}" + (" " + ignore.replace(" ", "_") if ignore else "")
    code = _send.play([line])
    if code in (2, 4):
        return "send failed", state()
    if code == 3:
        # Kick back instead of waiting (the user, 2026-11-25: observe that the game doesn't change when we
        # expect it to): the brain never took the line.
        return "not played: the brain didn't take the WALK line", state()
    deadline = time.time() + timeout
    s0 = state()
    last, changed = (s0.get("turn"), (s0.get("player") or {}).get("x"), (s0.get("player") or {}).get("y")), time.time()
    while time.time() < deadline:
        res = memory().get("walk_result")
        if res and res != before:
            return res["reason"], state()
        s = state()
        now = (s.get("turn"), (s.get("player") or {}).get("x"), (s.get("player") or {}).get("y"))
        if now != last:
            last, changed = now, time.time()
        elif time.time() - changed > stall:
            return f"stalled: nothing changed in the game for {stall} s", s
        time.sleep(0.05)
    return "timed out", state()


def report(reason, s):
    p = s.get("player") or {}
    print(f"walk ended: {reason} | turn {s.get('turn')} HP {p.get('hp')}/{p.get('maxhp')} at ({p.get('x')},{p.get('y')}) {p.get('effects')}")
    print("creatures:", [(o["name"], o["x"], o["y"], "hostile" if o.get("hostile") else "") for o in (s.get("map") or {}).get("objects", []) if o.get("creature")])
    print("messages:", " | ".join((s.get("messages") or [])[-4:]))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("x", type=int)
    ap.add_argument("y", type=int)
    ap.add_argument("--ignore", default=None)
    ap.add_argument("--timeout", type=float, default=300)
    import say as _say
    a = ap.parse_args(_say.take_narration(sys.argv[1:]))
    reason, s = walk(a.x, a.y, a.ignore, a.timeout)
    report(reason, s)
    return 0 if reason == "arrived" else 2


if __name__ == "__main__":
    import atexit, narrate_check
    atexit.register(narrate_check.remind)
    sys.exit(main())
