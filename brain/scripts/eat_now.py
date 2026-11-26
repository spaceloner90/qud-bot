"""One-off stage: eat approved food until not hungry (the auto-eat routine), then end the stage.

args: {"max_servings": 3}
"""
import world
from scripts import eat


def act(state, memory, args):
    if state.get("wait") == "map" and state.get("autoact"):
        return ["PASS"]
    lines, why, done = eat.step(state, memory, world.CURRENT, args.get("max_servings", 3))
    if why:
        return lines + [f"STOP {why}"]
    if done:
        return lines + ["NEXT not hungry"]
    return lines
