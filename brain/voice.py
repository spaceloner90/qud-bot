"""The narrator's voice channel, separate from the panel log (the user, 2026-11-24: what's spoken needn't
be what's written; only interesting notes, never repeated, never over itself).

Scripts answer "VOICE <event>: <text>"; step.py passes them here with the state. Lines whose event is off
in brain/voice.json, or that were spoken within repeat_turns, are dropped; the rest go to live/voice.log.
Milestones (level-ups, quest steps) are spotted in the game's messages here, not in the scripts.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "brain" / "voice.json"
OUT = ROOT / "live" / "voice.log"
STATE = ROOT / "live" / "voice_state.json"
MILESTONE = re.compile(r"(gained a level! You are now level \d+|finished the step, .+?, of the quest .+?!|completed the quest .+?!)")


def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def emit(state, voice_lines):
    cfg = load(CONFIG, {"events": {}, "repeat_turns": 300})
    vs = load(STATE, {"spoken": {}, "msgs": []})
    turn = state.get("turn") or 0
    lines = []
    for v in voice_lines:
        event, _, text = v.partition(":")
        if not text:
            event, text = "llm", v
        lines.append((event.strip(), text.strip()))
    # Milestones from the game's own messages (new ones since the last call).
    msgs = list(state.get("messages") or [])
    prev = vs.get("msgs") or []
    new = msgs
    for n in range(min(len(prev), len(msgs)), 0, -1):
        if prev[-n:] == msgs[:n]:
            new = msgs[n:]
            break
    for m in new:
        hit = MILESTONE.search(m)
        if hit:
            lines.append(("milestone", hit.group(1).replace("You have ", "").replace("!", ".")))
    vs["msgs"] = msgs[-40:]
    out = []
    for event, text in lines:
        if not cfg.get("events", {}).get(event, False):
            continue
        last = vs["spoken"].get(text)
        repeat = (cfg.get("repeat_turns_by_event") or {}).get(event, cfg.get("repeat_turns", 300))
        if last is not None and turn - last < repeat:
            continue
        vs["spoken"][text] = turn
        out.append(text)
    if len(vs["spoken"]) > 500:
        vs["spoken"] = dict(sorted(vs["spoken"].items(), key=lambda kv: kv[1])[-300:])
    STATE.write_text(json.dumps(vs), encoding="utf-8")
    if out:
        with open(OUT, "a", encoding="utf-8") as f:
            for t in out:
                f.write(f"{turn}\t{t}\n")
    return out
