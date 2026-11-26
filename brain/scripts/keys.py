"""Play a fixed list of keys, one per call, then stop. For exploring screens by hand.

args: {"keys": ["Escape", "n", ...]}
"""


def act(state, memory, args):
    keys = args.get("keys", [])
    i = memory.get("i", 0)
    if i >= len(keys):
        return ["STOP keys done"]
    memory["i"] = i + 1
    return ["KEY " + keys[i]] + (["STOP keys done"] if i + 1 >= len(keys) else [])
