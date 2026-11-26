"""PostToolUse hook: while the Qud bot's narration is on (live/voice_on), remind Claude to narrate when
the voice has been silent for SILENCE seconds (the user, 2026-11-24: "minutes of silence"). At most one
reminder per SILENCE seconds."""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SILENCE = 25

def main():
    try:
        cwd = (json.loads(sys.stdin.read() or "{}").get("cwd") or "").replace("\\", "/")
    except Exception:
        cwd = ""
    # Only for work in qud-bot (the hook is also wired at workspace level as a fallback).
    if cwd and "qud-bot" not in cwd:
        return
    live = ROOT / "live"
    if not (live / "voice_on").exists():
        return
    now = time.time()
    vlog, nag = live / "voice.log", live / "_narrate_nag"
    last_voice = vlog.stat().st_mtime if vlog.exists() else 0
    last_nag = nag.stat().st_mtime if nag.exists() else 0
    if now - last_voice < SILENCE or now - last_nag < SILENCE:
        return
    nag.write_text(str(now))
    quiet = int(now - last_voice)
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext":
        f"Narration is on and the voice has been silent for {quiet} s. Per .claude/skills/narrate/SKILL.md: "
        "say what you are doing now and why with tools/say.py (one line), and a think.py line for any "
        "decision, then carry on."}}))

if __name__ == "__main__":
    main()
