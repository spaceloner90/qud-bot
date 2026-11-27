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


RETRY_TURNS = 300  # "unreachable" means unreachable now (the user, 2026-11-27): try again after this long


def unreachable(world, zone, turn=None):
    """Items given up on in this zone, kept in the run's world file (2026-11-27: stage memory forgot them on
    every plan change, so each restart walked back to the same loot across deep water and stalled), as
    {key: turn}. With turn, only the give-ups younger than RETRY_TURNS (older ones are tried again)."""
    store = world.data.setdefault("unreachable", {})
    d = store.get(zone or "?")
    if not isinstance(d, dict):  # the first version kept a plain list: those are retried
        d = store[zone or "?"] = {}
    if turn is None:
        return d
    return {k for k, t in d.items() if turn - t < RETRY_TURNS}


def deep(world, zone):
    """Items in or beyond deep water, kept per zone: fetched only when swimming is safe (args.swim_ok)."""
    return world.data.setdefault("deep", {}).setdefault(zone or "?", [])


def give_up(c, world, zone, key, turn=0):
    c["tried"].append(key)
    c["target"] = None
    unreachable(world, zone)[key] = turn


CONTAINER = re.compile(r"\b(chest|locker|coffer|strongbox|crate|footlocker)\b")
DIR_KEY = {(0, -1): "Keypad8", (1, -1): "Keypad9", (1, 0): "Keypad6", (1, 1): "Keypad3", (0, 1): "Keypad2",
           (-1, 1): "Keypad1", (-1, 0): "Keypad4", (-1, -1): "Keypad7", (0, 0): "Keypad5"}
ROW = re.compile(r"\b([a-z])\)\s+(.+?)\s{2,}")


def menu_signature(state):
    """What a menu shows, without the map round it: the lettered rows and popup lines. The whole screen
    isn't a fair comparison: the map's water glyphs change from one snapshot to the next (2026-11-27: a
    stale "g) get" menu looked new, a second g went to the cell's own list and picked up the chest)."""
    rows = (state.get("screen") or {}).get("rows", [])
    sig = []
    for r in rows:
        sig += [m.group(0) for m in ROW.finditer(r)]
        if "▌" in r:
            sig.append(r[r.index("▌"):r.rindex("▐") + 1] if "▐" in r else r[r.index("▌"):])
    return "\n".join(sig)


def opened(world, zone):
    """Containers already opened (or given up on) in this zone, kept in the run's world file."""
    return world.data.setdefault("opened", {}).setdefault(zone or "?", [])


