"""The tools index, generated from each tool's own docstring, so it can't drift from the tools (the
Gemini/Antigravity handover, 2026-11-26, asked for a one-page index; a hand-written one would go stale).

  python tools/help.py             the core live-play tools: what each does and its usage lines
  python tools/help.py --all       every tool in tools/
  python tools/help.py walk kill   just these, with the full docstring

AGENTS.md still holds: read a tool's docstring before using it, never call one from memory. This prints
those docstrings in one call.
"""
import ast, sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
# In the order a hand-over usually needs them.
CORE = ["brief", "send", "walk", "approach", "kill", "wait", "menu", "macro", "next_zone", "frontier",
        "siege", "watch_handover", "world", "known", "profile", "fights", "say", "think", "voice"]


def doc(name):
    path = TOOLS / f"{name}.py"
    try:
        return ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) or "(no docstring)"
    except (OSError, SyntaxError) as e:
        return f"(unreadable: {e})"


def summary(text):
    """The first paragraph (what it does) and the indented usage lines."""
    paras = text.split("\n\n")
    usage = [l for l in text.splitlines() if l.startswith(("  python ", "  -"))]
    return paras[0].replace("\n", " ") + ("\n" + "\n".join(usage) if usage else "")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if args and args[0] != "--all":
        for name in args:
            print(f"===== tools/{name}.py\n{doc(name)}\n")
        return
    names = sorted(p.stem for p in TOOLS.glob("*.py")) if args else CORE
    for name in names:
        print(f"## {name}\n{summary(doc(name))}\n")
    if not args:
        print("(python tools/help.py --all for every tool; python tools/help.py <name> for one in full)")


if __name__ == "__main__":
    main()
