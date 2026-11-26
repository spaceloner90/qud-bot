"""Walk to the zone edge in a direction, cross into the next zone, and start the explore-and-hunt plan
there (keeping the current plan's explore args when it has them). Made 2026-11-25 for hunting the marsh
zones around Joppa zone by zone.

  python tools/next_zone.py W        (N S E W)

Exit 2 when the walk to the edge or the crossing doesn't go as expected (the plan is then left in the
remote stage, so nothing acts on its own).
"""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import walk, send  # noqa: E402

PLAN = ROOT / "brain" / "plan.json"
DEFAULT_ARGS = {"hand_off": True, "fight": True, "missile": True, "collect": True, "auto_eat": True, "auto_cook": True,
                "hunt": True, "goal_level": 5, "max_turns": 1500, "raise_hp_fraction": 0.5, "hold": True,
                "max_hostiles": 2, "accept_kinds": ["dreadroot"]}
REMOTE = {"script": "remote", "args": {"poll_seconds": 10, "map_poll_seconds": 1}}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    d = (sys.argv[1:] or ["W"])[0].upper()
    s = walk.state()
    p = s["player"]
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    stage0 = (plan.get("stages") or [plan])[0]
    args = stage0.get("args") if stage0.get("script") == "explore" else None
    # Town settings (fight and hunt off, a short budget) don't follow us out of town (2026-11-26: Joppa's
    # args carried into the outskirts, so nothing was hunted there).
    if args:
        args = {**args, "fight": True, "hunt": True, "max_turns": DEFAULT_ARGS["max_turns"]}
    PLAN.write_text(json.dumps({"label": f"{p['name']}: to the next zone {d} (from {s['turn']})",
                                "objective": plan.get("objective"), "goal": "next zone", "stages": [REMOTE]}, indent=1),
                    encoding="utf-8")
    time.sleep(1.5)  # let the remote stage start before sending
    edge = {"W": (0, p["y"]), "E": (79, p["y"]), "N": (p["x"], 0), "S": (p["x"], 24)}[d]
    reason, s = walk.walk(*edge)
    print("walk:", reason, s["player"]["x"], s["player"]["y"])
    if reason != "arrived":
        return 2
    z0 = s["player"]["zone"]
    for _ in range(2):
        send.play([f"CMD CmdMove{d}"])
        s = walk.state()
        if s["player"]["zone"] != z0:
            break
    p = s["player"]
    print("now", p["zone"], p["x"], p["y"], p["zoneName"], "HP", p["hp"], p["maxhp"])
    if p["zone"] == z0 or s.get("wait") != "map":
        return 2
    PLAN.write_text(json.dumps({"label": f"{p['name']}: hunting {p['zone']} (from {s['turn']})",
                                "objective": plan.get("objective"),
                                "goal": "Explore and hunt this zone: hostiles and prey; evaluate new critters",
                                "stages": [{"script": "explore", "args": args or DEFAULT_ARGS}, REMOTE]}, indent=1),
                    encoding="utf-8")
    print("explore plan set")
    return 0


if __name__ == "__main__":
    import atexit, narrate_check
    atexit.register(narrate_check.remind)
    sys.exit(main())