def chest_step(state, c, world, zone, px, py, swim_ok=False):
    """Open the nearest unopened container of this zone and take what's in it, one key per call (found by
    hand on 2026-11-27: stand on or next to it, CmdGetFrom, the direction, its letter in "Select an item",
    "o) open"; an empty one asks "There's nothing in that. Would you like to store an item?" (n); in a
    full one each item's letter, then "g) get"; Escape back to the map). Returns lines, or None when no
    container is left."""
    ch = c.get("chest")
    screen = "\n".join((state.get("screen") or {}).get("rows", []))
    rows = [(m.group(1), m.group(2).strip()) for r in (state.get("screen") or {}).get("rows", []) for m in [ROW.search(r)] if m]

    def finish(say):
        if ch.get("key") not in opened(world, zone):
            opened(world, zone).append(ch["key"])
        ch["phase"] = "close"
        return [f"SAY {say}"] + (["KEY Escape"] if state.get("wait") == "key" else [])

    if ch and ch.get("phase") and ch["phase"] != "approach":
        ch["keys"] = ch.get("keys", 0) + 1  # menu keys only: walking there has its own give-up (2026-11-27)
        if ch["keys"] > 40:  # never loop in a menu
            return finish(f"Giving up on the {ch['name']}: its menus didn't go as expected.")
        ph = ch["phase"]
        # The snapshot right after a key can still show the screen before it (game_facts.md): never press
        # again on an unchanged screen ("g" twice would pick the item lettered g).
        if ph not in ("close", "approach") and state.get("wait") == "key":
            sig = menu_signature(state)
            if sig == ch.get("seen_screen"):
                return ["WAIT"]
            ch["seen_screen"] = sig
        if ph == "close":
            if state.get("wait") == "map":
                c["chest"] = None
                return []
            return ["KEY Escape"]
        if state.get("wait") == "map" and ph not in ("approach", "interact"):
            # Back on the map mid-way (a menu closed by itself): count it as done.
            c["chest"] = None
            if ch["key"] not in opened(world, zone):
                opened(world, zone).append(ch["key"])
            return []
        if ph == "interact":  # CmdGetFrom sent: "Interact [Select a direction]"
            if "Select a direction" in screen:
                ch["phase"] = "cell"
                return [f"KEY {DIR_KEY[(ch['x'] - px, ch['y'] - py)]}"]
            return ["WAIT"] if ch["keys"] < 4 else finish(f"No direction prompt for the {ch['name']}.")
        if ph == "cell":
            want = W.kind_name(ch["name"])
            hit = next((k for k, n in rows if W.kind_name(n).startswith(want)), None)
            if hit:
                ch["phase"] = "menu"
                return [f"KEY {hit}"]
            if "o) open" in screen:  # the only thing there: its menu came straight up
                ch["phase"] = "opened"
                return ["KEY o"]
            return ["WAIT"] if ch["keys"] < 4 else finish(f"Couldn't find the {ch['name']} in the list.")
        if ph == "menu":
            if "o) open" in screen:
                ch["phase"] = "opened"
                return ["KEY o"]
            return ["WAIT"] if ch["keys"] < 6 else finish(f"The {ch['name']} has no open option.")
        if ph in ("opened", "take"):
            if "nothing in that" in screen:  # "... Would you like to store an item?": no
                return finish(f"The {ch['name']} is empty.")[:1] + ["KEY n"]
            if "o) open" in screen:
                # The container's own menu again (after the last item the game goes back to the cell's list
                # with the chest's menu up): its "g) get" would pick up the chest itself (2026-11-27).
                return finish(f"Emptied the {ch['name']} ({ch.get('took', 0)} item(s)).")
            if "g) get" in screen:
                ch["phase"] = "take"
                ch["took"] = ch.get("took", 0) + 1
                return ["KEY g"]
            items = [(k, n) for k, n in rows if not n.startswith("[")]
            if any(W.kind_name(n).startswith(W.kind_name(ch["name"])) for k, n in items):
                return finish(f"Emptied the {ch['name']} ({ch.get('took', 0)} item(s)).")  # back in the cell's list
            if items:
                return [f"KEY {items[0][0]}"]
            return finish(f"Emptied the {ch['name']} ({ch.get('took', 0)} item(s)).")

    if state.get("wait") != "map":
        return None
    turn = state.get("turn") or 0
    done = set(opened(world, zone)) | unreachable(world, zone, turn) | (set() if swim_ok else set(deep(world, zone)))
    boxes = [o for o in world.objects_in(zone) if CONTAINER.search(W.kind_name(o["name"]))
             and f"{o['x']},{o['y']},{o['name']}" not in done]
    if not boxes:
        return None
    o = min(boxes, key=lambda o: max(abs(o["x"] - px), abs(o["y"] - py)))
    key = f"{o['x']},{o['y']},{o['name']}"
    if not ch or ch.get("key") != key:
        ch = c["chest"] = {"key": key, "name": o["name"], "x": o["x"], "y": o["y"], "phase": "approach", "steps": 0}
    d = max(abs(o["x"] - px), abs(o["y"] - py))
    if d <= 1:
        ch["phase"] = "interact"
        ch["keys"] = 0
        c["target"] = None
        return [f"SAY Opening the {o['name']} at ({o['x']},{o['y']}).", "CMD CmdGetFrom"]
    # Walking there, with the item give-up rules (and the swim check at the top of step()).
    c["target"] = key
    ch["steps"] += 1
    if ch["steps"] > 80 or (ch.get("last_pos") == [px, py] and ch["steps"] > 3):
        c["chest"] = None
        give_up(c, world, zone, key, turn)
        return [f"SAY Cannot reach the {o['name']} at ({o['x']},{o['y']}) for now; leaving it."]
    ch["last_pos"] = [px, py]
    return ([f"SAY Going to open the {o['name']} at ({o['x']},{o['y']})."] if ch["steps"] == 1 else []) + [f"GOTO {o['x']} {o['y']}"]


