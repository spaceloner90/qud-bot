"""Speak a line through the narrator (live/voice.log), for the LLM's own remarks. Separate from the panel
log (tools/think.py); obeys brain/voice.json's "llm" event switch.

  python tools/say.py "Found the vermin. Now for a corpse."

Importable: say(text). The action tools (send.py, walk.py, next_zone.py) take --say "<line>" and
--think "<line>" to narrate in the same call as the action (2026-11-26).
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def say(text):
    """Append a voice line; returns what was printed."""
    text = (text or "").strip()
    if not text:
        return ""
    try:
        cfg = json.loads((ROOT / "brain" / "voice.json").read_text(encoding="utf-8"))
        if not cfg.get("events", {}).get("llm", True):
            return "llm voice lines are off in brain/voice.json"
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    try:
        turn = json.loads((ROOT / "live" / "state.json").read_text(encoding="utf-8-sig")).get("turn", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        turn = 0
    with open(ROOT / "live" / "voice.log", "a", encoding="utf-8") as f:
        f.write(f"{turn}\t{text}\n")
    return f"voice: {text}"


def take_narration(argv):
    """Pull --say/--think "<line>" out of an argument list and play them at once (before the action, so
    the narration is in step with it). Returns the remaining arguments."""
    import think as _think
    rest, args = [], list(argv)
    while args:
        a = args.pop(0)
        if a in ("--say", "--think") and args:
            text = args.pop(0)
            print(say(text) if a == "--say" else _think.think(text))
        else:
            rest.append(a)
    return rest


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    text = " ".join(sys.argv[1:]).strip()
    if not text:
        print(__doc__)
        return
    print(say(text))


if __name__ == "__main__":
    main()
