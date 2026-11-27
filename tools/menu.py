"""Menu macros (the user, 2026-11-24: menus need macros, not one key per round trip). Cursor moves go
out as one batch; the screen is checked once before each confirming key.

  python tools/menu.py item "<name>" <action>       e.g. item "witchwood bark" eat, item "salve" apply
  python tools/menu.py trade <dir> [--sell NAME ...] [--buy NAME[:QTY] ...] [--examine NAME]
                                                    dir: N S E W NE NW SE SW (the trader's side)

Names match loosely: case-insensitive, ignoring prefixes like "slimy wet", and the first row whose
text contains the name wins. Actions are the item menu's words (eat, apply, equip, drop, look,
remove); the matching letter is read from the menu. Popups after the action are read and dismissed
only if they're plain "press space" popups; anything else stops with the screen printed.
Needs a live run in the remote stage (like tools/send.py).
"""
import json, re, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR_KEYS = {"N": "Keypad8", "S": "Keypad2", "E": "Keypad6", "W": "Keypad4",
            "NE": "Keypad9", "NW": "Keypad7", "SE": "Keypad3", "SW": "Keypad1"}


def state():
    return json.loads((ROOT / "live" / "state.json").read_text(encoding="utf-8-sig"))


def rows(s=None):
    return ((s or state()).get("screen") or {}).get("rows", [])


sys.path.insert(0, str(ROOT / "tools"))
import send as _send  # in process: a Python start per key was a third of each key's time (2026-11-25)
_checked = False


def send(*lines):
    global _checked
    code = _send.play(list(lines), check_run=not _checked)
    if code in (2, 4):
        sys.exit(f"send failed (code {code})")
    if code == 3:  # the game didn't take it within 8 s: kick back rather than carry on blind (2026-11-25)
        fail(f"the game didn't take {lines[0]!r} (no new snapshot in 8 s)")
    _checked = True


def say(text):
    subprocess.run([sys.executable, str(ROOT / "tools" / "say.py"), text], cwd=ROOT, capture_output=True)


def fail(msg):
    say("A menu did not go as expected; looking at the screen.")
    print("stopped:", msg)
    print("\n".join(rows()))
    sys.exit(3)


def norm(t):
    return re.sub(r"\s+", " ", t.lower()).strip()


def selected_index(rs, col):
    for i, r in enumerate(rs):
        seg = r[col:col + 6]
        if ">" in seg:
            return i
    return None


def find_row(rs, name, col, width=40):
    n = norm(name)
    hits = [i for i, r in enumerate(rs) if n in norm(r[col:col + width])]
    # Prefer an item row (price, weight or letter); screens without them (the skills list, 2026-11-25:
    # "Spry [100sp]" was never found) take the first plain match.
    for i in hits:
        if re.search(r"\$|#|\)", rs[i][col:col + width]):
            return i
    return hits[0] if hits else None


BURST = 3  # cursor keys that land from one answer (measured 2026-11-25: 3, 5 and 8 sent all moved 3)


def select(name, col=0, width=40, max_sends=60):
    """Move the cursor (in the column starting at col) onto the row containing name. Sends bursts of up to
    BURST cursor keys and checks where the cursor ended up (the user, 2026-11-25: press fuzzily, observe the
    state instead): extra keys may be dropped and header rows skipped, so each burst is followed by a look,
    and an overshoot is corrected back. Off screen, the row may be above or below (2026-11-25: the slugs had
    scrolled out at the top): search down, and once the list stops moving, search up."""
    n = norm(name)
    down, last = True, None
    for _ in range(max_sends):
        rs = rows()
        cur = selected_index(rs, col)
        if cur is not None and n in norm(rs[cur][col:col + width]):
            return True
        tgt = find_row(rs, name, col, width)
        if tgt is None or cur is None:
            view = (cur, tuple(r[col:col + width] for r in rs))
            if view == last:
                if not down:
                    return False  # stuck at the top too
                down = False
            last = view
            key, k = ("KEY DownArrow" if down else "KEY UpArrow"), BURST
        else:
            key = "KEY DownArrow" if tgt > cur else "KEY UpArrow"
            k = max(1, min(abs(tgt - cur), BURST))
        send(*[key] * k)
    return False


def popup_text(rs):
    """The popup's own lines: the text between its ▌ and ▐ borders, without the screen behind it
    (2026-11-26: an item's look card printed as a cut-off line mixed with the inventory list)."""
    out = []
    for x in rs:
        if "▌" in x:
            inner = x[x.index("▌") + 1:x.rindex("▐")] if "▐" in x[x.index("▌") + 1:] else x[x.index("▌") + 1:]
            if inner.strip():
                out.append(inner.strip())
    return out


def dismiss_popups(limit=6, full=False):
    for _ in range(limit):
        s = state()
        if s.get("wait") == "map":
            return
        text = " ".join(rows(s)).lower()
        if "press space" in text or "press [space]" in text:
            joined = " / ".join(popup_text(rows(s)))
            print("popup:", joined if full else joined[:200])
            send("KEY Space")
            continue
        return


def escape_to_map(limit=5):
    for _ in range(limit):
        if state().get("wait") == "map":
            return True
        send("KEY Escape")
    return state().get("wait") == "map"