def step(state, memory, world, args, mkey="collect", only=None, max_dist=None):
    """mkey: the memory slot ("collect" for the end-of-zone sweep, "gear" for the early gear grab);
    only: a regex the item's kind must match; max_dist: ignore items further than this."""
    c = memory.setdefault(mkey, {"tried": [], "taken": [], "steps": 0})
    p = state.get("player") or {}
    zone, px, py = p.get("zone"), p.get("x"), p.get("y")
    # Walking to an item, the game's path asked to swim ("There is a deep pool ... Move ... again to enter it
    # and start swimming"). Swimming is fine when the zone is quiet (the user, 2026-11-27: what we accept
    # depends on how sure we are of what's around): explore sets args.swim_ok (nothing that moves or shoots
    # known near, full HP, no fight lately). Then the same step again goes in. Otherwise the item is
    # marked "deep" and fetched later, when it's safe.
    here = [px, py, state.get("turn")]
    # Only a prompt new since the last call counts: the message log keeps old lines, and an old swim
    # prompt marked dry loot (a chest we had just dropped at our feet) as deep (2026-11-27).
    from scripts import fight as _fight
    fresh = _fight.new_messages(state, c.setdefault("seen_msgs", {}))
    if (c.get("target") and c.get("swim_at") != here
            and any("start swimming" in m for m in fresh)):
        c["swim_at"] = here
        key = c["target"]
        name = key.split(",", 2)[2]
        if args.get("swim_ok"):
            tx, ty = key.split(",")[:2]
            return [f"SAY Nothing dangerous near and full health: swimming out for the {name}.", f"GOTO {tx} {ty}"], None, False
        c["target"] = None
        if key not in deep(world, zone):
            deep(world, zone).append(key)
        return [f"SAY The {name} is across deep water: leaving it until the zone is quiet enough to swim."], None, False

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
        # Say so (2026-11-27: the sweep ended at once as "picked up 0 item(s)" at 299/369 lbs, no reason given)
        c["load_full"] = f"{ld[0]}/{ld[1]} lbs"
        return [], None, True

    # Containers first (2026-11-27: chests were never opened; one held the short bow we lacked). Only in
    # the end-of-zone sweep, not the early gear grab.
    if mkey == "collect" and args.get("open_containers", True):
        lines = chest_step(state, c, world, zone, px, py, args.get("swim_ok", False))
        if lines is not None:
            return lines, None, False

    gone = unreachable(world, zone, state.get("turn") or 0) | (set() if args.get("swim_ok") else set(deep(world, zone)))
    items = [o for o in world.objects_in(zone) if lootable(world, o["name"])
             and f"{o['x']},{o['y']},{o['name']}" not in c["tried"]
             and f"{o['x']},{o['y']},{o['name']}" not in gone
             and (only is None or only.search(W.kind_name(o["name"])))
             and (max_dist is None or max(abs(o["x"] - px), abs(o["y"] - py)) <= max_dist)]
    if not items:
        return [], None, True
    o = min(items, key=lambda o: max(abs(o["x"] - px), abs(o["y"] - py)))
    key = f"{o['x']},{o['y']},{o['name']}"

    if (o["x"], o["y"]) == (px, py):
        c["got"] = {"key": key, "name": o["name"]}
        c["steps"], c["target"] = 0, None
        return ["CMD CmdGet"], None, False

    # Walking there: give up on one that takes too long (a long way round, or blocked).
    if c.get("target") != key:
        c["target"], c["steps"], c["last_pos"] = key, 0, None
    c["steps"] += 1
    if c["steps"] > args.get("max_walk", 80) or c.get("last_pos") == [px, py] and c["steps"] > 3:
        give_up(c, world, zone, key, state.get("turn") or 0)
        return [f"SAY Cannot reach {o['name']} at ({o['x']},{o['y']}) for now; leaving it."], None, False
    c["last_pos"] = [px, py]
    lines = [f"GOTO {o['x']} {o['y']}"]
    if c["steps"] == 1:
        lines.insert(0, f"SAY Gear in sight: going for the {o['name']} at ({o['x']},{o['y']}) now rather than at the end of the zone." if mkey == "gear"
                     else f"SAY Zone explored; collecting what autoget left: {o['name']} at ({o['x']},{o['y']}), {len(items)} items to check.")
    return lines, None, False
