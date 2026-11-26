"""One-off stage: make camp and cook a meal (the cook routine), then end the stage.

args: none. Used in safe places (a town) when hungry; the camp meal costs nothing.
"""
from scripts import cook


def act(state, memory, args):
    if state.get("wait") == "map" and state.get("autoact"):
        return ["PASS"]
    lines, why, done = cook.step(state, memory)
    if why:
        return lines + [f"STOP {why}"]
    if done:
        return lines + ["NEXT cooked"]
    return lines
