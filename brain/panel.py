"""The in-game bot panel, written after every brain call. The mod draws it as a window over the game
(F10 toggles): a status header from live/panel.txt, and under it a scrolling log from
live/narration.log (newest at the bottom; the mod keeps it scrolled there unless you scroll up).

The log keeps everything, one line per entry ("<turn>\t<text>"):
  - the bot's narration (SAY lines)
  - "!! " hand-offs and stops (NEXT / STOP reasons)
  - the LLM's own notes (tools/think.py): decisions and why
Its own state (last action, last raise, recent game messages) is kept in live/panel_state.json so it
survives plan changes.
"""
import json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT = ROOT / "live" / "panel.txt"
STATE = ROOT / "live" / "panel_state.json"
NARRATION = ROOT / "live" / "narration.log"

ACTIONS = [
    (re.compile(r"^CMD CmdAutoExplore"), "exploring (autoexplore)"),
    (re.compile(r"^CMD CmdAttack(\w+)"), "attacking {0}"),
    (re.compile(r"^CMD CmdWaitUntilHealed"), "resting until healed"),
    (re.compile(r"^CMD CmdWait"), "waiting"),
    (re.compile(r"^CMD CmdMove([NSEW]+)$"), "moving {0}"),
    (re.compile(r"^CMD CmdMoveU"), "going up"),
    (re.compile(r"^CMD CmdMoveD"), "going down"),
    (re.compile(r"^CMD CmdAbilities"), "using an ability"),
    (re.compile(r"^CMD CmdInventory"), "in the inventory"),
    (re.compile(r"^CMD CmdTalk"), "talking"),
    (re.compile(r"^CMD (\w+)"), "{0}"),
    (re.compile(r"^GOTO (\d+) (\d+)"), "walking to ({0},{1})"),
    (re.compile(r"^KEY (\S+)"), "key {0}"),
    (re.compile(r"^PASS"), "letting the game act"),
    (re.compile(r"^WAIT"), "waiting for the LLM"),
]

# Actions too frequent to log each time they start (they still show in the header).
QUIET = re.compile(r"^(moving|walking to|key |waiting|letting the game act|the game's automatic)")



def describe(lines):
    for l in lines:
        if l.startswith(("SAY", "STOP", "NEXT")):
            continue
        for pat, text in ACTIONS:
            m = pat.match(l)
            if m:
                return text.format(*m.groups())
    return None


def new_messages(msgs, prev):
    """Messages added since prev (both oldest-first; the game's list is a sliding window)."""
    if not prev:
        return []
    for n in range(min(len(prev), len(msgs)), 0, -1):
        if prev[-n:] == msgs[:n]:
            return msgs[n:]
    return msgs


def update(state, plan, memory, lines):
    try:
        ps = json.loads(STATE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        ps = {}
    ps.setdefault("raise", None)
    ps.setdefault("doing", "")
    turn = state.get("turn")
    log = []

    # Game messages aren't copied in: they're already in the game's own message log (the user, 2026-11-24).
    for l in lines:
        if l.startswith("SAY "):
            log.append(l[4:].strip())
        elif l.startswith(("STOP ", "NEXT ")):
            ps["raise"] = {"turn": turn, "text": l[5:].strip(), "stop": l.startswith("STOP")}
            log.append(("!! Stopped: " if l.startswith("STOP") else "!! Handing over to the LLM: ") + l[5:].strip())

    # The log is a train of thought (the user, 2026-11-24): reasons from the scripts' SAY lines and the
    # LLM's own notes (tools/think.py), not a command log. What's being done shows in the header only.
    doing = describe(lines)
    if doing == "letting the game act" and state.get("autoact"):
        doing = "the game's automatic action (autoexplore / resting / walking)"
    if doing and doing != "letting the game act":
        ps["doing"] = doing

    if log:
        last = ps.get("last_log")
        with open(NARRATION, "a", encoding="utf-8") as f:
            for entry in log:
                if entry != last:
                    f.write(f"{turn}\t{entry}\n")
                last = entry
        ps["last_log"] = last
    STATE.write_text(json.dumps(ps), encoding="utf-8")

    p = state.get("player") or {}
    stages = plan.get("stages") or [plan]
    idx = min(memory.get("_stage", 0), len(stages) - 1)
    script = stages[idx].get("script", "?")
    xp = next((r.strip().split("XP:")[1].strip() for r in (state.get("screen") or {}).get("rows", []) if "XP:" in r), "?")
    out = [
        "OBJECTIVE  " + (plan.get("objective") or plan.get("label") or "-"),
        "GOAL       " + (plan.get("goal") or plan.get("label") or "-"),
        f"NOW        {script}: {ps.get('doing') or '-'}   (turn {turn})",
        f"           {p.get('zoneName') or '?'}   HP {p.get('hp')}/{p.get('maxhp')}   level {p.get('level')}   XP {xp}   {p.get('food') or ''}",
    ]
    TEXT.write_text("\n".join(out) + "\n", encoding="utf-8")
