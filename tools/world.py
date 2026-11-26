"""Read and annotate the world file of the current run (runs/<run id>/world.json).

  python tools/world.py                         summary of the current run's world
  python tools/world.py note "<about>" "<text>" add a fact (about a person, place, quest...)
  python tools/world.py food add "<name>"       a food the bot may eat on its own when hungry
  python tools/world.py evaluate liquid|feature "<kind>" "<note>"  a new one's use (clears it from to_evaluate)
  python tools/world.py pending                 the liquids and features still to evaluate
  python tools/world.py backfill                feed every logged snapshot of this run into it (no live run!)

note, kind and food are queued (runs/<id>/edits.jsonl) and applied by the bot on its next call, so they
never collide with the live bot rewriting world.json.
  python tools/world.py kind "<name>" fight difficulty=Average mobile=no effect="You are grabbed"
                                                set what we know about a kind of creature (verdict:
                                                fight, avoid or ask); the fight routine reads it

The current run is the one in live/state.json.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "brain"))
import world as W  # noqa: E402


def latest_state():
    return json.loads((ROOT / "live" / "state.json").read_text(encoding="utf-8"))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    state = latest_state()
    w = W.load(state, apply=False)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cmd == "note":
        p = state.get("player") or {}
        W.queue_edit(w.id, {"op": "note", "about": sys.argv[2], "text": sys.argv[3], "turn": state.get("turn"), "zone": p.get("zone")})
        print(f"queued note about {sys.argv[2]}: {sys.argv[3]}")
        return
    if cmd == "food":
        # food add|remove "<name>": foods the bot may eat on its own when hungry
        W.queue_edit(w.id, {"op": "food", sys.argv[2]: [sys.argv[3]]})
        print(f"queued food {sys.argv[2]} {sys.argv[3]}")
        return
    if cmd == "kind":
        # kind "<name>" <fight|avoid|ask> [difficulty=Average] [mobile=yes|no] [effect="You are grabbed"]...
        fields, effects = {}, []
        for a in sys.argv[4:]:
            key, _, value = a.partition("=")
            if key == "effect":
                effects.append(value)
            elif key == "mobile":
                fields["mobile"] = value.lower() in ("yes", "true", "1")
            elif value.lower() in ("yes", "no", "true", "false"):
                fields[key] = value.lower() in ("yes", "true")
            else:
                try:
                    fields[key] = float(value) if "." in value else int(value)
                except ValueError:
                    fields[key] = value
        fields["verdict"] = sys.argv[3]
        W.queue_edit(w.id, {"op": "kind", "name": sys.argv[2], "fields": fields, "effects": effects})
        print(f"queued kind {W.kind_name(sys.argv[2])}: {fields}" + (f", effects {effects}" if effects else ""))
        return
    if cmd == "evaluate":
        # python tools/world.py evaluate liquid|feature "<kind>" "<note>": what a new liquid or feature is good for
        if sys.argv[2] not in ("liquid", "feature"):
            print("usage: world.py evaluate liquid|feature \"<kind>\" \"<note>\"")
            return
        W.queue_edit(w.id, {"op": "evaluate", "type": sys.argv[2], "kind": sys.argv[3].lower(), "note": sys.argv[4], "turn": state.get("turn")})
        print(f"queued evaluation of {sys.argv[2]} {sys.argv[3]}: {sys.argv[4]}")
        return
    if cmd == "pending":
        for e in w.data.get("to_evaluate") or []:
            print(f"  {e['key']}: {e['example']} at {e['zone']} ({e['x']},{e['y']}), turn {e['turn']}")
        return
    if cmd == "backfill":
        # writes world.json directly: only use while no bot run is live
        rid, n = w.id, 0
        for line in (ROOT / "live" / "log.jsonl").open(encoding="utf-8"):
            try:
                s = json.loads(line).get("state")
            except json.JSONDecodeError:
                continue
            if isinstance(s, dict) and s.get("player") and W.run_id(s) in (rid, W.run_id({"player": s["player"]})):
                w.update(s)
                n += 1
        w.save()
        print(f"backfilled {n} snapshots into {w.path}")
        return
    d = w.data
    pending = W.RUNS / w.id / "edits.jsonl"
    if pending.exists():
        print(f"({len(pending.read_text(encoding='utf-8').splitlines())} queued edits not applied yet: the bot applies them on its next call)")
    print(f"food the bot may eat: {d.get('food', [])}")
    print(f"run {w.id}: {d['run'].get('player')}, level {d['run'].get('level')}, last turn {d['run'].get('last_turn')}")
    print(f"zones ({len(d['zones'])}):")
    for zid, z in d["zones"].items():
        print(f"  {z.get('name')} [{zid}] turns {z.get('first_turn')}-{z.get('last_turn')}" + (f" {z.get('status')}" if z.get("status") else ""))
    print(f"creatures ({len(d['creatures'])}):")
    for c in sorted(d["creatures"].values(), key=lambda c: (c["zone"], c["name"])):
        print(f"  {c['glyph']} {c['name']}{' HOSTILE' if c.get('hostile') else ''} at {d['zones'].get(c['zone'], {}).get('name')} ({c['x']},{c['y']}) turn {c['last_turn']}")
    kinds = {}
    for o in d["objects"].values():
        kinds.setdefault(o["name"], []).append(o)
    print(f"objects ({len(d['objects'])}): " + ", ".join(f"{k} x{len(v)}" for k, v in sorted(kinds.items())))
    print(f"quests ({len(d['quests'])}): " + "; ".join(q.get("name", "?") + (" (done)" if q.get("finished") else "") for q in d["quests"]))
    print(f"kinds ({len(d.get('kinds', {}))}):")
    for name, k in sorted(d.get("kinds", {}).items()):
        print(f"  {name}: {k.get('verdict')}, {k.get('difficulty', '?')}, {'mobile' if k.get('mobile') else 'stays put' if k.get('mobile') is False else 'movement ?'}, "
              f"kills {k.get('kills', 0)}, xp {k.get('xp', [])}, max hit {k.get('max_hit', 0)}" + (f", effects {k['effects']}" if k.get("effects") else ""))
    print(f"notes ({len(d['notes'])}):")
    for n in d["notes"]:
        print(f"  [{n.get('about')}] {n.get('text')}")


if __name__ == "__main__":
    main()
