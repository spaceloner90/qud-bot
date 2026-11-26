"""Speak a line through the narrator (live/voice.log), for the LLM's own remarks. Separate from the panel
log (tools/think.py); obeys brain/voice.json's "llm" event switch.

  python tools/say.py "Found the vermin. Now for a corpse."
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    text = " ".join(sys.argv[1:]).strip()
    if not text:
        print(__doc__)
        return
    try:
        cfg = json.loads((ROOT / "brain" / "voice.json").read_text(encoding="utf-8"))
        if not cfg.get("events", {}).get("llm", True):
            print("llm voice lines are off in brain/voice.json")
            return
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    try:
        turn = json.loads((ROOT / "live" / "state.json").read_text(encoding="utf-8-sig")).get("turn", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        turn = 0
    with open(ROOT / "live" / "voice.log", "a", encoding="utf-8") as f:
        f.write(f"{turn}\t{text}\n")
    print(f"voice: {text}")


if __name__ == "__main__":
    main()
