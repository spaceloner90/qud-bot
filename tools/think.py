"""Write the LLM's own reasoning into the bot panel's log (live/narration.log), so the log reads as a
train of thought: decisions and why, alongside the scripts' lines (the user, 2026-11-24).

  python tools/think.py "Going back up: HP 16 and the vine shoots from the dark."

Importable: think(text). Or pass --think "<line>" to send.py, walk.py or next_zone.py.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def think(text):
    """Append a panel line; returns what was printed."""
    text = (text or "").strip()
    if not text:
        return ""
    try:
        turn = json.loads((ROOT / "live" / "state.json").read_text(encoding="utf-8-sig")).get("turn", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        turn = 0
    with open(ROOT / "live" / "narration.log", "a", encoding="utf-8") as f:
        f.write(f"{turn}\t* {text}\n")
    return f"{turn}\t* {text}"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    text = " ".join(sys.argv[1:]).strip()
    if not text:
        print(__doc__)
        return
    print(think(text))


if __name__ == "__main__":
    main()
