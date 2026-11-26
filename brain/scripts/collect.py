"""Pick up the items remembered in this zone once it's explored (the user's rule, 2026-11-24: note all
items and grab them while carrying capacity isn't a problem). Called by explore when the game says the
zone has nothing left to explore and args.collect is on.

The game's own Autoget already takes food, trade goods, nuggets, artifacts, scrap, ammo and weightless
items while autoexploring; this sweeps up the rest (weapons, armour, books on the floor...).

Which items: the run's world file remembers every object seen per zone (and forgets one once its cell
is in view without it). Not furniture, terrain, corpses or junk (SKIP), and not kinds the world file
marks "skip" in data["loot"] (set by the LLM, or learned here when a pickup fails). Kinds marked
"take" are always tried.

One action per call: GOTO the nearest candidate, then CMD CmdGet on its cell, then check the messages
for "You take". Stops when nothing is left, or the load passes args.max_load of capacity (sidebar
"#48/353").

step(state, memory, world, args) returns (lines, why, done):
  lines   the action to play now
  why     a reason to raise the LLM (a pickup failed oddly, an unknown popup...), or None
  done    True when the sweep is finished (then explore reports the zone as done)
"""
import re
import world as W

SKIP = re.compile(
    r"(stairs|door|wall|shelf|chest|table|chair|bed\b|dresser|cushion|basket|sconce|statue|shrine|sign\b|"
    r"tombstone|contraption|boulder|trash|bones|corpse|pool|puddle|well\b|tree\b|grave|altar|fountain|"
    r"brazier|campfire|forge|oven|lever|chime|urn|sarcophagus|pillar|column|machine|terminal|rubble|web\b)")
TAKEN = re.compile(r"^You (take|pick up) ")
# Gear worth taking at once, not at the end-of-zone sweep (the user, 2026-11-24: we walked past an iron
# long sword that doubled our damage for 130 turns). Matched on the kind name.
GEAR = re.compile(
    r"(sword|blade|axe|dagger|knife|club|mace|hammer|cudgel|staff|spear|halberd|whip|flail|"
    r"bow|musket|rifle|pistol|carbine|"
    r"armor|armour|mail|leather|plate|cap|helm|hat|boots|shoes|sandals|gloves|gauntlets|bracers|"
    r"cloak|cape|shield|buckler|robe|vest|furs|overalls|apron|mask|goggles|girdle|belt)")
LOAD = re.compile(r"#(\d+)\s*/\s*(\d+)")


def load(state):
    for r in (state.get("screen") or {}).get("rows", []):
        m = LOAD.search(r)
        if m and int(m.group(2)) > 0:
            return int(m.group(1)), int(m.group(2))
    return None


def lootable(world, name):
    kind = W.kind_name(name)
    verdict = (world.data.get("loot") or {}).get(kind, {}).get("verdict")
    if verdict == "skip":
        return False
    if verdict == "take":
        return True
    return not SKIP.search(kind)


