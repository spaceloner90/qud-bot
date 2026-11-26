"""The hand-over digest: everything a decision point needs, in one call, instead of reading the raw
live/state.json (mostly screen buffer and colours) plus the narration log, the world file and the
knowledge (suggested by the Gemini/Antigravity handover, 2026-11-26).

  python tools/brief.py              the digest
  python tools/brief.py --radius 12  a wider map crop around @ (default 8; 0 for no map)
  python tools/brief.py --full       the whole zone map

Sections follow AGENTS.md's decision-point checklist: why we stopped; the character (HP, XP, food,
effects); every ability with its cooldown; the map around @; every creature in view with our verdict
and the threat estimate; items, stairs and doors in view; liquids and features still to evaluate; the
whole pack and what's equipped; open quests with their next step; the last messages and narration.
It only reads files: safe at any time, with or without a run.
"""
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIVE = ROOT / "live"
sys.path.insert(0, str(ROOT / "brain"))  # the brain's world.py, not tools/world.py
import world as W  # noqa: E402

TAGS = re.compile(r"\{\{\w\||\}\}|&\w|\^\w")
CTRL = re.compile(r"[\x00-\x08\x0b-\x1f]")  # the game's stat glyphs in item names (-> ♦ ○ ♥)


def load(path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def clean(s):
    """Item names carry the game's stat glyphs: '\\x04 2 \\t -1' is AV/DV, '\\x1a 5' penetration, '\\x03 1d2'
    damage. Spell them out."""
    s = TAGS.sub("", str(s or ""))
    s = re.sub(r"\x04(-?\d+)\s*\t(-?\d+)", r"[AV \1 DV \2]", s)
    s = re.sub(r"\x1a(\d+)", r"[pen \1]", s)
    s = re.sub(r"\x03(\d+d\d+(?:[+-]\d+)?)", r"[dmg \1]", s)
    return re.sub(r"\s+", " ", CTRL.sub(" ", s)).strip()


def tail(path, n):
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except FileNotFoundError:
        return []


def dist(a, b):
    return max(abs(a.get("x", 0) - b.get("x", 0)), abs(a.get("y", 0) - b.get("y", 0)))


def section(title):
    print(f"\n## {title}")


def run_line():
    try:
        sys.path.insert(1, str(ROOT / "tools"))
        import send
        active, why = send.run_status()
        return ("active" if active else "not active") + f" ({why})"
    except Exception as e:  # never let the digest fail on this
        return f"unknown ({e})"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=int, default=8)
    ap.add_argument("--full", action="store_true")
    a = ap.parse_args()

    s = load(LIVE / "state.json")
    if not s:
        print("no snapshot (live/state.json): the game hasn't asked the brain yet")
        return 1
    p = s.get("player") or {}
    world = W.load(s, apply=False)
    turn = s.get("turn") or 0
    plan = load(ROOT / "brain" / "plan.json", {}) or {}
    stages = [st.get("script") for st in (plan.get("stages") or [plan])]

    # ---- why we're here ----
    print(f"# {clean(p.get('name'))}, turn {turn}, {p.get('zoneName')} ({p.get('zone')}) at ({p.get('x')},{p.get('y')})")
    print(f"run: {run_line()}; waiting at: {s.get('wait')}; plan: {plan.get('label')!r} stages {stages}")
    print(f"objective: {plan.get('objective')} | goal: {plan.get('goal')}")
    ho = load(LIVE / "handover.json")
    if ho:
        age = turn - (ho.get("turn") or turn)
        print(f"last hand-over (#{ho.get('n')}, {age} turns ago): {ho.get('reason')}")

    # ---- the character ----
    section("Character")
    rows = (s.get("screen") or {}).get("rows") or []
    xp = next((m.groups() for r in rows for m in [re.search(r"XP:\s*(\d+)\s*/\s*(\d+)", r)] if m), None)
    prof = (world.data.get("run") or {}).get("profile") or {}
    if not xp and prof.get("xp") is not None:
        xp = (prof.get("xp"), prof.get("xp_next"))
    print(f"level {p.get('level')}  XP {'/'.join(map(str, xp)) if xp else '?'}  HP {p.get('hp')}/{p.get('maxhp')}  "
          f"AV {p.get('av')} DV {p.get('dv')}  QN {p.get('qn')} MS {p.get('ms')}  {p.get('food')}, {p.get('water')}")
    print("effects:", ", ".join(p.get("effects") or []) or "none")
    stats = prof.get("stats") or {}
    attrs = {k: stats[k] for k in ("ST", "AG", "TO", "IN", "WI", "EG") if k in stats}
    if attrs:
        print("attributes:", " ".join(f"{k} {v}" for k, v in attrs.items()))

    # ---- abilities: the whole list, for the ability review ----
    section("Abilities (cooldowns are our guess from last use; the abilities list in game is the authority)")
    profile = load(ROOT / "runs" / world.id / "profile.json", {}) or {}
    cur = profile.get("current") or {}
    try:
        sys.path.insert(1, str(ROOT / "brain" / "scripts"))
        from fight import COOLDOWN
    except Exception:
        COOLDOWN = {}
    ready_at = world.data.get("cooldowns") or {}  # the turn each ability is ready again (fight.cooldowns)
    for name, length in COOLDOWN.items():
        left = (ready_at[name] - turn) if name in ready_at else None
        state = "ready" if left is None or left <= 0 else f"about {left} turns left"
        print(f"  {name}: {state} (cooldown {length})")
    if cur:
        print("  mutations:", ", ".join(f"{k} {v}" for k, v in (cur.get("mutations") or {}).items()))
        print("  skills:", ", ".join(cur.get("skills") or []))
        pts = {k: v for k, v in (cur.get("points") or {}).items() if v}
        if pts:
            print("  UNSPENT POINTS:", pts)
        if cur.get("level") != p.get("level"):
            print(f"  (profile is from level {cur.get('level')}: run tools/profile.py after a level-up)")

    # ---- the map ----
    m = s.get("map") or {}
    mrows = m.get("rows") or []
    if mrows and (a.full or a.radius > 0):
        x0, y0 = p.get("x", 0), p.get("y", 0)
        if a.full:
            xs, ys = range(0, len(mrows[0])), range(0, len(mrows))
        else:
            r = a.radius
            xs = range(max(0, x0 - 2 * r), min(len(mrows[0]), x0 + 2 * r + 1))
            ys = range(max(0, y0 - r), min(len(mrows), y0 + r + 1))
        section(f"Map x {xs.start}-{xs.stop - 1}, y {ys.start}-{ys.stop - 1} (@ is us; read terrain from features, not glyphs)")
        for y in ys:
            row = mrows[y]
            line = "".join("@" if (x, y) == (x0, y0) else (row[x] if x < len(row) else " ") for x in xs)
            print(f"{y:2} {line.rstrip()}")

    # ---- creatures ----
    objs = m.get("objects") or []
    creatures = sorted((o for o in objs if o.get("creature")), key=lambda o: dist(o, p))
    section(f"Creatures in view ({len(creatures)})")
    try:
        import threat
    except Exception:
        threat = None
    for o in creatures:
        k = world.kind(o.get("name") or "") or {}
        tag = "HOSTILE" if o.get("hostile") else "not hostile"
        seen = "" if o.get("seen", True) else " (hidden: not visible to the eye)"
        print(f"- {o.get('name')} at ({o.get('x')},{o.get('y')}), {dist(o, p)} away, {tag}{seen}: "
              f"HP {o.get('hp')}/{o.get('maxhp')} AV {o.get('av')} DV {o.get('dv')} lvl {o.get('lvl')} "
              f"[{clean(o.get('diff'))}] MS {o.get('ms')}")
        atk = ", ".join(f"{t.get('name')} {t.get('dmg')}" for t in o.get("attacks") or [])
        extra = [f"attacks {atk}" if atk else "", "effects " + ", ".join(o["effects"]) if o.get("effects") else "",
                 "mutations " + ", ".join(o["mutations"]) if o.get("mutations") else ""]
        print("    " + "; ".join(e for e in extra if e))
        known = (f"known kind: verdict {k.get('verdict')}, kills {k.get('kills', 0)}, max hit {k.get('max_hit')}"
                 + (f", note: {k.get('note')}" if k.get("note") else "")) if k else "NEW KIND: not in game knowledge, evaluate it"
        print("    " + known)
        if threat and o.get("hostile"):
            try:
                print("    estimate: " + threat.estimate(s, world, o, [c for c in creatures if c is not o and c.get("hostile")]).get("why", ""))
            except Exception as e:
                print(f"    estimate failed: {e}")

    # ---- items, stairs, doors ----
    things = sorted((o for o in objs if not o.get("creature")), key=lambda o: dist(o, p))
    section(f"Items, stairs and doors in view ({len(things)})")
    for o in things[:25]:
        print(f"- {clean(o.get('name'))} at ({o.get('x')},{o.get('y')}), {dist(o, p)} away")
    if len(things) > 25:
        print(f"  ... and {len(things) - 25} more")

    # ---- features ----
    feats = m.get("features") or []
    section(f"Features in view ({len(feats)})")
    counts = {}
    for f in feats:
        counts.setdefault(clean(f.get("name")), []).append((f.get("x"), f.get("y")))
    for name, cells in sorted(counts.items(), key=lambda kv: -len(kv[1]))[:20]:
        near = min(cells, key=lambda c: dist({"x": c[0], "y": c[1]}, p))
        print(f"- {name} x{len(cells)} (nearest {near})")
    pending = world.data.get("to_evaluate") or []
    if pending:
        print("TO EVALUATE (tools/world.py evaluate liquid|feature \"<kind>\" \"<note>\"):")
        for e in pending:
            print(f"  {e['key']}: {e['example']} at {e['zone']} ({e['x']},{e['y']})")

    # ---- gear: the whole pack, for the inventory review ----
    section("Equipped")
    for e in s.get("equipped") or []:
        print("- " + clean(e))
    section(f"Pack ({len(s.get('inventory') or [])} entries; review every item: what could it do for us now?)")
    for e in s.get("inventory") or []:
        print("- " + clean(e))

    # ---- quests ----
    section("Open quests")
    for q in s.get("quests") or []:
        if q.get("finished"):
            continue
        nxt = next((st for st in q.get("steps") or [] if not st.get("finished")), None)
        origin = ", ".join(str(x) for x in (q.get("giver"), q.get("where")) if x)
        print(f"- {q.get('name')}" + (f" (from {origin})" if origin else "")
              + (f": next, {nxt.get('name')}: {nxt.get('text')}" if nxt else ""))

    # ---- recent ----
    section("Last messages")
    for msg in (s.get("messages") or [])[-8:]:
        print("- " + clean(msg))
    section("Last narration (live/narration.log)")
    for line in tail(LIVE / "narration.log", 8):
        print("  " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
