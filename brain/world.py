"""The world file: what this run has taught us, kept per run in runs/<run id>/world.json.

Scripts stay generic (they must work on any seed); the facts of a particular run live here, and
scripts may rely on them, e.g. "where did we last see the person who gave this quest".

Filled in two ways:
- automatically, on every brain call (step.py calls update): zones visited, creatures and objects
  seen (last known place), and the quest log;
- by hand or by scripts, as notes: facts learned from conversations, signs, events
  (tools/world.py note "Mehmet" "gives the quest What's Eating the Watervine?").

The run id is the game's own ID (the save folder name), from the snapshot's "game" field. Snapshots
from before the mod sent it use "name-<player>"; that file is renamed once the real id appears.

Only what the player could see goes in, like the snapshot itself.
"""
import json, os, re, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
OBJECT_KINDS_KEEP = 400  # cap on remembered objects per world file

CURRENT = None  # the World for the current brain call, set by step.py

# Words the game puts in front of a creature's name for its current state ("wet giant centipede",
# "wet giant centipede [wading]"). Stripped so one kind is one entry. Extend as new ones show up.
STATE_WORDS = {"slime-stained", "blood-stained", "wet", "bloody", "slimy", "dilute", "slimy-finned", "web-toed", "salty", "brackish", "muddy", "oily", "sticky", "tarry", "sappy", "burning", "frozen", "flaming", "sleeping", "stunned", "confused", "dazed"}


def kind_name(name):
    # "feral dog and member of the Third Ithri-Sehian Family": the faction part isn't the kind.
    name = name.split(" and member of ")[0]
    # "glowfish and friend to fungi" (2026-11-25): an allegiance suffix, not the kind.
    name = name.split(" and friend to ")[0]
    base = name.split("[")[0].strip().lower()
    words = base.split()
    while len(words) > 1 and words[0] in STATE_WORDS:
        words = words[1:]
    return " ".join(words)


def run_id(state):
    game = state.get("game") or {}
    if game.get("id"):
        return game["id"]
    name = (state.get("player") or {}).get("name") or "unknown"
    return "name-" + "".join(c for c in name if c.isalnum())


