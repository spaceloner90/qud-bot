"""Wait for the brain's next hand-over (live/handover.json changes), then print it and exit.

Run in the background after giving the bot a plan: its exit wakes the LLM (the user, 2026-11-25: when
the bot stops, both sides were stuck waiting). Also exits when the mod stops asking (state.json unchanged
for --idle seconds while not on a popup), since that's a stop too.

  python tools/watch_handover.py [--idle 120]
  python tools/watch_handover.py --live       wait instead for a run to start (the user's F1)
"""
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import send as _send  # noqa: E402  (run_status: whether a run is going)
H = ROOT / "live" / "handover.json"
S = ROOT / "live" / "state.json"


def read(p):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--idle", type=int, default=120)
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    if a.live:  # a live remote run rewrites the snapshot about every second
        times = []
        while True:
            try:
                m = S.stat().st_mtime
            except FileNotFoundError:
                m = None
            if m and (not times or m != times[-1]):
                times = (times + [m])[-3:]
                if len(times) == 3 and times[-1] - times[0] < 10:
                    print(f"LIVE: the run is going (turn {read(S).get('turn')})")
                    return 0
            time.sleep(0.5)
    n0 = read(H).get("n", 0)
    # A hand-over that came after the current plan was written but before this watcher started was missed
    # (2026-11-25: the explore stage handed over about a goat within a second of next_zone.py writing the
    # plan, and the watcher then waited for the next one for ever): report it at once.
    try:
        if H.exists() and H.stat().st_mtime > (ROOT / "brain" / "plan.json").stat().st_mtime:
            h = read(H)
            print(f"HANDOVER (before the watcher started) at turn {h.get('turn')}: {h.get('reason')}")
            return 0
    except OSError:
        pass
    checked, was_active = 0.0, _send.run_status()[0]
    last_m, still = None, time.time()
    while True:
        h = read(H)
        # A run that stopped (a brain crash, a key press) is a hand-over too (2026-11-25: a crash waited out
        # the idle timer): the mod's log says so at once.
        if time.time() - checked > 2:
            checked = time.time()
            active, why = _send.run_status()
            if not active and was_active:
                print(f"STOPPED: the run ended ({why})")
                return 0
            was_active = was_active or active
        if h.get("n", 0) != n0:
            print(f"HANDOVER at turn {h.get('turn')}: {h.get('reason')}")
            return 0
        # A plan was given but the run still sits in the remote stage, with no hand-over since (2026-11-26:
        # an identical plan re-sent after a hand-over was ignored, and the run passed for minutes).
        try:
            pl = read(ROOT / "brain" / "plan.json")
            stages = pl.get("stages") or [pl]
            pm = (ROOT / "brain" / "plan.json").stat().st_mtime
            if stages and stages[0].get("script") != "remote" and time.time() - pm > 15 \
                    and not (H.exists() and H.stat().st_mtime > pm):
                mem = read(ROOT / "live" / "memory.json")
                first_remote = next((i for i, st in enumerate(stages) if st.get("script") == "remote"), None)
                if mem.get("_hold") or (first_remote is not None and mem.get("_stage", 0) >= first_remote):
                    print(f"HELD: plan '{pl.get('label')}' given but the run is still in the remote stage (hold: {mem.get('_hold')})")
                    return 0
        except (OSError, ValueError):
            pass
        try:
            m = S.stat().st_mtime
        except FileNotFoundError:
            m = None
        if m != last_m:
            last_m, still = m, time.time()
        elif time.time() - still > 25 and read(S).get("wait") not in (None, "map") and _send.run_status()[0]:
            # In a popup or menu the mod asks again at once after a WAIT (the remote stage blocks at most
            # 10 s), so a snapshot this old there means nobody is asking (2026-11-26: a popup sat for
            # minutes after the brain answered PASS on it).
            s = read(S)
            print(f"STALLED: a {s.get('wait')} screen unanswered for 25s (turn {s.get('turn')})")
            return 0
        elif time.time() - still > a.idle:
            s = read(S)
            print(f"IDLE: no snapshot for {a.idle}s (turn {s.get('turn')}, wait {s.get('wait')}); the run may have stopped")
            return 0
        time.sleep(1)


if __name__ == "__main__":
    import atexit, narrate_check
    atexit.register(narrate_check.remind)
    sys.exit(main())