def step(state, memory, world, args, mkey="collect", only=None, max_dist=None):
    """mkey: the memory slot ("collect" for the end-of-zone sweep, "gear" for the early gear grab);
    only: a regex the item's kind must match; max_dist: ignore items further than this."""
    c = memory.setdefault(mkey, {"tried": [], "taken": [], "steps": 0})
    p = state.get("player") or {}
    zone, px, py = p.get("zone"), p.get("x"), p.get("y")

    # The pickup sent last call: did it work?
    # Several things on the cell: CmdGet opens "Select an item" (2026-11-24: a corpse and a foreleg).
    # The item's letter opens its menu, "g) get" takes it, then the list stays open: Escape.
    screen = "\n".join((state.get("screen") or {}).get("rows", []))
    if c.get("got") and state.get("wait") == "key" and "not owned by you" in screen:
        # Someone else's (2026-11-26: a canteen in Joppa): taking it is theft. Decline, leave this one.
        pending = c.pop("got")
        c["tried"].append(pending["key"])
        return [f"SAY {pending['name']} belongs to someone here: leaving it.", "KEY Escape"], None, False
    if c.get("got") and state.get("wait") == "key" and "nothing to take" in screen:
        # A fixture, not loot (2026-11-26: a brinestalk gate, retried after every plan change): skip the kind.
        pending = c.pop("got")
        c["tried"].append(pending["key"])
        world.data.setdefault("loot", {})[W.kind_name(pending["name"])] = {
            "verdict": "skip", "why": "There's nothing to take.", "turn": state.get("turn")}
        return [f"SAY {pending['name']} can't be taken: skipping that kind.", "KEY Space"], None, False
    if c.get("got") and state.get("wait") == "key":
        want = W.kind_name(c["got"]["name"])
        if "g) get" in screen and c["got"].get("picked"):
            return ["KEY g"], None, False
        if "Select an item" in screen:
            if c["got"].get("picked"):
                return ["KEY Escape"], None, False
            for r in (state.get("screen") or {}).get("rows", []):
                m = re.search(r"\b([a-z])\)\s+(.+?)\s{2,}", r)
                if m and W.kind_name(m.group(2)).startswith(want):  # the row adds stats ("♦1 ○2")
                    c["got"]["picked"] = True
                    return [f"KEY {m.group(1)}"], None, False
            c["got"]["picked"] = True  # not in the list: close it and count it as not taken
            return ["KEY Escape"], None, False
    pending = c.pop("got", None)
    if pending:
        new = (state.get("messages") or [])[-4:]
        took = [m for m in new if TAKEN.match(m)]
        c["tried"].append(pending["key"])
        if took:
            c["taken"].append(pending["name"])
            return [f"SAY Picked up {pending['name']}."], None, False
        # Nothing taken. Only a refusal the game spells out marks the whole kind skip (a bug of ours once
        # marked cloth overalls skip from one failed pile, 2026-11-24); otherwise just this item.
        said = " ".join(new)
        if re.search(r"can't|cannot|too heavy|unable|not able", said, re.I):
            kind = W.kind_name(pending["name"])
            world.data.setdefault("loot", {})[kind] = {"verdict": "skip", "why": said[-120:], "turn": state.get("turn")}
            return [f"SAY couldn't pick up {pending['name']} ({said[-60:]}): skipping that kind"], None, False
        return [f"SAY Did not get {pending['name']}; moving on to the next item."], None, False

    ld = load(state)
    if ld and ld[0] >= args.get("max_load", 0.8) * ld[1]:
        return [], None, True

    items = [o for o in world.objects_in(zone) if lootable(world, o["name"])
             and f"{o['x']},{o['y']},{o['name']}" not in c["tried"]
             and (only is None or only.search(W.kind_name(o["name"])))
             and (max_dist is None or max(abs(o["x"] - px), abs(o["y"] - py)) <= max_dist)]
    if not items:
        return [], None, True
    o = min(items, key=lambda o: max(abs(o["x"] - px), abs(o["y"] - py)))
    key = f"{o['x']},{o['y']},{o['name']}"

    if (o["x"], o["y"]) == (px, py):
        c["got"] = {"key": key, "name": o["name"]}
        c["steps"] = 0
        return ["CMD CmdGet"], None, False

    # Walking there: give up on one that takes too long (a long way round, or blocked).
    if c.get("target") != key:
        c["target"], c["steps"], c["last_pos"] = key, 0, None
    c["steps"] += 1
    if c["steps"] > args.get("max_walk", 80) or c.get("last_pos") == [px, py] and c["steps"] > 3:
        c["tried"].append(key)
        return [f"SAY Cannot reach {o['name']} at ({o['x']},{o['y']}); leaving it."], None, False
    c["last_pos"] = [px, py]
    lines = [f"GOTO {o['x']} {o['y']}"]
    if c["steps"] == 1:
        lines.insert(0, f"SAY Gear in sight: going for the {o['name']} at ({o['x']},{o['y']}) now rather than at the end of the zone." if mkey == "gear"
                     else f"SAY Zone explored; collecting what autoget left: {o['name']} at ({o['x']},{o['y']}), {len(items)} items to check.")
    return lines, None, False
