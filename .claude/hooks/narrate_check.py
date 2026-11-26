"""Claude Code PostToolUse hook shim: delegates to the agent-agnostic tools/narrate_check.py."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import narrate_check  # noqa: E402


def main():
    try:
        cwd = (json.loads(sys.stdin.read() or "{}").get("cwd") or "").replace("\\", "/")
    except Exception:
        cwd = ""
    # Only for work in qud-bot (the hook is also wired at workspace level as a fallback).
    if cwd and "qud-bot" not in cwd:
        return
    msg = narrate_check.check_silence()
    if msg:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))


if __name__ == "__main__":
    main()
