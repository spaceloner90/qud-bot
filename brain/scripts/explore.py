"""Explore the current zone with the game's own autoexplore, and hand back to the LLM at anything new.

Each call gives at most one action (on the map an action clears anything queued behind it). While
autoexplore runs, the mod doesn't ask the brain at all, so the brain sees the game each time it stops.

Stops (each STOP reason starts with a short tag, so the analyzer can count them):
  goal       player level reached args.goal_level
  popup      a menu, popup or prompt is waiting for a key (wait == "key")
  hostile    a hostile creature is in view
  hurt       HP below args.min_hp_fraction of max
  stuck      autoexplore made no progress twice in a row (zone explored, or something blocks it)
  budget     more than args.max_turns game turns since the plan started

args: {"goal_level": 2, "min_hp_fraction": 0.5, "max_turns": 1000, "hand_off": false, "hunt": true}

hunt (default on): also fight non-hostile creatures whose kind is marked prey in game_knowledge.json (only
while HP is at least rest_fraction of max). Turn it off ("hunt": false) in settlements.

With hand_off, every stop ends the stage instead (NEXT), so the plan's next stage takes over, e.g. the
remote script where the LLM assesses what was found, without the run ending.
"""


# Text in popups that only inform and can be dismissed. Grows as we meet them (check each in a
# stop first, then add it here).
INFO_POPUPS = [
    "You note this piece of information",
]


ZONE_DONE = "anywhere else to explore"

# Effects that take control away (see decide): explore waits them out, a hostile in view raises the LLM.
BAD_EFFECTS = {"terrified", "dazed", "confused", "stunned", "shaken", "paralyzed", "asleep"}

import re
import world  # noqa: E402  (the run's world file, loaded by step.py)
from scripts import fight  # noqa: E402
from scripts import eat  # noqa: E402
from scripts import collect  # noqa: E402
from scripts import cook  # noqa: E402


def interrupt_kinds(state, args):
    """Kinds whose sight should break off the game's autoexplore: prey, while hunting and fighting at
    full HP (rest_fraction) with no bad effect. Empty otherwise."""
    p = state.get("player") or {}
    if not (args.get("hunt", True) and args.get("fight") and world.CURRENT is not None
            and p.get("hp") and p.get("maxhp") and p["hp"] >= args.get("rest_fraction", 1.0) * p["maxhp"]
            and not any(e in BAD_EFFECTS for e in p.get("effects") or [])):
        return []
    kinds = (world.CURRENT.data.get("kinds") or {})
    return sorted(k for k, v in kinds.items() if isinstance(v, dict) and v.get("prey") and v.get("verdict") != "avoid")


def write_interrupts(state, args):
    """live/interrupt.txt for the mod: the radius on the first line, then one kind per line (lower case,
    matched against the creature's display name)."""
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "live" / "interrupt.txt"
    text = f"{args.get('hunt_radius', 12)}\n" + "".join(k.lower() + "\n" for k in interrupt_kinds(state, args))
    try:
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            path.write_text(text, encoding="utf-8")
    except OSError:
        pass


def clear_interrupts():
    """No autoexplore interrupts (any stage other than explore)."""
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "live" / "interrupt.txt"
    try:
        if path.exists() and path.read_text(encoding="utf-8").strip().count("\n") > 0:
            path.write_text("12\n", encoding="utf-8")
    except OSError:
        pass


def ignored(name):
    """Kinds the LLM marked "ignore" (harmless and worthless, e.g. the dreadroot: immobile, no XP, terror
    when attacked): not fought, not a reason to stop, rest or skip cooking."""
    k = world.CURRENT.kind(name) if world.CURRENT is not None else None
    return bool(k and k.get("verdict") == "ignore")


def harmless(name):
    """Kinds the LLM marked harmless (they can't hurt us themselves, e.g. the dreadroot's fear aura)."""
    k = world.CURRENT.kind(name) if world.CURRENT is not None else None
    return bool(k and k.get("harmless"))


DIR8 = {(0, -1): "N", (1, -1): "NE", (1, 0): "E", (1, 1): "SE", (0, 1): "S", (-1, 1): "SW", (-1, 0): "W", (-1, -1): "NW"}


def free_direction(state):
    """A step direction out of a pool: a neighbour with no pool feature and no wall, preferring the one with
    the fewest pools around it; else any neighbour that isn't a wall."""
    p = state.get("player") or {}
    px, py = p.get("x", 0), p.get("y", 0)
    m = state.get("map") or {}
    rows = m.get("rows") or []
    pools = {(f.get("x"), f.get("y")) for f in m.get("features") or [] if "pool" in (f.get("name") or "") or "puddle" in (f.get("name") or "")}
    def open_(x, y):
        return 0 <= y < len(rows) and 0 <= x < len(rows[y]) and rows[y][x] not in "▒#"
    best = None
    for (dx, dy), name in DIR8.items():
        x, y = px + dx, py + dy
        if not open_(x, y):
            continue
        around = sum((x + a, y + b) in pools for a in (-1, 0, 1) for b in (-1, 0, 1))
        score = ((x, y) in pools, around)
        if best is None or score < best[0]:
            best = (score, name)
    return best[1] if best else "S"


def visible_hostiles(state):
    m = state.get("map") or {}
    player = state.get("player") or {}
    px, py = player.get("x", 0), player.get("y", 0)
    found = []
    for o in m.get("objects", []):
        if o.get("creature") and o.get("hostile") and not ignored(o["name"]):
            dist = max(abs(o["x"] - px), abs(o["y"] - py))
            found.append((dist, o))
    return [o for _, o in sorted(found, key=lambda t: t[0])], px, py


