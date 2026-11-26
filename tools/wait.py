"""Wait safely, one turn at a time, during a remote run (the user, 2026-11-24: confusion garbles our
input; never take turns freely while it's on unless sure nothing is happening). Replaces every
hand-written wait loop: two deaths came from loops that checked only one thing.

  python tools/wait.py --until-clear confused     wait until that effect is gone
  python tools/wait.py --turns 5                  wait up to 5 turns

Stops (and prints why) at the first of:
  - any HP drop                       - a popup or menu
  - a hostile that wasn't in view, or one that came closer
  - a hostile adjacent                - the effect gone / the turns done
While confused with any hostile in view, it waits at most one turn and stops: every move may go astray.
Exit code 0 when the wait finished as asked, 2 when something stopped it.
"""
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def state():
    return json.loads((ROOT / "live" / "state.json").read_text(encoding="utf-8-sig"))


def rooted_kinds():
    """Kinds known not to move (game knowledge): one 2+ cells away can't reach us."""
    try:
        sys.path.insert(0, str(ROOT / "brain"))
        import world as W
        g = json.loads((ROOT / "brain" / "game_knowledge.json").read_text(encoding="utf-8"))
        return {k for k, v in (g.get("kinds") or {}).items() if v.get("mobile") is False}, W.kind_name
    except Exception:
        return set(), (lambda n: n)


ROOTED, KIND = rooted_kinds()


def hostiles(s):
    p = s.get("player") or {}
    px, py = p.get("x", 0), p.get("y", 0)
    out = {}
    for o in (s.get("map") or {}).get("objects", []):
        if not o.get("hostile"):
            continue
        d = max(abs(o["x"] - px), abs(o["y"] - py))
        if d >= 2 and KIND(o["name"]) in ROOTED:
            continue  # rooted and not next to us: can't reach us
        out[f"{o['name']}@{o['x']},{o['y']}"] = d
    return out


def say(text):
    subprocess.run([sys.executable, str(ROOT / "tools" / "say.py"), text], cwd=ROOT, capture_output=True)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--until-clear", default=None, help="an effect name, e.g. confused")
    ap.add_argument("--turns", type=int, default=20)
    a = ap.parse_args()
    s = state()
    hp0 = (s.get("player") or {}).get("hp")
    seen = hostiles(s)
    for n in range(a.turns):
        s = state()
        p = s.get("player") or {}
        effects = " ".join(p.get("effects") or [])
        now = hostiles(s)
        why = None
        if s.get("wait") != "map":
            why = "a popup or menu is open"
        elif hp0 is not None and (p.get("hp") or 0) < hp0:
            why = f"HP dropped {hp0} -> {p.get('hp')}"
        elif any(d <= 1 for d in now.values()):
            why = "a hostile is adjacent: " + ", ".join(k for k, d in now.items() if d <= 1)
        elif any(k not in seen or d < seen[k] for k, d in now.items()):
            why = "a hostile appeared or came closer: " + ", ".join(k for k, d in now.items() if k not in seen or d < seen[k])
        elif a.until_clear and a.until_clear not in effects:
            print(f"done: {a.until_clear} is gone after {n} turn(s); HP {p.get('hp')}")
            return 0
        elif "confused" in effects and now and n >= 1:
            why = "still confused with a hostile in view: one turn at a time"
        if why:
            print(f"stopped after {n} turn(s): {why}; HP {p.get('hp')}, turn {s.get('turn')}")
            say(f"Stopped waiting: {why.split(':')[0]}.")
            return 2
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "send.py"), "CMD CmdWait"], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != 0:
            print("send failed:", (r.stdout + r.stderr).strip()[:200])
            return 2
        seen = {**seen, **now}
    print(f"done: waited {a.turns} turn(s); HP {(state().get('player') or {}).get('hp')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
