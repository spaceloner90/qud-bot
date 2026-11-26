"""Use an activated ability (Freezing Ray, Charge, Teleport...) through the Abilities screen, one key
per call, reading each screen before acting.

How the game asks (learned by hand, 2026-11-24): CMD CmdAbilities lists the abilities ("f) Charge
[attack]", cursor ">"); Space on one opens a cell picker (wait kind "picker") whose top line names the
ability: "Freezing Ray  Space-select | unlock (F8)". Targeted abilities (Freezing Ray, Charge) come
locked onto a target ("unlock"); Teleport comes unlocked ("lock") with the cursor on the player.
Space in the picker uses the ability. Escape cancels at any point without spending a turn.

Because we can't see which creature a lock is on, the caller only uses targeted abilities when exactly
one creature is in view and it is the hostile target. Cooldowns aren't readable yet, so the caller
tracks them by turn.

step(state, memory, name) returns (lines, raise_reason, done):
  done with raise_reason None    the ability was used (memory["ability_result"] holds new messages)
  done with a raise_reason        it didn't work out; screens have been backed out of
  done, no reason, and memory["ability_cooldown"] = {"name", "turns"}: still cooling down (read from
                                  the list or the game's "You must wait N rounds" popup); backed out
"""
import re


def rows(state):
    return (state.get("screen") or {}).get("rows", [])


def step(state, memory, name):
    a = memory.setdefault("ability", {"phase": "open", "name": name, "moves": 0})
    phase, wait = a["phase"], state.get("wait")

    if phase == "open":
        if wait != "map":
            memory.pop("ability", None)
            return [], f"ability {name}: expected the map to open Abilities", True
        a["phase"] = "find"
        a["turn"] = state.get("turn")
        return ["CMD CmdAbilities"], None, False

    if phase == "find":
        lines = rows(state)
        if not any("Manage Abilities" in r for r in lines):
            memory.pop("ability", None)
            return ["KEY Escape"], f"ability {name}: the Abilities screen didn't open", True
        listed = [(i, r) for i, r in enumerate(lines) if ") " in r[:45] and name in r[:45]]
        cursor = next((i for i, r in enumerate(lines) if r[:45].lstrip("│ ").startswith(">")), None)
        if not listed:
            memory.pop("ability", None)
            return ["KEY Escape"], f"ability {name}: not in the ability list", True
        target_row = listed[0][0]
        # Still cooling down: the list shows "Freezing Ray [15 turn cooldown]". Back out without a raise
        # and tell the caller how long (memory["ability_cooldown"]), so it fights on without it.
        cool = re.search(r"\[(\d+) turn cooldown\]", listed[0][1][:60])
        if cool:
            memory.pop("ability", None)
            memory["ability_cooldown"] = {"name": name, "turns": int(cool.group(1))}
            return ["KEY Escape"], None, True
        if cursor == target_row:
            a["phase"] = "picker"
            return ["KEY Space"], None, False
        a["moves"] += 1
        if a["moves"] > 15 or cursor is None:
            memory.pop("ability", None)
            return ["KEY Escape"], f"ability {name}: couldn't move the cursor to it", True
        return ["KEY DownArrow" if cursor < target_row else "KEY UpArrow"], None, False

    if phase == "picker":
        wait_msg = re.search(r"You must wait (\d+) rounds? before using", " ".join(rows(state)))
        if wait_msg:  # the same, said in a popup after Space
            memory.pop("ability", None)
            memory["ability_cooldown"] = {"name": name, "turns": int(wait_msg.group(1))}
            return ["KEY Space", "KEY Escape"], None, True
        top = " ".join(rows(state)[:2])
        if wait != "picker" and "Manage Abilities" in " ".join(rows(state)):
            # Space on it left us in the list (2026-11-24: Charge while swimming): not usable here.
            memory.pop("ability", None)
            memory["ability_failed"] = {"name": name, "why": "not usable here"}
            return ["KEY Escape"], None, True
        # Already fired without a picker: an AIM target (mod v0.25) answers the picker itself, so we're back
        # on the map with the ability's message (2026-11-25: "You emit a freezing ray" was then read as
        # "no picker" and the fight handed over). That's success.
        recent = " ".join((state.get("messages") or [])[-4:])
        if wait == "map" and re.search(r"You emit a freezing ray|You charge|You teleport", recent):
            memory.pop("ability", None)
            return [], None, True
        if wait != "picker" or name not in top:
            memory.pop("ability", None)
            return ["KEY Escape", "KEY Escape"], f"ability {name}: no picker for it (wait {wait}): {top[:80]}", True
        a["phase"] = "used"
        a["msgs_before"] = list(state.get("messages") or [])
        return ["KEY Space"], None, False

    if phase == "used":
        from scripts.fight import new_messages
        new = new_messages(state, {"msgs": a.get("msgs_before", [])})
        memory["ability_result"] = {"name": name, "turn": state.get("turn"), "messages": new}
        memory.pop("ability", None)
        if wait == "picker":  # still in the picker: it wasn't accepted
            return ["KEY Escape"], f"ability {name}: the picker didn't accept the target", True
        if "Manage Abilities" in " ".join(rows(state)):
            # Back in the list without a ray (2026-11-24: a wall between us and the target): no clear
            # line. Back out; the caller holds fire at this target for a while.
            memory["ability_failed"] = {"name": name, "why": "no clear line"}
            return ["KEY Escape"], None, True
        return [], None, True

    memory.pop("ability", None)
    return [], f"ability {name}: unknown phase {phase}", True
