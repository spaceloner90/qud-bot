"""Record the character's sheet (attributes, mutations, owned skills, points, level, XP) into the run's
profile, runs/<id>/profile.json, with a history entry per call (the user, 2026-11-25: track each character's
profile separately). Run it at every level-up, after spending points.

  python tools/profile.py

Opens the character sheet and the skills page, reads them, and closes them. Needs a live run in the remote
stage, on the map. The brain keeps stats, XP and the level history from the sidebar in world.json's "run".
"""
import json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "brain"))
import world as W  # noqa: E402
sys.path.insert(0, str(ROOT / "tools"))
import menu as M  # noqa: E402


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    s = M.state()
    if s.get("wait") != "map":
        print("not on the map")
        return 2
    rid = W.run_id(s)
    M.send("CMD CmdCharacter")
    sheet = M.rows()
    text = "\n".join(sheet)
    attrs = {k: int(v) for k, v in re.findall(r"(Strength|Agility|Toughness|Intelligence|Willpower|Ego)\s+(\d+)", text)}
    muts = re.findall(r"\s{2,}([A-Z][A-Za-z' -]+?) \((\d+|D)\)", text)
    pts = re.search(r"Skill points: (\d+), Attribute points: (\d+), Mutation points: (\d+)", text)
    lvl = re.search(r"Level: (\d+)", text)
    xp = re.search(r"XP: (\d+)", text)
    M.send("KEY Keypad7")
    skills = []
    # One row at a time, expanding every collapsed group ([+]) the cursor lands on: a collapsed group hides
    # its skills, and once the profile listed only Long Blade (Siwur, 2026-11-26, after the groups had been
    # collapsed to find it). Owned ones carry no [cost], a group header included ("[+] Axe" owned).
    same = 0
    for _ in range(400):
        rows = M.rows()
        for r in rows[2:22]:
            m = re.search(r"(?:\[[-+]\]|-)\s+([A-Z][A-Za-z' !-]+?)\s*(\[\d+sp\].*)?\s*[│|]?$", r.strip("│ >"))
            if m and not m.group(2) and m.group(1).strip() not in skills and "sp remaining" not in r:
                skills.append(m.group(1).strip())
        cursor = next((r for r in rows[2:22] if r.strip("│ ").startswith(">")), "")
        if "[+]" in cursor:
            M.send("KEY Keypad6")
            continue
        M.send("KEY Keypad2")
        same = same + 1 if M.rows() == rows else 0
        if same >= 2:  # the cursor stopped moving: the end of the list
            break
    M.escape_to_map()
    prof = {"turn": s.get("turn"), "level": int(lvl.group(1)) if lvl else None, "xp": int(xp.group(1)) if xp else None,
            "attributes": attrs, "mutations": {n.strip(): r for n, r in muts},
            "skills": skills,
            "points": dict(zip(("skill", "attribute", "mutation"), map(int, pts.groups()))) if pts else None,
            "hp": (s.get("player") or {}).get("hp"), "maxhp": (s.get("player") or {}).get("maxhp"),
            "equipped": s.get("equipped"), "recorded": time.strftime("%Y-%m-%d %H:%M")}
    path = ROOT / "runs" / rid / "profile.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        data = {"character": (s.get("player") or {}).get("name"), "history": []}
    data["current"] = prof
    data["history"].append(prof)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: prof[k] for k in ("level", "xp", "attributes", "mutations", "skills", "points")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
