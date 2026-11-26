"""Read every entry of a list screen with a details panel (skills, mutations...) during a remote run.

  python tools/read_list.py out.md            the list screen must already be open in the game

Moves the cursor down one entry at a time (KEY DownArrow, read-only) and records, for each entry, the
selected line and the full description shown in the panel below it (the text between the panel's
├─title─┤ line and the bottom border). Stops when the screen stops changing. Never presses Space,
Return or anything that could choose or buy. Collapsed categories ([+]) are expanded with "6" first.
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def snapshot():
    return json.loads((ROOT / "live" / "state.json").read_text(encoding="utf-8"))


def parse(rows):
    """(selected line, panel title, panel text) from the screen rows."""
    selected = next((r.strip("│ ").strip() for r in rows if r.strip("│ ").startswith(">")), None)
    start = next((i for i, r in enumerate(rows) if r.lstrip().startswith("├")), None)
    if start is None:
        return selected, None, ""
    title = rows[start].strip("├┤─ ").strip("─ ")
    body = []
    for r in rows[start + 1:]:
        if r.lstrip().startswith("└"):
            break
        body.append(r.strip("│ ").rstrip())
    return selected, title, " ".join(" ".join(b.split()) for b in body if b.strip())


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    out = Path(sys.argv[1])
    entries, last, same, expanded = [], None, 0, set()
    for _ in range(300):
        s = snapshot()
        rows = (s.get("screen") or {}).get("rows", [])
        selected, title, text = parse(rows)
        key = (selected, title, text)
        if key == last:
            same += 1
            if same >= 2:
                break
        else:
            same = 0
            if selected and (not entries or entries[-1][0] != selected):
                entries.append((selected, title, text))
        last = key
        # A collapsed category ("[+] ..."): expand it first (the panel's "6-Expand"; read-only), so its
        # entries get read too; then carry on down.
        if selected and selected.lstrip("> ").startswith("[+]") and selected not in expanded:
            expanded.add(selected)
            subprocess.run([sys.executable, str(ROOT / "tools" / "send.py"), "KEY Keypad6"], capture_output=True)
            continue
        subprocess.run([sys.executable, str(ROOT / "tools" / "send.py"), "KEY DownArrow"], capture_output=True)
    lines = [f"- **{sel.lstrip('> ').strip()}**" + (f": {text}" if text else "") for sel, title, text in entries]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(entries)} entries written to {out}")


if __name__ == "__main__":
    main()