def known_threats(state, radius):
    """Hostiles the world file knows alive in this zone within radius, nearest first: [(creature, distance)]."""
    if world.CURRENT is None:
        return []
    p = state.get("player") or {}
    found = []
    for c in world.CURRENT.threats(p.get("zone")):
        if c.get("moved_turn", -1) > c.get("last_turn", 0):
            continue  # seen to have moved off its last known cell: whereabouts unknown
        if ignored(c["name"]) or harmless(c["name"]):
            continue
        d = max(abs(c["x"] - p.get("x", 0)), abs(c["y"] - p.get("y", 0)))
        if d <= radius:
            found.append((c, d))
    return sorted(found, key=lambda t: t[1])


# Parts that mark townsfolk and pets rather than wildlife (read off Joppa's people, 2026-11-25: the
# watervine farmers have AISelfPreservation, AmbientSoundGenerator and CookingAndGathering_Harvestry;
# wildlife like crocs and glowfish carry Endurance_ skills, so a skill alone doesn't mean a person).
TOWNSFOLK_PARTS = {"GivesRep", "Honorifics", "Titles", "GenericInventoryRestocker", "AmbientSoundGenerator",
                   "JoppaZealot", "Pettable", "ConversationScript", "AISitting"}
TOWNSFOLK_SKILLS = ("CookingAndGathering", "Tinkering", "Physic", "Customs", "Survival", "Persuasion")


def mobile_threats(state, args):
    """What stops us eating or camping: a hostile in view that can move, or a rooted one within reach, or
    a mobile hostile known near (2026-11-25: rooted glowpads in sight kept Uubas from eating until he went
    Famished mid-siege)."""
    if world.CURRENT is None:
        return bool(visible_hostiles(state)[0])
    p = state.get("player") or {}
    me = (p.get("x", 0), p.get("y", 0))
    for o in visible_hostiles(state)[0]:
        rooted = (world.CURRENT.kind(o["name"]) or {}).get("mobile") is False
        if not rooted or max(abs(o["x"] - me[0]), abs(o["y"] - me[1])) <= 1:
            return True
    return any((world.CURRENT.kind(c["name"]) or {}).get("mobile") is not False
               for c, d in known_threats(state, args.get("safe_radius", 15)))


def skipped(o, memory):
    """Prey the fight routine chose to leave (estimate against it, or it needs a swim)."""
    return (o.get("id") or f"{o['name']}@{o['x']},{o['y']}") in (memory.get("fight") or {}).get("skip", [])


def evaluate_new_kinds(state, memory):
    """Judge each kind of neutral creature in view that game knowledge doesn't know yet (the user,
    2026-11-25: all new critters should be evaluated). A clear fit (no townsfolk parts, no allegiance in
    its name, no special parts, not Tough or worse, no higher level than us, and the live estimate says
    the fight is ours) is marked prey at once and said in the panel; townsfolk are marked not prey; anything
    else is handed to the LLM. Returns (lines to say, reason to stop or None)."""
    import threat
    p = state.get("player") or {}
    seen = memory.setdefault("evaluated", [])
    said = []
    for o in (state.get("map") or {}).get("objects", []):
        if not o.get("creature") or o.get("hostile") or (o["x"], o["y"]) == (p.get("x"), p.get("y")):
            continue
        name = o.get("name") or ""
        k = world.kind_name(name)
        if k in seen or world.CURRENT.kind(name) is not None:
            continue
        seen.append(k)
        if name[:1].isupper():
            continue  # a person, never prey
        parts = o.get("parts") or []
        town = [x for x in parts if x in TOWNSFOLK_PARTS or x.startswith(TOWNSFOLK_SKILLS)]
        if town:
            world.CURRENT.set_kind(name, prey=False, note=f"townsfolk parts: {', '.join(town[:3])}")
            said.append(f"SAY New kind: {k}, townsfolk by its parts ({', '.join(town[:2])}): not prey.")
            continue
        lvl, diff = o.get("lvl") or 1, re.sub(r"\{\{\w\||\}\}", "", o.get("diff") or "").strip()
        if " and friend to " in name or " and member of " in name:
            return said, f"{k} is neutral with an allegiance ({name}); killing it may cost reputation: judge it"
        est = threat.estimate(state, world.CURRENT, o)
        flags = est.get("flags") or []
        if est.get("ok") and not flags and diff not in threat.HARSH and lvl <= (p.get("level") or 1):
            world.CURRENT.set_kind(name, verdict="fight", prey=True, difficulty=diff or None,
                                   auto_prey=f"turn {state.get('turn')}: {est.get('why')}")
            said.append(f"SAY New critter: {k} ({diff}, {o.get('hp')} HP, level {lvl}), harmless and small: prey. {est.get('why')}")
            continue
        why = (f"flags {flags}" if flags else f"rated {diff}" if diff in threat.HARSH else
               f"level {lvl} above ours" if lvl > (p.get("level") or 1) else est.get("why") or "no estimate")
        return said, f"{k} (neutral, {diff}, {o.get('hp')} HP, level {lvl}): {why}; judge it: prey, avoid or leave"
    return said, None


UNDER_FIRE = __import__("re").compile(r"hits you \(x\d+\) from the |shooting at you|whizzes past from the ")
DIRECTION = __import__("re").compile(r"from the (northeast|northwest|southeast|southwest|north|south|east|west)")
DIR_VEC = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0), "northeast": (1, -1),
           "northwest": (-1, -1), "southeast": (1, 1), "southwest": (-1, 1)}

