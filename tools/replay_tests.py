"""Replay frozen game states against the current brain scripts, offline (the user, 2026-11-26: add test
cases incrementally in retrospectives, not live).

  python tools/replay_tests.py            run every case in tests/fixtures/cases/ plus tests/unit_checks.py
  python tools/replay_tests.py vague      only cases whose name contains this

A case is a JSON file:
  {"name", "why",                       what it guards against and which run found it
   "script": "explore",                 the stage script whose act(state, memory, args) is called
   "args": {...}, "memory": {...},      the stage args and stage memory to call it with
   "state": {...},                      the frozen snapshot (from live/log.jsonl)
   "states": [{...}, ...],              or several, played in order with the same memory; expect is
                                        checked against the last answer
   "fresh_world": true,                 optional: an empty world file of its own (shared game knowledge
                                        only) instead of the live one, so the live file's records can't
                                        make a case pass
   "known_bug": "...",                  optional: a bug not fixed yet; reported as KNOWN (not failing) while
                                        it fails, and as FIXED once it passes (then drop the field)
   "expect": {"answer_re": "...",       a regex (multiline: ^ is any line's start) the answer lines must match
              "answer_not_re": "...",   ...must not match
              "memory_has": ["key"]}}   keys the stage memory must hold afterwards
Nothing under live/ is written: the scripts' live paths point at a temp dir, and the world file isn't saved.

Add a case: find the turn in live/log.jsonl (each "call" line holds the full state), copy its state into a
new file here with the stage args and memory it needs, and say what the right answer is.
Exit code 1 if anything fails.
"""
import copy, json, re, sys, tempfile, traceback, importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CASES = ROOT / "tests" / "fixtures" / "cases"
sys.path.insert(0, str(ROOT / "brain"))
sys.path.insert(0, str(ROOT / "tests"))


def isolate():
    """Point every live/ path the scripts write at a temp dir."""
    tmp = Path(tempfile.mkdtemp(prefix="qudbot_replay_"))
    from scripts import explore, fight, cook
    explore.TRACE = tmp / "trace.jsonl"
    explore.write_interrupts = lambda state, args: None
    explore.clear_interrupts = lambda: None
    fight.HANDOVERS = tmp / "fight_handovers.jsonl"
    cook.HUNGER_FILE = tmp / "hunger.json"
    return tmp


def run_case(path):
    case = json.loads(path.read_text(encoding="utf-8"))
    import world
    # "states": a sequence of snapshots played in order with one stage memory (for bugs that only show
    # across calls, like a target flip-flop); "expect" checks the last call's answer.
    states = case.get("states") or [case["state"]]
    script = importlib.import_module("scripts." + case["script"])
    memory = copy.deepcopy(case.get("memory") or {})
    fresh = None
    for raw in states:
        state = copy.deepcopy(raw)
        if case.get("fresh_world"):
            # A world file of its own, empty but for the shared game knowledge, kept across the case's
            # states (2026-11-27: a case reading the live world file passed because the live file already
            # held what the fix was meant to record).
            if fresh is None:
                rid = world.run_id(state)
                data = world.empty(rid)
                for key in world.SHARED:
                    data[key] = copy.deepcopy(world.load_game().get(key, {}))
                fresh = world.World(rid, data, Path(tempfile.mkdtemp(prefix="qudbot_world_")) / "world.json")
            fresh.update(state)  # what step.py does every call: the world learns from each snapshot
            world.CURRENT = fresh
        else:
            world.CURRENT = world.load(state, apply=False)
        answer = list(script.act(state, memory, case.get("args") or {}))
    text = "\n".join(answer)
    exp = case.get("expect") or {}
    problems = []
    if exp.get("answer_re") and not re.search(exp["answer_re"], text, re.M):
        problems.append(f"answer doesn't match /{exp['answer_re']}/")
    if exp.get("answer_not_re") and re.search(exp["answer_not_re"], text, re.M):
        problems.append(f"answer matches /{exp['answer_not_re']}/")
    for k in exp.get("memory_has") or []:
        if k not in memory:
            problems.append(f"memory lacks {k!r}")
    return problems, text


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    only = sys.argv[1:]
    isolate()
    failed = 0
    for path in sorted(CASES.glob("*.json")):
        if only and not any(o in path.stem for o in only):
            continue
        try:
            problems, text = run_case(path)
        except Exception:
            problems, text = ["crashed: " + traceback.format_exc().strip().splitlines()[-1]], ""
        known = json.loads(path.read_text(encoding="utf-8")).get("known_bug")
        if known:
            print(("FIXED " if not problems else "KNOWN ") + path.stem + (": drop known_bug" if not problems else f": {known[:110]}"))
            continue
        print(("PASS " if not problems else "FAIL ") + path.stem + ("" if not problems else ": " + "; ".join(problems)))
        if problems:
            failed += 1
            print("      answer: " + text.replace("\n", " | ")[:300])
    try:
        import unit_checks
        for name, fn in unit_checks.CHECKS:
            if only and not any(o in name for o in only):
                continue
            known = getattr(fn, "known_bug", None)
            try:
                fn()
                print(("FIXED " if known else "PASS ") + name + (": drop known_bug" if known else ""))
            except AssertionError as e:
                if known:
                    print(f"KNOWN {name}: {known[:110]}")
                    continue
                failed += 1
                print(f"FAIL {name}: {e}")
            except Exception:
                failed += 1
                print(f"FAIL {name}: crashed: " + traceback.format_exc().strip().splitlines()[-1])
    except ImportError:
        pass
    print(f"{failed} failing")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
