"""Cook a free meal when hungry: Make Camp, then the campfire's "Whip up a meal" (found 2026-11-24: it
gives Sated and uses up nothing). One key per call, each screen checked before acting.

Steps the game shows:
  map            -> CMD CmdAbilities
  abilities list -> move the cursor to "Make Camp", Space
  "Make Camp [Select a direction]" -> a direction key towards a free cell
  map ("You make camp.") -> CMD CmdGetFrom
  "Interact [Select a direction]" -> the fire's direction
  "Select an item" list -> the campfire's letter (or Space if it's already selected)
  campfire menu  -> c (cook)
  cook menu      -> m (Whip up a meal)
  popups         -> Space until the map; extra menus left open -> Escape

step(state, memory) returns (lines, raise_reason, done). Raises (with Escapes to back out) on any
screen that doesn't look as expected, so the LLM can see it.
"""
import re

DIRS = [((0, -1), "Keypad8"), ((1, 0), "Keypad6"), ((0, 1), "Keypad2"), ((-1, 0), "Keypad4"),
        ((1, -1), "Keypad9"), ((1, 1), "Keypad3"), ((-1, 1), "Keypad1"), ((-1, -1), "Keypad7")]
FLOOR = set(".,'`\"·")  # · : dirt path and tent floor (2026-11-25: "no free cell" beside Tam's tent)
# Cook at Famished only: Hungry has no penalty, and a meal only lifts the meter a little above Hungry
# (Hungry again ~600 turns after one, with two world-map steps). Camping is free but not risk-free.
HUNGRY_WORDS = ("Hungry", "Famished", "Starving")  # cook at Hungry when safe (the user, 2026-11-24): the camp meal is free


def rows(state):
    return (state.get("screen") or {}).get("rows", [])


def text(state):
    return "\n".join(rows(state))


# Cooking at the first sign of Hungry camped too often (the user, 2026-11-25: track when we go from Sated
# to Hungry and wait another X turns before we're "really" hungry). Hunger drops 1 a turn: Hungry below 0,
# Famished below -1200 (research/design.md), so 900 turns after turning Hungry leaves 300 before Famished.
REALLY_HUNGRY_AFTER = 450  # measured 2026-11-25: Hungry (206540) -> Famished (207280) took ~740 turns, not 1200
HUNGER_FILE = __import__("pathlib").Path(__file__).resolve().parents[2] / "live" / "hunger.json"


