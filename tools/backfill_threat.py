"""Rebuild the threat observations (game knowledge: each kind's "obs", and "weapons") from live/log.jsonl,
for every run in it. Run with the bot stopped (the brain rewrites brain/game_knowledge.json each call).

  python tools/backfill_threat.py            print what it found
  python tools/backfill_threat.py --write    replace obs/weapons in brain/game_knowledge.json
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "brain"))
import threat, world as W


class Fake:
    def __init__(self):
        self.data = {"kinds": {}, "weapons": {}}

    def set_kind(self, name, **fields):
        return self.data["kinds"].setdefault(W.kind_name(name), {})


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    fake, prev = Fake(), None
    for line in (ROOT / "live" / "log.jsonl").open(encoding="utf-8"):
        if '"state"' not in line:
            continue
        try:
            s = json.loads(line).get("state")
        except json.JSONDecodeError:
            continue
        if not isinstance(s, dict) or not s.get("turn"):
            continue
        msgs = list(s.get("messages") or [])
        new = msgs
        if prev is not None:
            new = msgs
            for n in range(min(len(prev), len(msgs)), 0, -1):
                if prev[-n:] == msgs[:n]:
                    new = msgs[n:]
                    break
        prev = msgs
        if not new:
            continue
        parts = [x.strip() for m in new for x in m.split("\n") if x.strip()]
        p = s.get("player") or {}
        adj = [o for o in (s.get("map") or {}).get("objects", []) if o.get("hostile")
               and max(abs(o["x"] - p.get("x", 0)), abs(o["y"] - p.get("y", 0))) == 1 and o.get("av") is not None]
        threat.observe(fake, parts, s, adj[0] if len(adj) == 1 else None)
    for k, v in sorted(fake.data["kinds"].items()):
        o = v.get("obs") or {}
        if o.get("attacks"):
            print(f"{k:30} attacks {o['attacks']:4} hits {o['hits']:4} dmg {o['dmg']:4} mult/hit {o['mult']/max(1,o['hits']):.2f} "
                  f"ourAV {o['av']/max(1,o['av_n']):.1f} per turn {o['attacks']/max(1,o['turns']):.2f}")
    for k, o in fake.data["weapons"].items():
        print(f"WEAPON {k:28} hits {o['hits']} misses {o['misses']} mult/hit {o['mult']/max(1,o['hits']):.2f} dmg/hit {o['dmg']/max(1,o['hits']):.2f} targetAV {o['av']/max(1,o['av_n']):.1f}")
    if "--write" in sys.argv:
        g = json.loads(W.GAME.read_text(encoding="utf-8"))
        for k, v in fake.data["kinds"].items():
            if v.get("obs"):
                g.setdefault("kinds", {}).setdefault(k, {"verdict": "ask"})["obs"] = v["obs"]
        g["weapons"] = fake.data["weapons"]
        W.GAME.write_text(json.dumps(g, indent=1, ensure_ascii=False), encoding="utf-8")
        print("written")


if __name__ == "__main__":
    main()
