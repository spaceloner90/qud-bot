"""Eat approved food when hungry, through the inventory screen (classic UI), one key per call.

Food the bot may eat on its own is listed in the run's world file (tools/world.py food add "<name>"):
what's edible and what we're willing to consume is a per-run decision by the LLM.

step(state, memory, world, max_servings) returns (lines, raise_reason, done):
  lines   the next key(s) to play
  raise   a reason to hand over to the LLM (no approved food, a screen that doesn't look as expected)
  done    True when not hungry any more, or after max_servings
Each screen is read before acting; nothing is pressed blind.
"""
import re

ITEM = re.compile(r"^\W*>?\s*([a-zA-Z])\)\s+(.+?)\s{2,}")
EAT = re.compile(r"([a-zA-Z])\) eat\b")
# Hungry has no penalty; Famished costs 10 quickness (wiki, 2026-11-24). So eat at Famished.
HUNGER = ("Famished", "Starving")
RESERVE_SERVINGS = 3   # at Hungry, eat only while more than this many servings are in the pack


def screen_text(state):
    return (state.get("screen") or {}).get("rows", [])


def hungry(state):
    """True/False from the sidebar's status line; None when the sidebar isn't on screen (some frames
    lack it, e.g. right after a reload), which must not be read as "not hungry"."""
    food = (state.get("player") or {}).get("food")
    if food is not None:  # the snapshot's own field (mod v0.14+)
        if any(w in food for w in HUNGER):
            return True
        # Hungry: eat too while the pack holds more than a reserve (the user, 2026-11-24: no reason not
        # to eat toward Sated while food is readily available). Servings are counted from "[N servings]".
        if "Hungry" in food:
            # Only once "really" hungry (cook.REALLY_HUNGRY_AFTER turns into Hungry), like cooking.
            from scripts import cook
            if not cook.really_hungry(state):
                return False
            servings = 0
            for e in state.get("inventory") or []:
                m = re.search(r"\[(\d+) servings?\]", e)
                servings += int(m.group(1)) if m else 0
            return servings > RESERVE_SERVINGS
        return False
    rows = screen_text(state)
    if not any("HP:" in r for r in rows):
        return None
    text = " ".join(rows)
    return any(w in text for w in HUNGER)


def step(state, memory, world, max_servings=3):
    eat = memory.setdefault("eat", {"phase": "start", "servings": 0})
    phase, wait = eat["phase"], state.get("wait")
    food = (world.data.get("food") if world is not None else None) or []

    if phase == "start":
        h = hungry(state)
        if h is None:
            return ["PASS"] if wait == "map" else [], None, False  # can't tell yet: look again next call
        if not h:
            memory.pop("eat", None)
            return [], None, True
        if eat["servings"] >= max_servings:
            memory.pop("eat", None)
            return [], f"still hungry after {max_servings} servings", True
        if wait != "map":
            return [], "eat: expected the map before opening the inventory", True
        eat["phase"] = "inventory"
        return ["CMD CmdInventory"], None, False

    if phase == "inventory":
        if wait != "key" or not any("Inventory" in r for r in screen_text(state)):
            return ["KEY Escape"], "eat: the inventory didn't open", True
        for row in screen_text(state):
            m = ITEM.match(row.strip("│ "))
            if m and any(f in m.group(2) for f in food):
                eat.update({"phase": "select", "item": m.group(2), "letter": m.group(1)})
                return [f"KEY {m.group(1)}"], None, False
        memory.pop("eat", None)
        return ["KEY Escape"], f"hungry, but no approved food in the inventory (approved: {food})", True

    if phase == "select":
        if not any(">" in r and eat["item"].split(" [")[0] in r for r in screen_text(state)):
            memory.pop("eat", None)
            return ["KEY Escape"], f"eat: {eat['item']} wasn't selected", True
        eat["phase"] = "menu"
        return ["KEY Return"], None, False

    if phase == "menu":
        letter = next((m.group(1) for r in screen_text(state) for m in [EAT.search(r)] if m), None)
        if letter is None:
            memory.pop("eat", None)
            return ["KEY Escape", "KEY Escape"], f"eat: no 'eat' option for {eat['item']}", True
        eat["phase"] = "ate"
        return [f"KEY {letter}"], None, False

    if phase == "ate":
        text = " ".join(screen_text(state))
        if wait == "key" and "You eat" in text:
            eat["servings"] += 1
            eat["phase"] = "start"
            return ["KEY Space"], None, False
        memory.pop("eat", None)
        return ["KEY Escape"], "eat: no 'You eat' confirmation", True

    memory.pop("eat", None)
    return [], f"eat: unknown phase {phase}", True