def new_messages(before, after):
    """The messages in after that weren't in before (the log is a sliding window of the last few)."""
    for k in range(min(len(before), len(after)), 0, -1):
        if before[-k:] == after[:k]:
            return after[k:]
    return list(after)


def pick_action(menu, action):
    """The letter of the item-menu entry for action, case-insensitive. Of several (2026-11-25: "Equip"
    matched "E) Equip (manual)", which opens a slot picker, not "e) equip (auto)"), the automatic one."""
    found = re.findall(r"\b([a-zA-Z])\) (" + re.escape(action) + r"[^▐▌│]*)", menu, re.I)
    if not found:
        return None
    found.sort(key=lambda f: ("manual" in f[1].lower(), f[1][:1].isupper()))
    return found[0][0]


def item(name, action):
    if state().get("wait") != "map":
        fail("not on the map")
    before = list(state().get("messages") or [])
    send("CMD CmdInventory")
    if "Inventory" not in " ".join(rows()):
        fail("the inventory didn't open")
    if not select(name):
        escape_to_map()
        fail(f"no item matching {name!r}")
    send("KEY Space")
    key = pick_action(" ".join(rows()), action)
    if not key:
        fail(f"no '{action}' in the item's menu")
    send(f"KEY {key}")
    dismiss_popups(full=action.lower() == "look")  # a look card is read in full
    escape_to_map()
    s = state()
    # Report only what this action said: old messages read as success (2026-11-25: a failed equip
    # printed "done" with the trade's messages).
    new = new_messages(before, s.get("messages") or [])
    if not new and action.lower() not in ("look", "add notes", "mark important"):
        fail(f"'{action}' on {name!r} changed nothing in the message log")
    print("done:", " | ".join(new[-3:]))


def read_column(col, pages=8):
    """Every row text in a trade column, scrolling down a page at a time (batched)."""
    seen = []
    for _ in range(pages):
        for r in rows()[1:22]:
            t = r[col:col + 40].strip("█▒│> ").rstrip()
            if t and t not in seen:
                seen.append(t)
        send(*["KEY Keypad2"] * 18)
    return seen


def trade(direction, sell, buy, examine):
    if "Your inventory" in " ".join(rows()):
        pass  # already on a trade screen (2026-11-25: picking up there meant driving it by hand)
    elif state().get("wait") != "map":
        fail("not on the map or a trade screen")
    else:
        send("CMD CmdTalk")
        if "direction" not in " ".join(rows()):
            fail("no talk direction prompt")
        send(f"KEY {DIR_KEYS[direction]}")
        m = re.search(r"\b([1-9])\) Let.s trade", " ".join(rows()))
        if not m:
            fail("no 'Let's trade' option")
        send(f"KEY {m.group(1)}")
        if "Your inventory" not in " ".join(rows()):
            fail("the trade screen didn't open")
    for spec in buy:
        nm, _, qty = spec.partition(":")
        if not select(nm, col=0):
            fail(f"the trader has no {nm!r}")
        if qty:
            send(*[f"KEY {c}" for c in qty])
        else:
            send("CMD CmdTradeAdd")
    if sell or examine:
        send("KEY RightArrow")
    for nm in sell:
        if not select(nm, col=39):
            fail(f"we have no {nm!r} to sell")
        send("CMD CmdTradeAdd")
    if examine:
        if not select(examine, col=39):
            fail(f"we have no {examine!r}")
        send("CMD CmdVendorExamine")
        popup = [x.strip("│ ▌▐").strip() for x in rows() if "▌" in x and x.strip("▌▐ █│")]
        print("examine:", " / ".join(popup)[:300])
        send("KEY Space")
    totals = next((r for r in rows() if "drams" in r), "")
    print("totals:", totals.strip())
    if buy or sell:
        send("CMD CmdTradeOffer")
        offer = " ".join(x.strip("│ ▌▐").strip() for x in rows() if "▌" in x and x.strip("▌▐ █│"))
        print("offer:", offer[:200])
        if "Agreed" not in offer:
            fail("no offer to agree to")
        send("KEY y")
        dismiss_popups()
    escape_to_map()
    if state().get("wait") != "map":   # back in the conversation: end it
        m = re.search(r"\b([1-9])\) .*\[End\]", " ".join(rows()))
        if m:
            send(f"KEY {m.group(1)}")
    print("done:", " | ".join((state().get("messages") or [])[-3:]))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    a = sys.argv[1:]
    if not a:
        print(__doc__)
        return
    if a[0] == "item" and len(a) >= 3:
        item(a[1], a[2])
    elif a[0] == "trade" and len(a) >= 2:
        sell, buy, examine, mode = [], [], None, None
        for x in a[2:]:
            if x in ("--sell", "--buy", "--examine"):
                mode = x
            elif mode == "--sell":
                sell.append(x)
            elif mode == "--buy":
                buy.append(x)
            elif mode == "--examine":
                examine = x
        trade(a[1].upper(), sell, buy, examine)
    else:
        print(__doc__)


if __name__ == "__main__":
    import atexit, narrate_check
    atexit.register(narrate_check.remind)
    main()
