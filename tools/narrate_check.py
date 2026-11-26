"""Agent-agnostic narration silence check: while live/voice_on exists, remind the agent when the voice
channel (live/voice.log) has been silent for SILENCE seconds (the user, 2026-11-24: "minutes of silence").
At most one reminder per SILENCE seconds (tracked via live/_narrate_nag).

Imported by the live-play CLI tools (send.py, walk.py, menu.py, wait.py, next_zone.py, watch_handover.py)
and by .claude/hooks/narrate_check.py; can also be run standalone:
  python tools/narrate_check.py
"""
import sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SILENCE = 25


def check_silence(silence=SILENCE):
    """Return a reminder string if voice_on is active and voice.log has been quiet >= silence seconds,
    else None. Updates live/_narrate_nag so it fires at most once per silence window."""
    live = ROOT / "live"
    if not (live / "voice_on").exists():
        return None
    now = time.time()
    vlog, nag = live / "voice.log", live / "_narrate_nag"
    last_voice = vlog.stat().st_mtime if vlog.exists() else 0
    last_nag = nag.stat().st_mtime if nag.exists() else 0
    if now - last_voice < silence or now - last_nag < silence:
        return None
    try:
        nag.write_text(str(now), encoding="utf-8")
    except OSError:
        pass
    quiet = int(now - last_voice)
    return (
        f"Narration is on and the voice has been silent for {quiet} s. Per research/narrate.md: "
        "say what you are doing now and why with tools/say.py (one line), and a think.py line for any "
        "decision, then carry on."
    )


def remind(silence=SILENCE):
    """Print a one-line reminder to stdout if the voice has been silent too long."""
    msg = check_silence(silence)
    if msg:
        print(f"[narrate] {msg}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    remind()
