"""Vet the fight routine against every known kind of enemy, offline (the user, 2026-11-25: whenever we add
new logic like the wait-to-come, vet it against the suite of known enemies).

  python tools/vet_fight.py            all kinds in game_knowledge.json
  python tools/vet_fight.py vine dog   only kinds containing these words

For each kind it builds a target from the latest logged snapshot of one (stats, attacks, parts), or a plain
stand-in, puts it next to us and 5 cells off, with us at full HP and at 40%, runs fight.engage on the
current snapshot with the current plan's explore args, and checks the answer against the kind's tactic:
  hold  (mobile melee)   off at range: wait for it or open with an ability; never walk to it at once
  close (ranged)          off at range: close in or open with an ability; never stand and wait
  siege (rooted melee)    hurt and next to it: step away; hurt and off: wait to heal; healthy: go in
  avoid verdict           never an attack or a walk towards it
Prints one row per kind and scenario, with a FAIL mark where the answer breaks the rule. Nothing is sent.
"""
import copy, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "brain"))
import world as W  # noqa: E402
from scripts import fight  # noqa: E402
import tempfile  # noqa: E402
fight.HANDOVERS = Path(tempfile.gettempdir()) / "qudbot_vet_handovers.jsonl"  # not the real hand-over log


def samples():
    """The latest full snapshot object per kind, from the call log."""
    out = {}
    try:
        lines = (ROOT / "live" / "log.jsonl").read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return out
    for line in lines[-40000:]:
        if '"creature": true' not in line and '"creature":true' not in line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        for o in ((e.get("state") or {}).get("map") or {}).get("objects", []):
            if o.get("creature") and o.get("attacks") is not None and o.get("hp"):
                out[W.kind_name(o["name"])] = o
    return out


def standin(kind):
    return {"name": kind, "creature": True, "hostile": True, "hp": 20, "maxhp": 20, "av": 2, "dv": 3, "lvl": 1,
            "qn": 100, "ms": 100, "str": 0, "agi": 0, "diff": "{{w|Average}}", "parts": [],
            "attacks": [{"name": "bite", "dmg": "1d4", "pen": 0, "cap": 1000, "hit": 0}]}


