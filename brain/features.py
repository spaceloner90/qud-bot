"""New things in view to evaluate (the user, 2026-11-26: note all new liquids and terrain features and
evaluate whether there's anything notable we could do with them; a cider weep and a wine weep on a
peaceful surface could have filled every container and solved money at the start).

Each base liquid ("puddle of 12 drams of salty cider" -> "cider") and each non-liquid feature kind is
evaluated once, ever: game knowledge keeps "liquid_kinds" and "feature_kinds" with the LLM's note (not "features":
that key is the world file's per-run map features). A kind not yet
known goes into the run's "to_evaluate" list; explore says so, and every hand-over carries the list until
the LLM records a note with `python tools/world.py evaluate liquid|feature "<kind>" "<note>"`. Nothing here stops a run.
"""
import re

LIQUID = re.compile(r"^(?:deep |frozen )?(?:pool|puddle|vase)\b")
MIXERS = {"salty", "brackish", "dilute", "bloody", "slimy", "tarry", "sappy", "wet", "oily", "muddy", "sugary"}


def base_liquid(name):
    """'pool of 1000 drams of slimy asphalt' -> 'asphalt'; 'vase [honey]' -> 'honey'; None if not a liquid."""
    n = (name or "").lower()
    if not LIQUID.search(n):
        return None
    m = re.search(r"\[(.+?)\]", n)
    if m:
        inner = re.sub(r"\d+ drams? of\s*", "", m.group(1)).split()
        return " ".join(w for w in inner if w not in MIXERS) or None
    tail = re.sub(r"^.*?\bof\b\s*", "", n)
    tail = re.sub(r"\d+ drams? of\s*", "", tail)
    words = [w for w in tail.split() if w not in MIXERS]
    return " ".join(words) or None


def feature_kind(name):
    """A non-liquid feature's kind: the name without a leading 'wet '/'sappy ' etc."""
    words = (name or "").lower().split()
    while words and words[0] in MIXERS:
        words.pop(0)
    return " ".join(words)


def scan(state, world):
    """Add unknown liquids and feature kinds in view to world.data["to_evaluate"]; returns the new ones."""
    p = state.get("player") or {}
    zone = p.get("zone") or ""
    if "." not in zone:  # the world map: its tiles are listed as features
        return []
    known_l = world.data.setdefault("liquid_kinds", {})
    known_f = world.data.setdefault("feature_kinds", {})
    pending = world.data.setdefault("to_evaluate", [])
    new = []
    for ft in (state.get("map") or {}).get("features") or []:
        name = ft.get("name") or ""
        liq = base_liquid(name)
        if liq:
            key, known = "liquid: " + liq, known_l
            kind = liq
        else:
            kind = feature_kind(name)
            if not kind or kind.startswith("["):
                continue
            key, known = "feature: " + kind, known_f
        if kind in known or any(e["key"] == key for e in pending):
            continue
        entry = {"key": key, "kind": kind, "example": name, "x": ft.get("x"), "y": ft.get("y"),
                 "zone": zone, "turn": state.get("turn")}
        pending.append(entry)
        new.append(entry)
    return new


def pending_text(world, limit=6):
    pending = (world.data.get("to_evaluate") or []) if world is not None else []
    if not pending:
        return ""
    shown = ", ".join(f"{e['kind']} ({e['example']} at {e['x']},{e['y']})" for e in pending[:limit])
    more = f" and {len(pending) - limit} more" if len(pending) > limit else ""
    return f" [new to evaluate: {shown}{more}]"