# "Hungry" isn't here: it has no penalty (Famished does).
NEEDS = ("Famished", "Starving", "Thirsty", "Parched", "Dehydrated")


def needs_status(state, accept=()):
    """Hunger/thirst words shown on the screen (the sidebar status line), or None. Words in accept
    (statuses the LLM already dealt with, args.accept_status) don't count."""
    p = state.get("player") or {}
    if p.get("food") is not None or p.get("water") is not None:  # the snapshot's own fields (mod v0.14+)
        text = f"{p.get('food', '')} {p.get('water', '')}"
    else:
        text = " ".join((state.get("screen") or {}).get("rows", []))
    found = [w for w in NEEDS if w in text and w not in accept]
    return ",".join(found) or None


def screen_summary(state, n=6):
    import re
    rows = (state.get("screen") or {}).get("rows", [])
    text = [" ".join(r.split()) for r in rows if re.search(r"[A-Za-z]{3}", r)]
    return " / ".join(text[:n])[:300]


TRACE = __import__("pathlib").Path(__file__).resolve().parents[2] / "live" / "trace.jsonl"


def act(state, memory, args):
    lines = decide(state, memory, args)
    said = memory.pop("new_things", None) or []
    if said:
        lines = said + lines
    if args.get("hand_off"):
        lines = ["NEXT " + l[5:] if l.startswith("STOP ") else l for l in lines]
    return lines


