"""Summarize what the bot has seen, from live/log.jsonl: the input for the LLM's assessments.

  python tools/analyze.py              everything in the log
  python tools/analyze.py --since 120  only snapshots from seq 120 on (seq restarts with each game start)
  python tools/analyze.py --last-run   only since the latest run started

Writes the report to stdout and to live/findings.md. Sections: progress (turns, level, XP, HP),
stops, zones, creatures, objects (items, containers, signs, doors, stairs), quests, inventory and
equipment changes, and new messages.
"""
import json, re, sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "live" / "log.jsonl"
OUT = ROOT / "live" / "findings.md"
XP_RE = re.compile(r"XP:\s*(\d+)\s*/\s*(\d+)")


def entries():
    with LOG.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    pass


def select(all_entries, args):
    if "--last-run" in args:
        start = 0
        for i, e in enumerate(all_entries):
            if e.get("kind") == "control" and e.get("key") == "run" and e.get("running"):
                start = i
        return all_entries[start:]
    if "--since" in args:
        since = int(args[args.index("--since") + 1])
        return [e for e in all_entries if e.get("seq", since) >= since]
    return all_entries


def xp_of(state):
    for row in (state.get("screen") or {}).get("rows", []):
        m = XP_RE.search(row)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


def main():
    args = sys.argv[1:]
    chosen = select(list(entries()), args)
    states = [e["state"] for e in chosen if isinstance(e.get("state"), dict) and e["state"].get("player")]
    stops = [e for e in chosen if e.get("kind") == "stop"]
    out = []
    w = out.append

    w("# Findings\n")
    if not states:
        w("No snapshots with a player in this range.")
        finish(out)
        return

    first, last = states[0], states[-1]
    p0, p1 = first["player"], last["player"]
    w("## Progress\n")
    w(f"- Snapshots: {len(states)}, seq {first['seq']} to {last['seq']}, {first.get('time')} to {last.get('time')}")
    w(f"- Turns: {first.get('turn')} to {last.get('turn')} ({last.get('turn', 0) - first.get('turn', 0)} turns)")
    w(f"- Level: {p0.get('level')} to {p1.get('level')}")
    xp0, xp1 = xp_of(first), xp_of(last)
    if xp0 and xp1:
        w(f"- XP: {xp0[0]}/{xp0[1]} to {xp1[0]}/{xp1[1]}")
    hps = [(s["player"].get("hp"), s["player"].get("maxhp"), s.get("turn")) for s in states if s["player"].get("hp") is not None]
    if hps:
        low = min(hps, key=lambda t: t[0])
        w(f"- HP: lowest {low[0]}/{low[1]} at turn {low[2]}, now {p1.get('hp')}/{p1.get('maxhp')}")

    w("\n## Stops\n")
    calls = [e for e in chosen if e.get("kind") == "call"]
    for e in calls:
        if e.get("stop"):
            w(f"- seq {e['seq']}: {e['stop']}")
    for e in stops:
        if not any(c.get("seq") == e.get("seq") and c.get("stop") for c in calls):
            w(f"- seq {e.get('seq')}: {e.get('reason')}")

    zones = OrderedDict()
    creatures = OrderedDict()
    objects = OrderedDict()
    for s in states:
        pl = s["player"]
        z = pl.get("zone")
        zones.setdefault(z, {"name": pl.get("zoneName"), "first": s.get("turn"), "last": s.get("turn")})
        zones[z]["last"] = s.get("turn")
        for o in (s.get("map") or {}).get("objects", []):
            if o.get("creature"):
                key = (z, o["name"])
                c = creatures.setdefault(key, {"hostile": o.get("hostile"), "first": s.get("turn"), "at": (o["x"], o["y"]), "glyph": o["glyph"]})
                c["hostile"] = c["hostile"] or o.get("hostile")
            else:
                key = (z, o["name"], o["x"], o["y"])
                objects.setdefault(key, {"first": s.get("turn"), "glyph": o["glyph"]})

    w("\n## Zones\n")
    for z, info in zones.items():
        w(f"- {info['name']} ({z}): turns {info['first']} to {info['last']}")

    w("\n## Creatures seen\n")
    for (z, name), c in creatures.items():
        tag = "HOSTILE" if c["hostile"] else "not hostile"
        w(f"- {c['glyph']} {name}, {tag}, first at {c['at']} turn {c['first']} ({zones[z]['name']})")

    w("\n## Objects seen (items, containers, signs, doors, stairs)\n")
    by_name = OrderedDict()
    for (z, name, x, y), o in objects.items():
        by_name.setdefault((z, name, o["glyph"]), []).append((x, y))
    for (z, name, glyph), spots in by_name.items():
        where = ", ".join(f"({x},{y})" for x, y in spots[:6]) + (" ..." if len(spots) > 6 else "")
        w(f"- {glyph} {name} x{len(spots)}: {where} ({zones[z]['name']})")

    w("\n## Popups\n")
    popups = OrderedDict()
    for s in states:
        if s.get("wait") == "key":
            rows = (s.get("screen") or {}).get("rows", [])
            text = " / ".join(" ".join(r.split()) for r in rows if re.search(r"[A-Za-z]{3}", r))
            popups.setdefault(text[:400], s.get("turn"))
    if not popups:
        w("- none")
    for text, turn in popups.items():
        w(f"- turn {turn}: {text}")

    w("\n## Quests\n")
    q0 = {q["name"]: q for q in first.get("quests") or [] if isinstance(q, dict)}
    q1 = [q for q in last.get("quests") or [] if isinstance(q, dict)]
    if not q1:
        w("- none in the quest log")
    for q in q1:
        new = "" if q["name"] in q0 else " (NEW)"
        state = "finished" if q.get("finished") else "open"
        w(f"- {q['name']}{new}: {state}; giver {q.get('giver')} at {q.get('where')}")
        for st in q.get("steps", []):
            mark = "x" if st.get("finished") else ("!" if st.get("failed") else " ")
            w(f"    [{mark}] {st.get('name')}: {st.get('text')}")

    w("\n## Inventory and equipment\n")
    for key in ("inventory", "equipped"):
        a, b = first.get(key) or [], last.get(key) or []
        gained = [i for i in b if i not in a]
        lost = [i for i in a if i not in b]
        w(f"- {key} now ({len(b)}): {', '.join(b) if b else 'nothing'}")
        if gained:
            w(f"  - gained: {', '.join(gained)}")
        if lost:
            w(f"  - lost: {', '.join(lost)}")

    w("\n## Messages\n")
    seen = OrderedDict()
    for s in states:
        for m in s.get("messages") or []:
            seen.setdefault(m, None)
    for m in seen:
        w("- " + m.replace("\n", " ")[:300])

    finish(out)


def finish(out):
    text = "\n".join(out) + "\n"
    OUT.write_text(text, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
