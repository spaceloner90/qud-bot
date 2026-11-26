"""Turn the narrator's voice on or off (the flag file live/voice_on; F9 in the game does the same).

  python tools/voice.py on | off | toggle | status

The narrator itself runs separately: powershell -NoProfile -File tools/narrator.ps1
"""
import sys
from pathlib import Path

FLAG = Path(__file__).resolve().parent.parent / "live" / "voice_on"


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "toggle":
        cmd = "off" if FLAG.exists() else "on"
    if cmd == "on":
        FLAG.parent.mkdir(exist_ok=True)
        FLAG.write_text("on\n", encoding="utf-8")
    elif cmd == "off":
        FLAG.unlink(missing_ok=True)
    print("voice " + ("on" if FLAG.exists() else "off"))


if __name__ == "__main__":
    main()
