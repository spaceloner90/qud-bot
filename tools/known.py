"""What do we already know about this? Search the shared game knowledge and the research notes for a
text (a game message, a creature, an item, an effect) before calling it new or unexplained (the user,
2026-11-25: the Amphibious water pouring was known since run 1, and I called it a mystery).

  python tools/known.py "pour fresh water"
  python tools/known.py "tumbling pod"

Prints matching game_knowledge.json entries (messages, kinds, food, weapons) and research lines.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    q = " ".join(sys.argv[1:]).lower()
    words = [w for w in re.findall(r"[a-z0-9']+", q) if len(w) > 2]
    hit = lambda s: q in s.lower() or (words and all(w in s.lower() for w in words))
    g = json.loads((ROOT / "brain" / "game_knowledge.json").read_text(encoding="utf-8"))
    n = 0
    for section in ("messages", "kinds", "food", "weapons"):
        sec = g.get(section) or {}
        for k, v in (sec.items() if isinstance(sec, dict) else ((x, "") for x in sec)):
            if hit(k) or hit(json.dumps(v, ensure_ascii=False)):
                print(f"[game_knowledge {section}] {k}: {json.dumps(v, ensure_ascii=False)[:400]}")
                n += 1
    for f in sorted((ROOT / "research").glob("*.md")):
        for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if hit(line):
                print(f"[{f.relative_to(ROOT)}:{i}] {line.strip()[:300]}")
                n += 1
    print(f"{n} match(es)" if n else "nothing known: it may really be new")
    return 0


if __name__ == "__main__":
    sys.exit(main())