def hungry_for(state):
    """Turns since the food status turned Hungry (0 when not hungry), kept in live/hunger.json per game so
    plan changes don't lose it; None when the snapshot has no food status."""
    import json
    food = (state.get("player") or {}).get("food")
    if food is None:
        return None
    game, turn = (state.get("game") or {}).get("id"), state.get("turn") or 0
    try:
        rec = json.loads(HUNGER_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        rec = {}
    if not any(w in food for w in HUNGRY_WORDS):
        if rec.get("since") is not None or rec.get("game") != game or not rec.get("seen_sated"):
            # seen_sated: we saw this game not hungry, so the next Hungry starts its clock exactly
            HUNGER_FILE.write_text(json.dumps({"game": game, "since": None, "seen_sated": True}), encoding="utf-8")
        return 0
    if rec.get("game") != game or rec.get("since") is None or rec["since"] > turn:
        # First seen Hungry with no record for this game (a loaded save was already Hungry, 2026-11-25:
        # Uubas went Famished before the delay ran out): assume it has been Hungry half the delay already.
        known = rec.get("game") == game and rec.get("since") is None and rec.get("seen_sated")
        rec = {"game": game, "since": turn if known else turn - REALLY_HUNGRY_AFTER // 2}
        HUNGER_FILE.write_text(json.dumps(rec), encoding="utf-8")
    return turn - rec["since"]


def really_hungry(state):
    """Famished or worse, or Hungry for REALLY_HUNGRY_AFTER turns; None without a food status."""
    food = (state.get("player") or {}).get("food")
    if food is None:
        return None
    if "Famished" in food or "Starving" in food:
        return True
    return (hungry_for(state) or 0) >= REALLY_HUNGRY_AFTER


def hungry(state):
    return really_hungry(state)


def refused_here(state, memory, turns=150, dist=10):
    """A camp was refused for hostiles nearby recently and close to here: don't try again yet."""
    r = memory.get("cook_refused")
    if not r:
        return False
    p = state.get("player") or {}
    if (state.get("turn") or 0) - (r.get("turn") or 0) > turns:
        return False
    return max(abs((p.get("x") or 0) - (r.get("x") or 0)), abs((p.get("y") or 0) - (r.get("y") or 0))) < dist


def camp_spot(state, failed=()):
    """The nearest dry cell, within 15, that has an open floor cell next to it for the fire (not water,
    not where a camp already failed)."""
    p = state.get("player") or {}
    m = state.get("map") or {}
    grid = m.get("rows") or []
    taken = {(o["x"], o["y"]) for o in m.get("objects", [])}
    bad = {tuple(x) for x in failed}
    px, py = p.get("x", 0), p.get("y", 0)
    best = None
    for y in range(max(0, py - 15), min(len(grid), py + 16)):
        for x in range(max(0, px - 15), min(len(grid[y]), px + 16)):
            if grid[y][x] not in FLOOR or (x, y) in taken or (x, y) in bad:
                continue
            free = sum(1 for (dx, dy), _ in DIRS
                       if 0 <= y + dy < len(grid) and 0 <= x + dx < len(grid[y + dy]) and grid[y + dy][x + dx] in FLOOR
                       and (x + dx, y + dy) not in taken)
            if free >= 2:
                d = max(abs(x - px), abs(y - py))
                if best is None or d < best[0]:
                    best = (d, (x, y))
    return best[1] if best else None


def free_cell(state):
    """A direction to an adjacent floor cell with nothing on it, from the snapshot's map."""
    p = state.get("player") or {}
    m = state.get("map") or {}
    grid = m.get("rows") or []
    taken = {(o["x"], o["y"]) for o in m.get("objects", [])}
    for (dx, dy), key in DIRS:
        x, y = p.get("x", 0) + dx, p.get("y", 0) + dy
        if 0 <= y < len(grid) and 0 <= x < len(grid[y]) and grid[y][x] in FLOOR and (x, y) not in taken:
            return key
    return None


def back_out(why):
    return ["KEY Escape", "KEY Escape", "KEY Escape"], why, True


def step(state, memory):
    c = memory.setdefault("cook", {"phase": "start", "presses": 0})
    phase, wait, scr = c["phase"], state.get("wait"), text(state)
    c["presses"] += 1
    if c["presses"] > 40:
        memory.pop("cook", None)
        return back_out("cooking took too many steps")

    if phase == "start":
        if wait != "map":
            memory.pop("cook", None)
            return [], "cook: not on the map", True
        key = free_cell(state)
        p = state.get("player") or {}
        here = (p.get("x"), p.get("y"))
        if key is None or here in [tuple(x) for x in c.get("failed_at", [])]:
            # No ground for a fire here: walk to some (the user, 2026-11-25: we had the surroundings under
            # control and only had to walk a bit to a viable camp instead of using up the jerky).
            spot = camp_spot(state, c.get("failed_at", []))
            if spot is None:
                memory.pop("cook", None)
                return [], "cook: no open ground for a campfire within reach", True
            c.update(phase="walking", spot=list(spot), steps=0)
            return [f"SAY No ground for a fire here: walking to ({spot[0]},{spot[1]}) to make camp.", f"GOTO {spot[0]} {spot[1]}"], None, False
        c.update(phase="abilities", fire_key=key, at=list(here))
        return ["CMD CmdAbilities"], None, False

    if phase == "walking":
        p = state.get("player") or {}
        c["steps"] = c.get("steps", 0) + 1
        # The spot is chosen by straight-line distance, so the walk can wind round walls (2026-11-26: a spot
        # 2 cells off took 30+ steps): allow a long walk; GOTO's own "no path" still ends it at once.
        if wait != "map" or c["steps"] > 80 or state.get("goto_failed"):
            memory.pop("cook", None)
            return back_out("cook: couldn't walk to open ground for a camp")
        if [p.get("x"), p.get("y")] == c["spot"]:
            c.update(phase="start")
            return ["PASS"], None, False
        return [f"GOTO {c['spot'][0]} {c['spot'][1]}"], None, False

    if phase == "abilities":
        lines = rows(state)
        if "Manage Abilities" not in scr:
            memory.pop("cook", None)
            return back_out("cook: the abilities screen didn't open")
        target = next((i for i, r in enumerate(lines) if "Make Camp" in r[:45]), None)
        cursor = next((i for i, r in enumerate(lines) if r[:45].lstrip("│ ").startswith(">")), None)
        if target is None or cursor is None:
            memory.pop("cook", None)
            return back_out("cook: Make Camp isn't in the abilities list")
        if "cooldown" in lines[target][:45]:
            memory.pop("cook", None)
            return back_out("cook: Make Camp is cooling down")
        if cursor != target:
            return ["KEY DownArrow" if cursor < target else "KEY UpArrow"], None, False
        c["phase"] = "camp_dir"
        return ["KEY Space"], None, False

    if phase == "camp_dir":
        if "cook with hostiles nearby" in scr or "make camp in combat" in scr and "direction" not in scr:
            # The game knows of a hostile we can't see (2026-11-24, at the stairs on stratum 3).
            memory.pop("cook", None)
            # Not a hand-over (2026-11-26: it retried on the same cell at once and handed over again):
            # note where and when, and let the caller try elsewhere or later (see refused_here).
            p = state.get("player") or {}
            memory["cook_refused"] = {"turn": state.get("turn"), "x": p.get("x"), "y": p.get("y")}
            return ["KEY Space", "KEY Escape", "SAY Can't cook here: something hostile is near, out of sight. I'll try again elsewhere."], None, True
        if "Make Camp" not in scr or "direction" not in scr:
            memory.pop("cook", None)
            return back_out("cook: no direction prompt for Make Camp")
        c["phase"] = "camped"
        return [f"KEY {c['fire_key']}"], None, False

    if phase == "camped":
        if wait != "map" or not any("You make camp" in m for m in (state.get("messages") or [])[-3:]):
            # Not here: try open ground elsewhere, twice at most, before handing over.
            failed = c.setdefault("failed_at", [])
            failed.append(c.get("at"))
            if len(failed) <= 2 and wait == "map":
                c.update(phase="start", presses=0)
                return ["SAY The camp didn't take here; looking for other ground."], None, False
            memory.pop("cook", None)
            return back_out("cook: making camp didn't work: " + " | ".join((state.get("messages") or [])[-2:])[:120])
        c["phase"] = "interact"
        return ["CMD CmdGetFrom"], None, False

    if phase == "interact":
        if "Interact" not in scr or "direction" not in scr:
            memory.pop("cook", None)
            return back_out("cook: no direction prompt to interact")
        c["phase"] = "select"
        return [f"KEY {c['fire_key']}"], None, False

    if phase == "select":
        lines = rows(state)
        if "Select an item" not in scr:
            memory.pop("cook", None)
            return back_out("cook: no item list at the fire")
        row = next((r for r in lines if "campfire" in r), None)
        m = re.search(r"([a-z])\)\s+campfire", row or "")
        if not m:
            memory.pop("cook", None)
            return back_out("cook: no campfire in the item list")
        c["phase"] = "fire_menu"
        return ["KEY Space"] if ">" in row.split(m.group(1) + ")")[0] else [f"KEY {m.group(1)}", "KEY Space"], None, False

    if phase == "fire_menu":
        if "c) cook" not in scr:
            memory.pop("cook", None)
            return back_out("cook: the campfire menu has no cook option")
        c["phase"] = "cook_menu"
        return ["KEY c"], None, False

    if phase == "cook_menu":
        if "Whip up a meal" not in scr:
            memory.pop("cook", None)
            return back_out("cook: no 'Whip up a meal' option")
        c["phase"] = "eating"
        return ["KEY m"], None, False

    if phase == "eating":
        # Popups ("You gather some fixings...", "You eat the meal."), then the menus reopen.
        if "[press space]" in scr.lower() or "press [space]" in scr.lower():
            return ["KEY Space"], None, False
        if wait != "map":
            return ["KEY Escape"], None, False
        if hungry(state):
            memory.pop("cook", None)
            return [], "cook: still famished after the meal", True
        # Put the fire out: a lit campfire burns whatever ends up on it (wiki), us included if a path
        # later crosses it.
        c["phase"] = "out_interact"
        return ["SAY Ate a cooked meal (" + str((state.get("player") or {}).get("food")) + "); putting the fire out so I cannot walk into it later.",
                "CMD CmdGetFrom"], None, False

    if phase == "out_interact":
        if "Interact" not in scr or "direction" not in scr:
            memory.pop("cook", None)
            return back_out("cook: no direction prompt to put the fire out")
        c["phase"] = "out_select"
        return [f"KEY {c['fire_key']}"], None, False

    if phase == "out_select":
        row = next((r for r in rows(state) if "campfire" in r), None)
        m = re.search(r"([a-z])\)\s+campfire", row or "")
        if "Select an item" not in scr or not m:
            memory.pop("cook", None)
            return back_out("cook: no campfire to put out")
        c["phase"] = "out_menu"
        return ["KEY Space"] if ">" in row.split(m.group(1) + ")")[0] else [f"KEY {m.group(1)}", "KEY Space"], None, False

    if phase == "out_menu":
        if "x) extinguish" not in scr:
            memory.pop("cook", None)
            return back_out("cook: no extinguish option on the campfire")
        c["phase"] = "out_done"
        return ["KEY x"], None, False

    if phase == "out_done":
        if "[press space]" in scr.lower() or "press [space]" in scr.lower():
            return ["KEY Space"], None, False
        if wait != "map":
            return ["KEY Escape"], None, False
        memory.pop("cook", None)
        return ["SAY The fire is out; back to it."], None, True

    memory.pop("cook", None)
    return back_out(f"cook: unknown phase {phase}")
