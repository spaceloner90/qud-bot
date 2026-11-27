"""Relight: equip a fresh torch from the pack when the one in hand has gone out (2026-11-27: a swim put the
torch out; lessons.md: light for exploring, so a viewer can follow). One key per call, like eat.py, and
never a second key on an unchanged screen (the snapshot can lag a key, game_facts.md).

  needed(state)                  an unlit torch is equipped and an unburnt stack is in the pack
  step(state, memory) -> (lines, why, done)

Flow (found by hand the same day, tools/menu.py item "torch x" equip): CmdInventory, the stack's letter,
Return for its menu, "e) equip", then Space for the "Your torch was unequipped" popup.
"""
import re

ITEM = re.compile(r"\b([a-z])\)\s+(torch x\d+[^│]*)")
EQUIP = re.compile(r"\b([a-zA-Z])\) equip \(auto\)")


def needed(state):
    eq = state.get("equipped") or []
    held = [e for e in eq if re.match(r"^(lit )?torch\b", e)]
    unlit = bool(held) and not any(e.startswith("lit torch") for e in held)
    spare = any(re.match(r"^torch x\d+", i) for i in state.get("inventory") or [])
    return unlit and spare


def step(state, memory):
    m = memory.setdefault("light", {"phase": "start", "keys": 0})
    m["keys"] += 1
    wait = state.get("wait")
    rows = (state.get("screen") or {}).get("rows", [])
    screen = "\n".join(rows)
    if m["keys"] > 14:
        memory.pop("light", None)
        return ["KEY Escape"] if wait != "map" else [], "relight: the inventory didn't go as expected", True
    if m["phase"] != "start" and wait == "key":
        from scripts.collect import menu_signature  # the menu without the map round it
        sig = menu_signature(state)
        if sig == m.get("seen"):
            return ["WAIT"], None, False
        m["seen"] = sig
    ph = m["phase"]
    if ph == "start":
        if wait != "map":
            return ["WAIT"], None, False
        m["phase"] = "inventory"
        return ["SAY The torch has gone out: lighting a fresh one.", "CMD CmdInventory"], None, False
    if ph == "inventory":
        if wait != "key":
            return ["WAIT"], None, False
        hit = next((mm.group(1) for r in rows for mm in [ITEM.search(r)] if mm), None)
        if not hit:
            memory.pop("light", None)
            return ["KEY Escape"], None, True  # no spare stack after all: carry on unlit
        m["phase"] = "select"
        return [f"KEY {hit}"], None, False
    if ph == "select":
        letter = next((mm.group(1) for r in rows for mm in [EQUIP.search(r)] if mm), None)
        if letter:  # the menu came straight up
            m["phase"] = "popup"
            return [f"KEY {letter}"], None, False
        m["phase"] = "menu"
        return ["KEY Return"], None, False
    if ph == "menu":
        letter = next((mm.group(1) for r in rows for mm in [EQUIP.search(r)] if mm), None)
        if not letter:
            return ["WAIT"], None, False
        m["phase"] = "popup"
        return [f"KEY {letter}"], None, False
    if ph == "popup":
        if wait == "map":
            memory.pop("light", None)
            return [], None, True
        return ["KEY Space" if "press space" in screen.lower() or "unequipped" in screen else "KEY Escape"], None, False
    memory.pop("light", None)
    return [], None, True