def verdict(answer, tac, kind_entry, dist, low):
    lines, why = answer
    acts = [l for l in (lines or []) if l.split(" ", 1)[0] in ("KEY", "CMD", "GOTO")]
    first = acts[0] if acts else (f"STOP {why}" if why else "nothing")
    bad = None
    if (kind_entry or {}).get("verdict") == "avoid":
        if first.startswith(("CMD CmdAttack", "GOTO")):
            bad = "attacks or walks towards an avoid kind"
    elif tac == "hold" and dist >= 2 and not low and first.startswith("GOTO"):
        bad = "walks to a melee enemy instead of letting it come"
    elif tac == "close" and dist >= 2 and first == "CMD CmdWait":
        bad = "stands and waits in a shooter's line"
    elif tac == "siege" and low and dist == 1 and not (kind_entry or {}).get("harmless")             and not first.startswith("GOTO") and not first.startswith("STOP"):
        bad = "stays next to a rooted enemy while hurt"
    elif tac == "siege" and not low and dist >= 2 and first == "CMD CmdWait":
        bad = "waits for a rooted enemy that can't come"
    return first, bad


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    want = [w.lower() for w in sys.argv[1:]]
    s0 = json.loads((ROOT / "live" / "state.json").read_text(encoding="utf-8-sig"))
    wd = W.load(s0, apply=False)
    wd.save = lambda: None
    W.CURRENT = wd
    plan = json.loads((ROOT / "brain" / "plan.json").read_text(encoding="utf-8"))
    stage = next((st for st in plan.get("stages") or [plan] if st.get("script") == "explore"), None)
    args = dict((stage or {}).get("args") or {"fight": True, "hold": True, "hunt": True, "accept_kinds": ["dreadroot"]})
    smp = samples()
    p0 = s0["player"]
    rows, fails = [], 0
    for kind, entry in sorted((wd.data.get("kinds") or {}).items()):
        if want and not any(w in kind for w in want):
            continue
        if kind[:1].isupper() or entry.get("prey") is False and entry.get("verdict") != "avoid" and not entry.get("obs"):
            pass
        base = copy.deepcopy(smp.get(kind) or standin(kind))
        base.update({"hostile": True, "name": kind, "id": "vet-" + kind})
        tac = fight.tactic(entry)
        for dist, low, cool in [(d, l, c) for c in (False, True) for d in (1, 5) for l in (False, True)]:
            if True:
                st = copy.deepcopy(s0)
                st["wait"] = "map"
                st["player"]["hp"] = max(1, int(p0["maxhp"] * (0.4 if low else 1.0)))
                o = dict(base, x=min(79, p0["x"] + dist), y=p0["y"])
                st["map"]["objects"] = [o]
                st["messages"] = []
                if cool:  # abilities just used: what the tactic does without the ray or a charge
                    wd.data["cooldowns"] = {"Freezing Ray": st.get("turn", 0) + 20, "Charge": st.get("turn", 0) + 20}
                else:
                    wd.data["cooldowns"] = {}
                try:
                    ans = fight.engage(st, {}, args, wd)
                except Exception as ex:
                    ans = (None, f"EXCEPTION {ex}")
                first, bad = verdict(ans, tac, entry, dist, low)
                fails += bool(bad)
                rows.append(f"{'FAIL' if bad else '    '} {kind[:28]:28} {tac:5} d{dist} {'40%' if low else 'full'}{' cd' if cool else '   '}: {first[:66]}" + (f"   <- {bad}" if bad else ""))
    # Mixed groups (2026-11-25: a vine and a dreadroot both 2 cells off; we faced the dreadroot and waited
    # in the vine's line): every shooter paired with every other kind at the same distance must never get
    # a wait, and the first move must be about the shooter.
    kinds = wd.data.get("kinds") or {}
    shooters = [k for k, e in kinds.items() if e.get("ranged") and e.get("verdict") != "avoid"]
    others = [k for k, e in kinds.items() if not e.get("ranged") and e.get("verdict") == "fight"]
    for sk in shooters:
        for ok in others:
            if want and not any(w in sk or w in ok for w in want):
                continue
            for low in (False, True):
                st = copy.deepcopy(s0)
                st["wait"] = "map"
                st["player"]["hp"] = max(1, int(p0["maxhp"] * (0.6 if low else 1.0)))
                a1 = dict(copy.deepcopy(smp.get(sk) or standin(sk)), name=sk, id="vet-s", hostile=True, x=p0["x"] + 2, y=p0["y"])
                a2 = dict(copy.deepcopy(smp.get(ok) or standin(ok)), name=ok, id="vet-o", hostile=True, x=p0["x"] - 2, y=p0["y"])
                st["map"]["objects"] = [a2, a1]
                st["messages"] = []
                wd.data["cooldowns"] = {"Freezing Ray": st.get("turn", 0) + 20, "Charge": st.get("turn", 0) + 20}
                try:
                    lines, why = fight.engage(st, {}, args, wd)
                except Exception as ex:
                    lines, why = None, f"EXCEPTION {ex}"
                acts = [l for l in (lines or []) if l.split(" ", 1)[0] in ("KEY", "CMD", "GOTO")]
                first = acts[0] if acts else f"STOP {why}"
                bad = None
                if first == "CMD CmdWait":
                    bad = "waits with a shooter in view"
                elif first.startswith("GOTO") and int(first.split()[1]) < p0["x"]:
                    bad = "walks to the other one first, away from the shooter"
                fails += bool(bad)
                rows.append(f"{'FAIL' if bad else '    '} pair {sk[:18]} + {ok[:18]:18} {'60%' if low else 'full'}: {first[:60]}" + (f"   <- {bad}" if bad else ""))
    print("\n".join(rows))
    print(f"{fails} failing of {len(rows)} (sample objects from the log for {sum(1 for k in smp)} kinds)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