class World:
    def __init__(self, rid, data, path):
        self.id, self.data, self.path = rid, data, path

    # ---- reading (for scripts) ----
    def zone(self, zone_id):
        return self.data["zones"].get(zone_id)

    def creature(self, name):
        """Last sighting of a creature by name (any zone), or None."""
        found = [c for c in self.data["creatures"].values() if c["name"] == name]
        return max(found, key=lambda c: c["last_turn"]) if found else None

    def objects_in(self, zone_id, kind=None):
        return [o for o in self.data["objects"].values() if o["zone"] == zone_id and (kind is None or o.get("kind") == kind)]

    def find_features(self, zone_id, text):
        """Features in a zone whose name contains text (e.g. "fresh water"), from what we've seen."""
        return [f for f in self.data.get("features", {}).values() if f["zone"] == zone_id and text in f["name"]]

    def notes_about(self, subject):
        return [n for n in self.data["notes"] if n.get("about") == subject]

    # ---- creature kinds: what this run has taught us about each kind of creature ----
    # {"verdict": "fight" | "avoid" | "ask", "difficulty": "Average", "mobile": bool,
    #  "effects": [message fragments seen and accepted for this kind, e.g. "You are grabbed"],
    #  "kills": n, "xp": [..], "max_hit": largest damage one of its hits did to us}
    # Verdicts are set by the LLM after assessing a kind (tools/world.py kind ...); scripts read them.
    def kind(self, name):
        """What we know about this kind of creature. Names carry prefixes that don't change the kind
        ("slimy sappy salt-encrusted dreadroot", "web-toed defanged girshling"): if there's no exact
        entry, the longest known kind the name ends with is used."""
        kinds = self.data.setdefault("kinds", {})
        k = kind_name(name)
        if k in kinds:
            return kinds[k]
        ends = [known for known in kinds if k.endswith(" " + known)]
        return kinds[max(ends, key=len)] if ends else None

    def mark_dead(self, name, zone_id, turn):
        """A creature of this name died in this zone (its record stays, for the map's history)."""
        c = self.data["creatures"].get(f"{zone_id}|{name}")
        if c is not None:
            c["dead_turn"] = turn

    def rooted_alive(self, zone_id):
        """Rooted creatures (one record per cell) last seen alive in this zone."""
        return [c for c in self.data["creatures"].values()
                if c["zone"] == zone_id and c.get("rooted") and c.get("hostile")
                and c.get("last_turn", 0) > c.get("dead_turn", -1)]

    def threats(self, zone_id):
        """Hostile creatures last seen alive in this zone (seen again after a death counts as alive)."""
        return [c for c in self.data["creatures"].values()
                if c["zone"] == zone_id and c.get("hostile") and c.get("last_turn", 0) > c.get("dead_turn", -1)]

    def set_kind(self, name, **fields):
        k = self.data.setdefault("kinds", {}).setdefault(kind_name(name), {"verdict": "ask", "effects": [], "kills": 0, "xp": [], "max_hit": 0})
        k.update({key: value for key, value in fields.items() if value is not None})
        return k

    # ---- writing ----
    def note(self, about, text, turn=None, zone=None):
        self.data["notes"].append({"about": about, "text": text, "turn": turn, "zone": zone,
                                   "time": time.strftime("%Y-%m-%dT%H:%M:%S")})

    def mark_zone(self, zone_id, **fields):
        self.data["zones"].setdefault(zone_id, {}).update(fields)

    def update(self, state):
        player = state.get("player") or {}
        zone_id, turn = player.get("zone"), state.get("turn")
        if not zone_id:
            return
        d = self.data
        run = d["run"]
        # The character's own profile (the user, 2026-11-25: track each character's experience and profile
        # separately): stats and XP from the sidebar when it's on screen, and a level history. Mutations
        # and skills come from the character sheet via tools/profile.py.
        prev_level = run.get("level")
        run.update({"player": kind_name(player.get("name") or "") and (player.get("name") or "").split()[-1],
                    "level": player.get("level"), "last_turn": turn,
                    "mode": (state.get("game") or {}).get("mode") or run.get("mode")})
        side = " ".join((state.get("screen") or {}).get("rows") or [])
        stats = {}
        for key in ("ST", "AG", "TO", "IN", "WI", "EG", "QN", "MS", "AV", "DV", "MA"):
            mm = re.search(r"\b" + key + r":\s*(-?\d+)", side)
            if mm:
                stats[key] = int(mm.group(1))
        xp = re.search(r"XP:\s*(\d+)\s*/\s*(\d+)", side)
        prof = run.setdefault("profile", {})
        if stats:
            prof["stats"] = stats
        if xp:
            prof["xp"], prof["xp_next"] = int(xp.group(1)), int(xp.group(2))
        prof["hp"], prof["maxhp"] = player.get("hp"), player.get("maxhp")
        if player.get("level") and player.get("level") != prev_level:
            run.setdefault("levels", []).append({"level": player.get("level"), "turn": turn, "zone": zone_id,
                                                  "maxhp": player.get("maxhp"), "xp": prof.get("xp")})
        z = d["zones"].setdefault(zone_id, {"first_turn": turn})
        z.update({"name": player.get("zoneName"), "last_turn": turn})

        m = state.get("map") or {}
        vis = m.get("vis") or []
        visible = lambda x, y: y < len(vis) and x < len(vis[y]) and vis[y][x] == "1"
        seen_here = set()
        seen_rooted = set()
        for o in m.get("objects", []):
            if o.get("creature"):
                # Rooted kinds never move: one record per cell, so seven dreadroots stay seven (2026-11-24:
                # one record per name collapsed them, and the ones left behind were forgotten).
                rooted = (self.kind(o["name"]) or {}).get("mobile") is False
                # Keyed by the bare kind: a dreadroot in slime turns "sappy dreadroot", which isn't a new one
                # (2026-11-24: the renamed one's old record was marked dead while the plant was alive).
                # The game's own id when the mod sends it (v0.25, 2026-11-25: the user wants creatures referenced
                # by id; by name every "wet glowpad" in a zone was one record). Otherwise as before.
                if o.get("id"):
                    key = f"{zone_id}|id:{o['id']}"
                else:
                    key = f"{zone_id}|{kind_name(o['name'])}|{o['x']}|{o['y']}" if rooted else f"{zone_id}|{o['name']}"
                seen_rooted.add(key)
                c = d["creatures"].setdefault(key, {"name": o["name"], "zone": zone_id, "first_turn": turn, "id": o.get("id")})
                c["name"] = o["name"]
                c.update({"x": o["x"], "y": o["y"], "glyph": o["glyph"], "last_turn": turn, "rooted": rooted,
                          "hostile": bool(o.get("hostile")) or c.get("hostile", False)})
            else:
                key = f"{zone_id}|{o['name']}|{o['x']}|{o['y']}"
                seen_here.add(key)
                ob = d["objects"].setdefault(key, {"name": o["name"], "zone": zone_id, "x": o["x"], "y": o["y"], "first_turn": turn})
                ob.update({"glyph": o["glyph"], "last_turn": turn})
        # A rooted creature whose cell is in view without it is dead (it can't have moved).
        for key, c in d["creatures"].items():
            if (c.get("rooted") and c["zone"] == zone_id and key not in seen_rooted and visible(c["x"], c["y"])
                    and not (c.get("id") and any(o.get("id") == c["id"] for o in m.get("objects", [])))
                    and c.get("dead_turn", -1) < c.get("last_turn", 0)):
                c["dead_turn"] = turn
        # A creature's last known cell is in view now and it isn't there: it has moved, whereabouts
        # unknown. threats() keeps it (it's alive) but distance rules can't use a stale position.
        for c in d["creatures"].values():
            if (c["zone"] == zone_id and c.get("last_turn", 0) < turn and visible(c.get("x", -1), c.get("y", -1))
                    and kind_name(c["name"]) not in {kind_name(o["name"]) for o in m.get("objects", []) if o.get("creature") and (o["x"], o["y"]) == (c["x"], c["y"])}):
                c["moved_turn"] = turn

        # Deaths in the latest messages, however they happened (fight routine or by hand): creatures of
        # that kind in this zone that aren't in view any more are marked dead. Death messages carry state
        # words ("The bloody cave spider dies!"), so match by kind.
        in_view = {kind_name(o["name"]) for o in m.get("objects", []) if o.get("creature")}
        for msg in (state.get("messages") or [])[-6:]:
            if msg.startswith("The ") and msg.endswith(" dies!"):
                dead = kind_name(msg[4:-6])
                with_ids = any(o.get("id") for o in m.get("objects", []) if o.get("creature"))
                if dead in in_view and not with_ids:
                    continue  # by name we can't tell which one died
                ids_now = {o.get("id") for o in m.get("objects", []) if o.get("creature") and o.get("id")}
                for c in d["creatures"].values():
                    if c["zone"] == zone_id and kind_name(c["name"]) == dead and c.get("dead_turn", -1) < c.get("last_turn", 0):
                        # With ids, only the one that was in view a moment ago and is gone now died; the others of
                        # that kind out of sight are still alive.
                        if c.get("id") and (c["id"] in ids_now or c.get("last_turn", 0) < turn - 3):
                            continue
                        c["dead_turn"] = turn

        # Objects remembered in cells that are in view now but no longer show them are gone.
        for key in [k for k, o in d["objects"].items() if o["zone"] == zone_id and k not in seen_here and visible(o["x"], o["y"])]:
            del d["objects"][key]
        if len(d["objects"]) > OBJECT_KINDS_KEEP:
            for key in sorted(d["objects"], key=lambda k: d["objects"][k]["last_turn"])[: len(d["objects"]) - OBJECT_KINDS_KEEP]:
                del d["objects"][key]

        # Named terrain and features (pools with their liquid, furniture, plants; world-map terrain),
        # so scripts can ask "where is fresh water" later. Keyed by cell; the latest name wins.
        feats = d.setdefault("features", {})
        for f in m.get("features", []) or []:
            feats[f"{zone_id}|{f['x']}|{f['y']}"] = {"zone": zone_id, "x": f["x"], "y": f["y"], "name": f["name"], "last_turn": turn}

        quests = [q for q in state.get("quests") or [] if isinstance(q, dict)]
        if quests:
            d["quests"] = quests

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        game = load_game()
        for key in SHARED:
            if key in self.data:
                game[key] = self.data[key]
        gtmp = GAME.with_suffix(".tmp")
        gtmp.write_text(json.dumps(game, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(gtmp, GAME)
        run = {k: v for k, v in self.data.items() if k not in SHARED}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(run, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self.path)


def empty(rid):
    return {"run": {"id": rid}, "zones": {}, "creatures": {}, "objects": {}, "quests": [], "notes": [], "kinds": {}}


# Game knowledge vs world knowledge (the user, 2026-11-24): creature kinds and safe foods are facts about the
# game, shared by every run; places, people, sightings and notes are facts about one world (seed). The shared
# part lives in brain/game_knowledge.json, the only copy: load() puts it into data["kinds"] / data["food"] so
# scripts read it as before, and save() writes it back there and leaves it out of the run's file.
GAME = ROOT / "brain" / "game_knowledge.json"
# Weapon records are not shared (2026-11-26): hit rates depend on the character's skills and level, so
# they live in each run's world.json; the old pooled records stay in game_knowledge.json untouched.
SHARED = ("kinds", "food", "liquid_kinds", "feature_kinds")  # never "features": the per-run map features


def load_game():
    try:
        return json.loads(GAME.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def load(state, apply=True):
    """The run's world. Only the brain applies queued edits (apply=True); tools read with apply=False."""
    rid = run_id(state)
    path = RUNS / rid / "world.json"
    if not path.exists():
        # The mod started sending the real id: adopt the file kept under the player's name.
        old = RUNS / run_id({"player": state.get("player")}) / "world.json"
        if rid != old.parent.name and old.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            os.replace(old, path)
            try:
                old.parent.rmdir()
            except OSError:
                pass
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else empty(rid)
    data["run"]["id"] = rid
    game = load_game()
    for key in SHARED:
        if key in game:
            data[key] = game[key]
    w = World(rid, data, path)
    if apply:
        apply_edits(w)
    return w


# Edits from tools (notes, kind verdicts, approved food) are queued in runs/<id>/edits.jsonl and applied
# by the brain when it loads the world. The brain rewrites world.json on every call, so a tool writing it
# directly could be overwritten by a call in flight.
GAME_EDITS = ROOT / "brain" / "game_edits.jsonl"
GAME_OPS = ("kind", "food")  # "evaluate" goes to the run queue: it also clears the run's to_evaluate list   # edits to shared game knowledge: applied by whichever run calls next


def queue_edit(rid, edit):
    # Kinds and food are game knowledge: queue them where any run applies them, so a fact recorded as a
    # run ends (a death) isn't lost when the next game is a new character (2026-11-24).
    path = GAME_EDITS if edit.get("op") in GAME_OPS else RUNS / rid / "edits.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(edit, ensure_ascii=False) + "\n")


def apply_edits(w):
    for path in (w.path.parent / "edits.jsonl", GAME_EDITS):
        _apply_edit_file(w, path)


def _apply_edit_file(w, path):
    if not path.exists():
        return
    taking = path.with_suffix(".applying")
    try:
        os.replace(path, taking)
    except OSError:
        return
    for line in taking.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("op") == "note":
            w.note(e["about"], e["text"], turn=e.get("turn"), zone=e.get("zone"))
        elif e.get("op") == "kind":
            k = w.set_kind(e["name"], **e.get("fields", {}))
            k["effects"] = sorted(set(k.get("effects", []) + e.get("effects", [])))
        elif e.get("op") == "dead":
            for c in w.data["creatures"].values():
                if c["zone"] == e["zone"] and c["name"] == e["name"]:
                    c["dead_turn"] = max(c.get("last_turn", 0), e.get("turn") or 0)
        elif e.get("op") == "moved":
            for c in w.data["creatures"].values():
                if c["zone"] == e["zone"] and c["name"] == e["name"]:
                    c["moved_turn"] = max(c.get("last_turn", 0) + 1, e.get("turn") or 0)
        elif e.get("op") == "loot":
            # {"op": "loot", "kind": ..., "verdict": "take" | "skip" | None (forget)}
            loot = w.data.setdefault("loot", {})
            if e.get("verdict"):
                loot[e["kind"]] = {"verdict": e["verdict"], "why": e.get("why", "set by the LLM")}
            else:
                loot.pop(e["kind"], None)
        elif e.get("op") == "evaluate":
            # {"op": "evaluate", "type": "liquid"|"feature", "kind": ..., "note": ...}: the LLM's verdict
            k = e["kind"]
            pending = w.data.setdefault("to_evaluate", [])
            hit = [x for x in pending if x["kind"] == k]
            typ = e.get("type") or ("liquid" if any(x["key"].startswith("liquid: ") for x in hit) else "feature")
            store = w.data.setdefault("liquid_kinds" if typ == "liquid" else "feature_kinds", {})
            store[k] = {"note": e.get("note", ""), "turn": e.get("turn")}
            w.data["to_evaluate"] = [x for x in pending if x["kind"] != k]
        elif e.get("op") == "food":
            food = w.data.setdefault("food", [])
            for name in e.get("add", []):
                if name not in food:
                    food.append(name)
            for name in e.get("remove", []):
                if name in food:
                    food.remove(name)
    w.save()
    taking.unlink()