def decide(state, memory, args):
    player = state.get("player") or {}
    turn = state.get("turn", 0)
    memory.setdefault("start_turn", turn)

    # One line per call: where the player is. With ask_during_autoact on (brain/bridge.json) this is
    # called every step of the game's autoexplore, so the route can be checked afterwards.
    with TRACE.open("a", encoding="utf-8") as f:
        f.write(__import__("json").dumps({"seq": state.get("seq"), "turn": turn, "zone": player.get("zone"),
                                          "x": player.get("x"), "y": player.get("y"),
                                          "wait": state.get("wait"), "autoact": state.get("autoact")}) + "\n")

    # The game doesn't consult us between autoexplore steps (2026-11-26: no map call with autoact set in
    # 8928 traced calls), so the check below never ran. The mod's begin-turn callback (v0.26) breaks off
    # autoexplore, once per creature, when a kind listed in live/interrupt.txt comes into view within the
    # radius: we decide the list here on every call (prey kinds while hunting at full HP, else none).
    write_interrupts(state, args)
    # New liquids and feature kinds in view are listed for evaluation (features.py); a note, not a stop.
    new_things = []
    try:
        import features
        if world.CURRENT is not None:
            new_things = features.scan(state, world.CURRENT)
    except Exception:
        new_things = []
    memory["new_things"] = [f"SAY New {e['key']} ({e['example']} at {e['x']},{e['y']}): to evaluate." for e in new_things]

    # The game's own automatic action is running: let it continue.
    if state.get("wait") == "map" and state.get("autoact"):
        # ...unless prey worth hunting is in view: autoexplore stops only for hostiles, so neutral critters
        # it passes were never hunted (the user, 2026-11-25: interrupt explore to hunt them right there).
        # Healthy enough and nothing wrong: fall through, and the fight routine's first move breaks off
        # the autoexplore.
        p0 = state.get("player") or {}
        if not (args.get("hunt", True) and args.get("fight") and world.CURRENT is not None
                and p0.get("hp") and p0.get("maxhp") and p0["hp"] >= args.get("rest_fraction", 1.0) * p0["maxhp"]
                and not any(e in BAD_EFFECTS for e in p0.get("effects") or [])):
            return ["PASS"]
        prey = [o for o in fight.hostiles_in_view(state, world.CURRENT, True)[0] if not o.get("hostile") and not skipped(o, memory)
                and max(abs(o["x"] - p0.get("x", 0)), abs(o["y"] - p0.get("y", 0))) <= args.get("hunt_radius", 12)]
        if not prey:
            return ["PASS"]
        memory["broke_off_for"] = prey[0].get("id") or prey[0]["name"]  # the fight routine narrates the hunt

    # A missile shot in progress (CmdFire sent, its picker open): fire.
    if memory.get("fight", {}).get("firing"):
        lines, why = fight.continue_fire(state, memory)
        if why:
            return lines + [f"STOP {why}"]
        if lines:
            return lines

    # An ability use in progress (its screens are open): finish it before anything else.
    if memory.get("fight", {}).get("using") and world.CURRENT is not None:
        lines, why = fight.continue_ability(state, memory, world.CURRENT)
        if why:
            return lines + [f"STOP {why}"]
        if lines:
            return lines

    # Eat approved food when hungry (args.auto_eat): a short routine through the inventory screen,
    # one key per call. If it can't (no approved food, odd screens, still hungry after max_servings)
    # it raises the agent once and stays off for the rest of the stage.
    # Not with a hostile in view: eating takes turns, and a spider got free bites (2026-11-24). And only
    # somewhere safe (no hostile known alive within safe_radius), since some food has side effects
    # (the dreadroot tuber terrifies; the user: eat it "as long as we are in a safe zone").
    # Cook a free meal when Hungry (args.auto_cook): Make Camp + "Whip up a meal" uses up nothing
    # (2026-11-24), so it comes before eating from the inventory and already at Hungry. Same safety rule.
    if args.get("auto_cook") and not memory.get("cook_gave_up") and (
            "cook" in memory or (state.get("wait") == "map" and cook.hungry(state) is True and not mobile_threats(state, args)
                                 and not cook.refused_here(state, memory))):
        lines, why, done = cook.step(state, memory)
        if why:
            memory["cook_gave_up"] = True
            return lines + [f"STOP {why}"]
        if lines:
            return (["SAY Hungry, and nothing hostile is near: making camp to cook a free meal."] if memory.get("cook", {}).get("phase") == "abilities" else []) + lines
    if args.get("auto_eat") and not memory.get("eat_gave_up") and (
            "eat" in memory or (state.get("wait") == "map" and eat.hungry(state) is True and not mobile_threats(state, args))):
        lines, why, done = eat.step(state, memory, world.CURRENT, args.get("max_servings", 3))
        if why:
            memory["eat_gave_up"] = True
            return lines + [f"STOP {why}"]
        if lines:
            return (["SAY Hungry: eating from the pack."] if "eat" in memory and memory["eat"].get("phase") == "inventory" else []) + lines

    if player.get("level", 0) >= args.get("goal_level", 2):
        return [f"STOP goal: reached level {player.get('level')} at turn {turn}"]

    # A level-up hands over to reconsider points and plans (the user, 2026-11-24), once the encounter
    # around us is over (the user, earlier: levelling mid-fight is pointless).
    lvl = player.get("level") or 0
    if memory.get("level_seen") is None:
        memory["level_seen"] = lvl
    if lvl > memory["level_seen"]:
        memory["level_pending"] = lvl
    if memory.get("level_pending") and not visible_hostiles(state)[0] and state.get("wait") == "map":
        memory["level_seen"] = memory.pop("level_pending")
        return [f"STOP level up: now level {lvl} at turn {turn}; reconsider points and plans"]

    if state.get("wait") == "picker":
        # A cell picker is open (explore never opens one): Space would select a cell, so hand back.
        return ["STOP picker: a cell picker is open"]

    # A pickup in progress (collect sent CmdGet onto a pile: "Select an item"): its screens are
    # collect's, not an unknown popup.
    if memory.get("gear", {}).get("got") and state.get("wait") == "key":
        more, why, done = collect.step(state, memory, world.CURRENT, args, mkey="gear", only=collect.GEAR)
        if why:
            return more + [f"STOP {why}"]
        return more or ["PASS"]
    if memory.get("collecting") and memory.get("collect", {}).get("got") and state.get("wait") == "key":
        more, why, done = collect.step(state, memory, world.CURRENT, args)
        if why:
            return more + [f"STOP {why}"]
        if more:
            return more

    if state.get("wait") == "key":
        # Known information-only popups get dismissed; anything else goes to the LLM. If a dismissal
        # didn't work (same popup next call), stop instead of pressing forever.
        full = " ".join((state.get("screen") or {}).get("rows", []))
        summary = screen_summary(state, n=40)
        known = next((k for k in INFO_POPUPS if k in full), None)
        if "[press space]" in full:
            known = "[press space]"  # a popup whose only option is to continue
        if ZONE_DONE in full:
            memory["zone_done"] = True
        # Taking someone's belongings is theft (2026-11-26: collect walked onto a canteen in Joppa): decline.
        if "not owned by you" in full:
            return ["SAY That belongs to someone here: leaving it.", "KEY Escape"]
        # Warnings that need acting on are never pressed past (the user, 2026-11-24: autoexplore blew
        # past a Famished warning): dismiss it, and hand over with what it said.
        warn = re.search(r"(Famished|Starving|starving|thirsty|Thirsty|Dehydrated|dehydrated|Parched|health has dropped)", full)
        if known and warn and memory.get("dismissed") != summary:
            memory["dismissed"] = summary
            return ["KEY Space", f"STOP warning: {warn.group(1)} ({screen_summary(state)[:100]})"]
        if known and memory.get("dismissed") != summary:
            memory["dismissed"] = summary
            # Every popup we press past goes into the panel log, to be read when the LLM takes over (the
            # user: all skipped popups should at least be interpreted later).
            text = re.sub(r"\s+", " ", " / ".join(x.strip("│ ▌▐█▀▄").strip() for x in (state.get("screen") or {}).get("rows", [])
                                                 if "▌" in x and x.strip("▌▐ █│▀▄"))).strip()[:160]
            return ([f"SAY Dismissed a popup: {text}"] if text else []) + ["KEY Space"]
        # A container autoexplore opened ("Examining a table"): the game does this on its own, and taking
        # from one in Joppa drew no reaction (the user's experiment, 2026-11-24). Take all, note what was
        # in it, then Escape; the next call carries on exploring.
        m = re.search(r"\[ (?:Examining|Opening) (?:a |an |the )?(.+?) \]", full)
        if m and "Take all" in full and not args.get("leave_containers"):
            if memory.get("container_taken") != summary:
                memory["container_taken"] = summary
                items = [r.strip("│ ").split(")", 1)[-1].strip() for r in (state.get("screen") or {}).get("rows", [])
                         if re.search(r"\b[a-z]\)\s+\S", r) and "[-]" not in r and "Examining" not in r]
                items = [re.sub(r"\s{2,}.*$", "", i) for i in items if i][:6]
                return [f"SAY Opened a {m.group(1)}: taking {', '.join(items) or 'what is in it'}.", "KEY Tab"]
            return ["KEY Escape"]
        return [f"STOP popup: {screen_summary(state)}"]
    memory.pop("dismissed", None)

    # Stuck in a pool (asphalt, sap): autoexplore then says "nowhere else to explore from here", which
    # isn't the zone being done (2026-11-26: arriving on stratum 4 stuck in asphalt handed over as "zone
    # explored"). Struggle free with moves towards a cell with no pool; a hostile in view is the fight's.
    stuck = [e for e in player.get("effects") or [] if e.startswith("stuck")]
    if stuck and state.get("wait") == "map" and not visible_hostiles(state)[0]:
        memory.pop("zone_done", None)
        memory["stuck_moves"] = memory.get("stuck_moves", 0) + 1
        if memory["stuck_moves"] > 30:
            return [f"STOP stuck: still {stuck[0]} after 30 moves"]
        d = free_direction(state)
        said = [f"SAY Stuck ({stuck[0]}): struggling free."] if memory["stuck_moves"] == 1 else []
        return said + [f"CMD CmdMove{d}"]
    memory.pop("stuck_moves", None)

    # Effects that take control away (terror moves you on its own, daze and confusion spoil aim and
    # moves): never explore or fight under them. Wait them out where we are; a hostile in view while
    # under one goes to the LLM. (2026-11-24: still terrified from a dreadroot tuber, a "step away" from
    # the giant amoeba walked into it instead, 25 -> 4 HP, and a crit dazed us.)
    bad = [e for e in player.get("effects") or [] if e in BAD_EFFECTS]
    if bad and state.get("wait") == "map":
        # Harmless kinds (the dreadroot: its aura terrifies but it never hurts us) don't count as a
        # threat while we wait the effect out.
        # Nor do rooted kinds that aren't next to us (2026-11-24: terrified by dreadroots, a jilted lover 3
        # cells off stopped the wait-out although it can't reach us).
        px0, py0 = player.get("x", 0), player.get("y", 0)
        def can_reach(o):
            k = world.CURRENT.kind(o["name"]) if world.CURRENT is not None else None
            return (k or {}).get("mobile") is not False or max(abs(o["x"] - px0), abs(o["y"] - py0)) <= 1
        hostiles_now = [o for o in visible_hostiles(state)[0] if not harmless(o["name"]) and can_reach(o)]
        if hostiles_now:
            o = hostiles_now[0]
            return [f"STOP {', '.join(bad)} with a hostile in view: {o['name']} at ({o['x']},{o['y']})"]
        # Every waited turn is checked (the user, 2026-11-24: never take turns freely under an effect):
        # any HP drop while waiting goes to the LLM.
        hp_now = player.get("hp") or 0
        if memory.get("waiting_hp") is not None and hp_now < memory["waiting_hp"]:
            memory["waiting_hp"] = hp_now
            return [f"STOP {', '.join(bad)} and losing HP while waiting ({hp_now}/{player.get('maxhp')})"]
        memory["waiting_hp"] = hp_now
        memory.setdefault("waiting_since", turn)
        if turn - memory["waiting_since"] > args.get("max_wait_out", 25):
            return [f"STOP {', '.join(bad)} for {turn - memory['waiting_since']} turns (re-applied?); waited long enough"]
        say = [] if memory.get("waiting_out") == bad else [f"SAY I'm {', '.join(bad)}, which spoils my moves: waiting it out before doing anything else."]
        memory["waiting_out"] = bad
        return say + ["CMD CmdWait"]
    memory.pop("waiting_out", None)
    memory.pop("waiting_since", None)
    memory.pop("waiting_hp", None)

    # The game said the zone has nothing left to explore (seen in its popup, or as a message).
    last_message = (state.get("messages") or [""])[-1]
    # Prey still in view when the zone is explored gets hunted first (2026-11-25: zones ended with a glowpad
    # and a dragonfly in sight): the fight routine below takes it, and the zone ends after.
    prey_left = bool(args.get("hunt", True) and args.get("fight") and world.CURRENT is not None
                     and any(not o.get("hostile") and not skipped(o, memory) for o in fight.hostiles_in_view(state, world.CURRENT, True)[0]))
    # A rooted hostile in view goes to the fight routine too, which sieges it (heal out of reach between
    # bouts); the sweep below attacked blindly and took us 27 -> 10 (2026-11-25).
    if args.get("fight") and world.CURRENT is not None and any(
            o.get("hostile") and (world.CURRENT.kind(o["name"]) or {}).get("mobile") is False and not skipped(o, memory)
            for o in visible_hostiles(state)[0]):
        prey_left = True
    if (memory.get("zone_done") or (memory.get("sent") and ZONE_DONE in last_message)) and prey_left:
        memory["zone_done"] = True
    elif memory.get("zone_done") or (memory.get("sent") and ZONE_DONE in last_message):
        memory["zone_done"] = True
        # Rooted enemies we fight (dreadroots, jilted lovers, vines) still alive in this zone: go back for
        # them before calling it done (the user, 2026-11-24: we walked past two dreadroots to the stairs).
        # Walk towards the nearest; once in view the fight routine above takes it. One that can't be
        # reached in rooted_max_walk steps is left.
        if args.get("clear_rooted", True) and world.CURRENT is not None:
            pz = player.get("zone")
            tried = memory.setdefault("rooted_tried", [])
            left = [c for c in world.CURRENT.rooted_alive(pz)
                    if f"{c['x']},{c['y']}" not in tried
                    # not the ones the fight routine left as too costly (they're for tools/siege.py)
                    and not (c.get("id") and c["id"] in (memory.get("fight") or {}).get("skip", []))
                    and ((world.CURRENT.kind(c["name"]) or {}).get("verdict") == "fight")]
            if left:
                said = []
                px1, py1 = player.get("x", 0), player.get("y", 0)
                c = min(left, key=lambda c: max(abs(c["x"] - px1), abs(c["y"] - py1)))
                key = f"{c['x']},{c['y']}"
                rt = memory.setdefault("rooted_target", {})
                if rt.get("key") != key:
                    rt.clear(); rt.update({"key": key, "steps": 0})
                    said.append(f"SAY Before leaving: a {c['name']} still stands at ({c['x']},{c['y']}); going back for it.")
                rt["steps"] += 1
                # Its cell is in view and nothing hostile stands there: a stale record (or it died).
                here_now = [o for o in visible_hostiles(state)[0] if (o["x"], o["y"]) == (c["x"], c["y"])]
                vis = (state.get("map") or {}).get("vis") or []
                cell_seen = c["y"] < len(vis) and c["x"] < len(vis[c["y"]]) and vis[c["y"]][c["x"]] == "1"
                if (c["x"], c["y"]) == (px1, py1) or (cell_seen and not here_now):
                    c["dead_turn"] = turn
                    return said + ["PASS"]
                d1 = max(abs(c["x"] - px1), abs(c["y"] - py1))
                if d1 == 1:
                    return said + [f"CMD CmdAttack{fight.DIRS[(c['x'] - px1, c['y'] - py1)]}"]
                if rt["steps"] > args.get("rooted_max_walk", 80):
                    tried.append(key)
                    return said + [f"SAY Can't reach the {c['name']} at ({c['x']},{c['y']}); leaving it.", "PASS"]
                # Walk to a free cell next to it (its own cell is occupied: no path there). Neighbours are
                # tried in turn, nearest to us first; one the game reports no path to moves on to the next.
                nbrs = sorted([(c["x"] + dx, c["y"] + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)],
                              key=lambda q: max(abs(q[0] - px1), abs(q[1] - py1)))
                if state.get("goto_failed") and rt.get("aim") is not None:
                    rt["n"] = rt.get("n", 0) + 1
                i = rt.get("n", 0)
                if i >= len(nbrs):
                    tried.append(key)
                    return said + [f"SAY No way to stand next to the {c['name']} at ({c['x']},{c['y']}); leaving it.", "PASS"]
                rt["aim"] = nbrs[i]
                return said + [f"GOTO {nbrs[i][0]} {nbrs[i][1]}"]
        # Prey seen while exploring and not killed (the user, 2026-11-25: track everything we see except
        # what we kill, and go back for it): walk to where each was last seen. Once it's in view, prey_left
        # above hands it to the fight routine; a cell in view without it means it wandered off.
        if args.get("hunt", True) and args.get("fight") and world.CURRENT is not None:
            pz = player.get("zone")
            ptried = memory.setdefault("prey_tried", [])
            px1, py1 = player.get("x", 0), player.get("y", 0)
            recs = [c for c in world.CURRENT.data.get("creatures", {}).values()
                    if c.get("zone") == pz and not c.get("hostile") and not c.get("rooted")
                    and c.get("last_turn", 0) > c.get("dead_turn", -1) and c.get("moved_turn", -1) <= c.get("last_turn", 0)
                    and (world.CURRENT.kind(c["name"]) or {}).get("prey")
                    and " and friend to " not in c["name"] and " and member of " not in c["name"]
                    and (c.get("id") or f"{c['name']}@{c['x']},{c['y']}") not in ptried
                    and (c.get("id") or f"{c['name']}@{c['x']},{c['y']}") not in (memory.get("fight") or {}).get("skip", [])]
            if recs:
                c = min(recs, key=lambda c: max(abs(c["x"] - px1), abs(c["y"] - py1)))
                key = c.get("id") or f"{c['name']}@{c['x']},{c['y']}"
                pt = memory.setdefault("prey_target", {})
                said = []
                if pt.get("key") != key:
                    pt.clear(); pt.update({"key": key, "steps": 0})
                    said.append(f"SAY Before leaving: a {c['name']} was last seen at ({c['x']},{c['y']}); going back for it.")
                pt["steps"] += 1
                vis = (state.get("map") or {}).get("vis") or []
                cell_seen = c["y"] < len(vis) and c["x"] < len(vis[c["y"]]) and vis[c["y"]][c["x"]] == "1"
                if cell_seen or (c["x"], c["y"]) == (px1, py1) or pt["steps"] > args.get("prey_max_walk", 60) or state.get("goto_failed"):
                    c["moved_turn"] = turn  # not there (in view, it would be prey_left): whereabouts unknown
                    ptried.append(key)
                    return said + ["PASS"]
                return said + [f"GOTO {c['x']} {c['y']}"]
        if args.get("collect") and world.CURRENT is not None:
            memory["collecting"] = True  # handled below, after fights and the danger checks
        else:
            return [f"NEXT zone explored at turn {turn}"]

    # Being shot by something out of view ("A seed hits you (x2) from the west", "...because something
    # is shooting at you"): the fight routine only sees hostiles in view, and resting under fire fails,
    # so raise the agent at once.
    # When healthy and the shot came from a known direction, walk that way to bring the shooter into
    # view (vines are immobile and shoot from beyond our torchlight); the fight routine then shoots it.
    hp_, maxhp_ = player.get("hp"), player.get("maxhp")
    fire = [m for m in fight.new_messages(state, memory.setdefault("seen", {})) if UNDER_FIRE.search(m)]
    # "...shooting at you or the shale" alone (no hit, no near miss, no direction) is something out of view
    # hitting rock near us (2026-11-26: two stops 18 turns apart, nothing ever hit us). Keep exploring;
    # hand over on the third within 100 turns, or at once on a real hit or a seed whizzing past.
    vague = re.compile(r"shooting at you or the ")
    if fire and all(vague.search(m) and not re.search(r"hits you|whizzes past", m) for m in fire):
        times = [t for t in memory.get("vague_fire", []) if turn - t <= 100] + [turn]
        memory["vague_fire"] = times
        if len(times) < 3:
            fire = []
            if state.get("wait") == "map":
                return [f"SAY Something out of sight is shooting near me, not at me ({len(times)} in 100 turns); carrying on.", "CMD CmdAutoExplore"]
    if fire:
        # The first shot from out of view goes to the LLM at once (the user, 2026-11-24: pause sooner;
        # walking towards the shooter while healthy took a second crit). The direction, if given, says
        # which way to leave its line or to look.
        d = next((DIRECTION.search(m) for m in fire if DIRECTION.search(m)), None)
        return [f"STOP under fire from out of view" + (f" (from the {d.group(1)})" if d else "") + f": {fire[-1][:140]}"]
    seek = memory.get("seek")
    if seek and state.get("wait") == "map":
        if visible_hostiles(state)[0] or seek["steps"] >= 8:
            memory.pop("seek")
            if not visible_hostiles(state)[0]:
                return [f"STOP under fire: walked {seek['steps']} towards the {seek['from']} and saw no shooter"]
        elif hp_ and maxhp_ and hp_ < args.get("seek_hp_fraction", 0.6) * maxhp_:
            memory.pop("seek")
            return [f"STOP under fire and hurt: HP {hp_}/{maxhp_}, shooter to the {seek['from']} not seen"]
        else:
            seek["steps"] += 1
            return ([f"SAY Something out of sight is shooting at me from the {seek['from']}; going that way to find it."] if seek["steps"] == 1 else []) + [f"GOTO {max(0, min(79, seek['x']))} {max(0, min(24, seek['y']))}"]

    # Needs shown in the sidebar status line (Hungry, Famished, Thirsty...): raise the agent once per
    # new status; it eats or drinks and starts the stage again.
    accepted = list(args.get("accept_status", [])) + (list(eat.HUNGER) if args.get("auto_eat") and not memory.get("eat_gave_up") else [])
    status = needs_status(state, accept=accepted)
    if status and memory.get("status_raised") != status:
        memory["status_raised"] = status
        return [f"STOP status: {status}"]

    # Every new kind of neutral critter gets evaluated (the user, 2026-11-25): a clear fit becomes prey on
    # the spot, anything else goes to the LLM to judge. Not in towns (hunting off).
    if args.get("hunt", True) and world.CURRENT is not None:
        said, why = evaluate_new_kinds(state, memory)
        if why:
            return said + [f"STOP new kind: {why}"]
        pre_eval = said
    else:
        pre_eval = []

    hostiles, px, py = visible_hostiles(state)
    # Hunting (args.hunt): non-hostile creatures whose kind the LLM marked prey are fought too, but only
    # when healthy enough to rest afterwards (rest_fraction), never as a reason to take damage hurt.
    hp0, maxhp0 = player.get("hp"), player.get("maxhp")
    # Hunting is on unless a plan turns it off (the user, 2026-11-25: we stopped farming harmless neutral
    # critters for XP because plans left "hunt" out; in the marsh there are plenty). Set "hunt": false in towns.
    hunting = bool(args.get("hunt", True) and hp0 is not None and maxhp0 and hp0 >= args.get("rest_fraction", 1.0) * maxhp0)
    prey = []
    if hunting and world.CURRENT is not None:
        prey = [o for o in fight.hostiles_in_view(state, world.CURRENT, True)[0] if not o.get("hostile")]
    if args.get("fight") and world.CURRENT is not None and (hostiles or prey or memory.get("fight", {}).get("active")
                                                            or (args.get("hold") and args.get("stay"))):
        # The fight routine takes routine fights; anything unusual comes back as a reason to stop.
        lines, why = fight.engage(state, memory, dict(args, hunt=hunting), world.CURRENT)
        if why:
            return pre_eval + [f"STOP {why}"]
        if lines and any(not l.startswith(("SAY", "VOICE")) for l in lines):
            return pre_eval + lines
        pre = pre_eval + (lines or [])
    elif hostiles:
        o = hostiles[0]
        d = max(abs(o["x"] - px), abs(o["y"] - py))
        return pre_eval + [f"STOP hostile: {o['name']} at ({o['x']},{o['y']}), {d} away; {len(hostiles)} hostile in view"]
    else:
        pre = pre_eval

    hp, maxhp = player.get("hp"), player.get("maxhp")
    # Heal before going on whenever hurt and nothing hostile is next to us (the user, 2026-11-25: in the
    # middle of explore-and-fight, pause to heal unless enemies are right beside us; earlier: standing still
    # regenerates, and one that comes to us meets us at full health). The game's rest when it allows it;
    # otherwise (a hostile in view or known near) one turn of waiting at a time, so the fight routine above
    # still answers anything that comes closer.
    rest_at = args.get("rest_fraction", 1.0)
    if args.get("fight") and hp is not None and maxhp and hp < rest_at * maxhp:
        adjacent = [o for o in visible_hostiles(state)[0]
                    if max(abs(o["x"] - player.get("x", 0)), abs(o["y"] - player.get("y", 0))) <= 1]
        if not adjacent:
            near = known_threats(state, args.get("safe_radius", 15))
            if memory.get("rest_tried_turn") != turn and not near and not visible_hostiles(state)[0]:
                memory["rest_tried_turn"] = turn
                return pre + [f"SAY Hurt ({hp}/{maxhp}) with nothing hostile near: resting before moving on.", "CMD CmdWaitUntilHealed"]
            if memory.get("regen_said") != hp // 5:
                memory["regen_said"] = hp // 5
                why = f"{near[0][0]['name']} known {near[0][1]} away" if near else "a rest was refused here"
                pre = pre + [f"SAY Hurt ({hp}/{maxhp}), {why}: waiting in place to regenerate."]
            return pre + ["CMD CmdWait"]
    if hp is not None and maxhp and hp < args.get("min_hp_fraction", 0.5) * maxhp:
        return [f"STOP hurt: HP {hp}/{maxhp}"]

    if turn - memory["start_turn"] > args.get("max_turns", 1000):
        return [f"STOP budget: {turn - memory['start_turn']} turns used"]

    here = [player.get("zone"), player.get("x"), player.get("y"), turn]
    if memory.get("last") == here:
        memory["no_progress"] = memory.get("no_progress", 0) + 1
    else:
        memory["no_progress"] = 0
    memory["last"] = here
    if memory["no_progress"] >= 2 and not memory.get("collecting"):  # collecting has its own give-up rules
        last = (state.get("messages") or [""])[-1]
        return [f"STOP stuck: autoexplore made no progress; last message: {last[:200]}"]

    lines = list(pre)
    zone = player.get("zone")
    if memory.get("announced") != zone:
        memory["announced"] = zone
        lines.append(f"VOICE zone: Into {(player.get('zoneName') or 'a new zone').split(',')[0]}.")
        lines.append(f"SAY Exploring {player.get('zoneName') or 'this zone'}; I will stop for anything hostile or new, or if HP drops under {int(args.get('min_hp_fraction', 0.5) * 100)}%.")
    # Don't autoexplore near a known danger: a hostile kind marked avoid, not yet assessed, or one that
    # shoots, last seen alive in this zone within danger_radius. Autoexplore doesn't know about it and
    # walks into its range (the vine, 2026-11-24).
    for c, d in known_threats(state, args.get("danger_radius", 12)):
        k = world.CURRENT.kind(c["name"]) if world.CURRENT is not None else None
        if k is None or k.get("verdict") != "fight" or k.get("ranged"):
            return [f"STOP near known danger: {c['name']} ({(k or {}).get('verdict', 'unassessed')}) last seen at ({c['x']},{c['y']}), {d} away"]
    # Reload in downtime, not at the start of the next fight (the user, 2026-11-24): an empty missile
    # weapon with ammo in the pack and nothing hostile in view gets reloaded before moving on.
    equipped = state.get("equipped") or []
    ammo = any(re.match(r"lead slug", i) for i in state.get("inventory") or [])
    if (args.get("missile", True) and ammo and any(fight.EMPTY.search(e) for e in equipped)
            and not visible_hostiles(state)[0] and memory.get("reload_tried_turn") != turn):
        memory["reload_tried_turn"] = turn
        return lines + ["SAY The musket is empty and nothing is around: reloading now so it is ready for the next fight.", "CMD CmdReload"]
    # The zone is explored: sweep up the remembered items autoget left (args.collect), then report.
    if memory.get("collecting"):
        more, why, done = collect.step(state, memory, world.CURRENT, args)
        if why:
            return lines + more + [f"STOP {why}"]
        if done:
            taken = memory.get("collect", {}).get("taken", [])
            return lines + [f"NEXT zone explored at turn {turn}; picked up {len(taken)} item(s)"
                            + (": " + ", ".join(taken[:8]) if taken else "")]
        lines += more
        return lines if any(not l.startswith(("SAY", "VOICE")) for l in lines) else lines + ["PASS"]
    # Gear in sight (weapons, armour): take it now, not at the end-of-zone sweep (the user, 2026-11-24:
    # an iron long sword lay 130 turns in our path before we picked it up). After a pickup the gear is
    # compared by the game's rules: a better weapon or any armour goes to the LLM to equip.
    # Safe enough to loot (the user, 2026-11-24: we stood on a pile with an iron long sword and didn't take
    # it because rooted dreadroots were in view): nothing adjacent, and nothing that can move within 3.
    def safe_to_loot():
        pp = state.get("player") or {}
        for o in visible_hostiles(state)[0]:
            d = max(abs(o["x"] - pp.get("x", 0)), abs(o["y"] - pp.get("y", 0)))
            k = world.CURRENT.kind(o["name"]) if world.CURRENT is not None else None
            if d <= 1 or (d <= 3 and (k or {}).get("mobile") is not False):
                return False
        return True
    if args.get("collect") and args.get("gear_early", True) and world.CURRENT is not None and safe_to_loot():
        more, why, done = collect.step(state, memory, world.CURRENT, args, mkey="gear", only=collect.GEAR,
                                       max_dist=args.get("gear_dist", 20))
        if why:
            return lines + more + [f"STOP {why}"]
        picked = [l[len("SAY Picked up "):].rstrip(".") for l in more if l.startswith("SAY Picked up ")]
        if picked:
            import threat
            verdict = threat.gear_verdict(state, picked[0])
            if verdict:
                return lines + more + [f"STOP {verdict}"]
        if not done:
            lines += more
            return lines if any(not l.startswith(("SAY", "VOICE")) for l in lines) else lines + ["PASS"]
    memory["sent"] = True
    return lines + ["CMD CmdAutoExplore"]
