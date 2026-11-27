"""How long each character took from level 1 to a level, in game turns and real time, from live/log.jsonl
(the owner, 2026-11-27: account for every character that did the level 1-5 run). The table is kept in
research/level5_runs.md; rerun this after a new run and update it there.

  python tools/level_runs.py              every character in the log, to level 5
  python tools/level_runs.py --level 6    to another level
  python tools/level_runs.py --hours      also the hours of the day each one was played

Per character (game id):
  turns         game turn at the first snapshot at that level minus the first snapshot's turn. A reload
                after a death rewinds the counter, so this counts the timeline that survived.
  bot acting    the sum of gaps under 60 s between logged actions. Only actions are logged (not WAIT or
                PASS), so long pauses, such as the LLM thinking, fall out.
  with pauses   the same with gaps up to 10 minutes: most LLM thinking and live fixes while a run was on.
  span          wall-clock time from the first snapshot to the level, breaks between sessions included.
"""
import argparse, json, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def scan(level):
    games, names = {}, {}
    with (ROOT / "live" / "log.jsonl").open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"kind":"call"' not in line[:60]:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            s = e.get("state") or {}
            gid = (s.get("game") or {}).get("id")
            p = s.get("player") or {}
            if not gid or not s.get("time"):
                continue
            try:
                t = datetime.fromisoformat(s["time"])
            except ValueError:
                continue
            g = games.setdefault(gid, {"first": None, "reached": None, "times": [], "max_level": 0,
                                       "reloads": 0, "last_turn": None})
            lvl, turn = p.get("level") or 0, s.get("turn") or 0
            if p.get("name"):
                names.setdefault(gid, set()).add(p["name"].split()[-1])  # confusion garbles names: all kept
            if g["first"] is None:
                g["first"] = (t, turn)
            if g["last_turn"] is not None and turn < g["last_turn"] - 5:
                g["reloads"] += 1
            g["last_turn"] = turn
            g["max_level"] = max(g["max_level"], lvl)
            if g["reached"] is None:
                g["times"].append(t)
                if lvl >= level:
                    g["reached"] = (t, turn)
    return games, names


def fmt(sec):
    h, m = divmod(int(sec) // 60, 60)
    return f"{h}h{m:02d}m"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", type=int, default=5)
    ap.add_argument("--hours", action="store_true")
    a = ap.parse_args()
    games, names = scan(a.level)
    for gid, g in sorted(games.items(), key=lambda kv: kv[1]["first"][0]):
        ts = g["times"]
        gaps = [(t1 - t0).total_seconds() for t0, t1 in zip(ts, ts[1:])]
        acting = sum(d for d in gaps if 0 <= d <= 60)
        paused = sum(d for d in gaps if 0 <= d <= 600)
        end = g["reached"]
        span = ((end[0] if end else ts[-1]) - g["first"][0]).total_seconds()
        turns = end[1] - g["first"][1] if end else None
        name = "/".join(sorted(names.get(gid, {"?"})))
        print(f"{gid[:8]} {name:<22} {g['first'][0]:%m-%d %H:%M}  max level {g['max_level']}  "
              f"turns to {a.level}: {turns if turns is not None else '-':>6}  acting {fmt(acting)}  "
              f"with pauses {fmt(paused)}  span {fmt(span)}  reloads {g['reloads']}")
        if a.hours:
            hours = {}
            for t in ts:
                hours[t.strftime("%m-%d %H")] = hours.get(t.strftime("%m-%d %H"), 0) + 1
            print("    " + ", ".join(f"{k}h: {v}" for k, v in sorted(hours.items())))


if __name__ == "__main__":
    main()
