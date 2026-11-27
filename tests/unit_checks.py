"""Small checks of bot logic that don't need a whole frozen state, each from a bug found in a run. Run by
tools/replay_tests.py. Each check raises AssertionError with what went wrong."""
import re


def sword_estimate_not_zero():
    """Uumurem 2026-11-26: the long sword's record was 0 hits / 3 misses (torch misses and unrecorded hand
    swings), so the estimate said 0.0 a turn and the bot handed over a 3-HP bat as 'kite'."""
    import threat
    us = {"hp": 27, "maxhp": 27, "av": 4, "dv": 8, "ag_mod": 1,
          "weapon": {"name": "two-handed iron long sword", "pv": 7, "dice": "1d8"}}
    weapons = {"two-handed iron long sword": {"hits": 0, "misses": 3, "dmg": 0, "mult": 0, "av": 0, "av_n": 0}}
    d = threat.our_dpt(us, {"av": 2, "dv": 2, "hp": 3, "agi": 1}, weapons)
    assert d and d > 1.0, f"our_dpt {d} with a 0/3 record"


def torch_miss_is_not_the_weapons():
    """A miss with the off-hand torch must not count as the wielded weapon's (2026-11-26)."""
    import threat
    m = threat.OURS.match("You miss with your lit torch! [5 vs 11]")
    assert m and m.group(6) == "lit torch", "the miss's weapon isn't captured"


def thrown_hit_parses_and_is_ranged():
    """The hulking baboon's boulder (2026-11-26) must parse as a hit and mark the kind ranged."""
    from scripts import fight
    h = fight.HIT.match("The hulking baboon hits with a small boulder (x5) for 9 damage!")
    assert h and h.group(1) == "hulking baboon" and h.group(2) == "9", f"HIT groups {h and h.groups()}"
    assert re.search(r" hits with an? .+ \(x\d+\) for \d+ damage", "The hulking baboon hits with a small boulder (x5) for 9 damage!")


def rest_when_only_rooted_far():
    """Yim 2026-11-26: 50 one-turn waits in sight of a rooted glowpad 13 cells off; heal() must rest."""
    from scripts import fight

    class W:
        def kind(self, name):
            return {"mobile": False} if "glowpad" in name else {}
    state = {"turn": 100, "player": {"x": 46, "y": 7},
             "map": {"objects": [{"name": "wet glowpad", "x": 33, "y": 0, "creature": True, "hostile": True}]}}
    fightmem = {}
    assert fight.heal(fightmem, state, W(), []) == "CMD CmdWaitUntilHealed"
    # the game refused (the turn didn't move): fall back to one-turn waits
    assert fight.heal(fightmem, state, W(), []) == "CMD CmdWait"
    # a mobile hostile in view: never rest
    state2 = {"turn": 5, "player": {"x": 0, "y": 0},
              "map": {"objects": [{"name": "snapjaw", "x": 9, "y": 0, "creature": True, "hostile": True}]}}
    assert fight.heal({}, state2, W(), []) == "CMD CmdWait"


def owned_item_is_declined():
    """Siwur 2026-11-26: 'That is not owned by you. Are you sure you want to take it?' handed over."""
    import world
    from scripts import explore

    class W:
        data = {"kinds": {}}
        def kind(self, n): return {}
        def objects_in(self, z): return []
    world.CURRENT = W()
    state = {"wait": "key", "turn": 1, "player": {"x": 1, "y": 1, "hp": 18, "maxhp": 18, "zone": "z"},
             "screen": {"rows": ["▌ That is not owned by you. Are you sure you want to take it? ▐",
                                 "█▄▄[Yes] [No] [ESC-Cancel]▄▄█"]},
             "messages": [], "map": {"objects": [], "rows": []}}
    out = explore.act(state, {}, {"fight": False, "hunt": False})
    assert any(l == "KEY Escape" for l in out), f"answer {out}"
    assert not any(l.startswith("STOP") for l in out), f"answer {out}"


def popup_never_gets_a_bare_pass():
    """Yim 2026-11-26: on "There's nothing to take." collect answered only a SAY line, step.py made it PASS,
    and a popup never asks again: the run sat for minutes. Off the map nothing-to-play must be WAIT."""
    import step
    assert step.keep_asking([], {"wait": "key"}) == ["WAIT"]
    assert step.keep_asking(["SAY Did not get x"], {"wait": "key"})[-1] == "WAIT"
    assert step.keep_asking(["PASS"], {"wait": "picker"}) == ["WAIT"]
    assert step.keep_asking([], {"wait": "map"}) == ["PASS"]
    assert step.keep_asking(["KEY Space"], {"wait": "key"}) == ["KEY Space"]


def rewritten_plan_is_new():
    """Uumurem 2026-11-26: an identical plan re-sent after a hand-over was ignored; the run sat in the remote
    stage. A rewrite (new mtime) of the same text must count as a new plan."""
    import step
    mem = {"_plan": "P", "_plan_mtime": 100.0}
    assert step.plan_changed(mem, "P", 200.0), "same text, rewritten: must be new"
    assert not step.plan_changed(mem, "P", 100.0), "untouched: not new"
    assert step.plan_changed(mem, "Q", 100.0), "different text: new"


def flying_prey_is_not_hunted():
    """Yim 2026-11-26: two giant dragonflies were planned as prey; flying ones can't be hit from the ground."""
    from scripts import fight

    class W:
        def kind(self, name):
            return {"prey": True} if "dragonfly" in name else {}
    assert not fight.is_prey({"name": "giant dragonfly", "creature": True, "effects": ["flying"], "hostile": False}, W())
    assert fight.is_prey({"name": "giant dragonfly", "creature": True, "effects": [], "hostile": False}, W())


def charge_only_from_three_cells():
    """Charge from 2 cells failed with 'no clear line' four times (Yim, Uumurem); from 4 it worked."""
    import inspect
    from scripts import fight
    src = inspect.getsource(fight)
    m = re.search(r'(\d) <= dist <= (\d) and is_ready\("Charge"\)', src)
    assert m and int(m.group(1)) >= 3, f"Charge allowed from {m and m.group(1)} cells"


def proficiency_counts_in_to_hit():
    """The dagger switch (Uumurem 2026-11-26): the estimate ignored Axe Proficiency's +2 to hit."""
    import threat
    us = {"ag_mod": 1, "skills": ["Axe", "Axe Proficiency"], "weapon": {"name": "bronze battle axe"}}
    assert abs(threat.to_hit_bonus(us, {}) - 3) < 1e-9, threat.to_hit_bonus(us, {})
    us["weapon"] = {"name": "iron dagger"}
    assert abs(threat.to_hit_bonus(us, {}) - 1) < 1e-9
    # the game's own rolls win as they accumulate: 20 rolls averaging 14.5 -> +4 seen, blended with +1
    b = threat.to_hit_bonus(us, {"rolls": 290, "roll_n": 20})
    assert 2.9 < b < 3.1, b


def weapon_records_are_per_character():
    """Weapon records were shared game knowledge by name, pooling five characters' swings (2026-11-26).
    And the run's own per-cell "features" must never be shared (a key collision copied them out, same day)."""
    import world
    assert "weapons" not in world.SHARED, world.SHARED
    assert "features" not in world.SHARED and "creatures" not in world.SHARED, world.SHARED


def missile_weapon_fills_empty_slot():
    """Uumurem 2026-11-26: a bow and arrows from the first fight were never considered."""
    import threat
    st = {"inventory": ["short bow \x1a4 [empty]", "wooden arrow x7 \x1a4 \x031d2"], "player": {}, "screen": {"rows": []},
          "equipped": ["two-handed iron long sword \x1a7 \x031d8"]}
    v = threat.gear_verdict(st, "short bow")
    assert v and "missile" in v and "arrow" in v, v


def new_liquids_and_features_are_listed():
    """Uumurem 2026-11-26: cider and wine weeps on a peaceful surface went unevaluated."""
    import features

    class W:
        data = {"liquid_kinds": {"water": {}}, "feature_kinds": {"dirt path": {}}}
    st = {"turn": 1, "player": {"zone": "JoppaWorld.11.20.1.1.10"},
          "map": {"features": [{"name": "puddle of 12 drams of salty cider", "x": 3, "y": 4},
                               {"name": "pool of 500 drams of brackish water", "x": 5, "y": 5},
                               {"name": "dirt path", "x": 1, "y": 1},
                               {"name": "cider weep", "x": 3, "y": 3}]}}
    new = features.scan(st, W())
    keys = sorted(e["key"] for e in new)
    assert keys == ["feature: cider weep", "liquid: cider"], keys
    assert features.scan(st, W()) == [], "listed twice"
    assert "cider" in features.pending_text(W())
    st["player"]["zone"] = "JoppaWorld"
    assert features.scan(st, type("W2", (), {"data": {}})()) == [], "world-map tiles are not features"


def feature_kinds_are_world_neutral():
    """Siwur 2026-11-26: 'shrine to Nathritafa, the Cerulean Bane of Namritara' went into shared game
    knowledge as a kind; stained and frozen watervine were each a kind; a frozen deep pool was a feature."""
    import features as F
    cases = {"shrine to Nathritafa, the Cerulean Bane of Namritara": "shrine",
             "shrine to Ithri-Seh III, the Platinum Altimeter": "shrine",
             "Namritara Glassfold": F.PROPER,
             "sap-and-blood-stained watervine": "watervine", "frozen watervine": "watervine",
             "salt-encrusted brinestalk": "brinestalk", "wet cider weep": "cider weep",
             "alchemist's table": "alchemist's table", "torch sconce": "torch sconce"}
    for name, kind in cases.items():
        assert F.feature_kind(name) == kind, (name, F.feature_kind(name))
    assert F.base_liquid("frozen deep pool of 3960 drams of brackish water") == "water"
    assert F.base_liquid("painted vase [4 drams of oil]") == "oil"
    assert F.base_liquid("vase [honey]") == "honey"
    assert F.base_liquid("pool table") is None


def chests_are_opened_like_by_hand():
    """Siwur 2026-11-27: auto-loot never opened containers (one held the short bow we lacked). Replays the
    real screens from opening two chests by hand: the script must press what I pressed."""
    import json
    from pathlib import Path
    from scripts import collect
    steps = json.loads((Path(__file__).parent / "fixtures" / "chest_open_states.json").read_text(encoding="utf-8"))
    by_seq = {s["seq"]: s for s in steps}

    class W:
        def __init__(self, box):
            self.data = {}
            self.box = box
        def objects_in(self, zone):
            return [self.box]
    zone = by_seq[3896]["state"]["player"]["zone"]
    worlds = []
    for box, seqs in (({"name": "chest", "x": 74, "y": 19}, range(3896, 3903)),
                      ({"name": "chest", "x": 76, "y": 19}, range(3903, 3909))):
        w, c = W(dict(box, zone=zone)), {"tried": [], "taken": [], "steps": 0}
        worlds.append(w)
        for seq in seqs:
            s = by_seq[seq]
            st = s["state"]
            got = [l for l in collect.chest_step(st, c, w, zone, st["player"]["x"], st["player"]["y"]) or []
                   if not l.startswith("SAY")]
            assert got == [s["answer"]], (seq, got, s["answer"])
    # the first chest is recorded as opened, so it isn't tried again after a plan change
    assert "74,19,chest" in worlds[0].data.get("opened", {}).get(zone, []), worlds[0].data


def chest_menu_is_not_an_item_menu():
    """Siwur 2026-11-27: after "g" took the staff (the chest's last item), the game went back to the cell's
    list with the chest's own menu up ("o) open", "g) get"); the routine took that for an item menu and
    pressed g, picking up the chest itself. The replayed screens up to there must match, then that menu
    gets Escape (the chest is done)."""
    import json
    from pathlib import Path
    from scripts import collect
    steps = json.loads((Path(__file__).parent / "fixtures" / "chest_stale_menu_states.json").read_text(encoding="utf-8"))
    by_seq = {s["seq"]: s for s in steps}
    zone = by_seq[4953]["state"]["player"]["zone"]

    class W:
        data = {}
        def objects_in(self, z):
            return [{"name": "chest", "x": 76, "y": 19, "zone": zone}]
    w, c = W(), {"tried": [], "taken": [], "steps": 0}
    for seq in range(4953, 4960):
        st = by_seq[seq]["state"]
        got = [l for l in collect.chest_step(st, c, w, zone, st["player"]["x"], st["player"]["y"]) or []
               if not l.startswith("SAY")]
        want = ["KEY Escape"] if seq == 4959 else [by_seq[seq]["answer"]]
        assert got == want, (seq, got, want)


def swims_for_loot_only_when_safe():
    """The user 2026-11-27: loot in deep water isn't unreachable; swimming is fine when the zone is under
    control. At the swim prompt: with swim_ok the same step goes in; without, the item is marked deep and
    left for later (not written off), and a deep item is skipped until swim_ok."""
    from scripts import collect

    class W:
        data = {"objects": {}}
        def objects_in(self, z):
            return [{"name": "studded leather armor", "x": 37, "y": 6, "zone": z}]
    prompt = "There is a deep pool of brackish sugary water that way. Move northeast again to enter it and start swimming."
    st = {"turn": 10, "wait": "map", "player": {"zone": "z", "x": 36, "y": 7},
          "messages": ["You pass by a watervine.", prompt], "screen": {"rows": []}}
    before = {"msgs": ["You pass by a watervine."]}  # the prompt is new since the last call
    w, mem = W(), {"gear": {"tried": [], "taken": [], "steps": 1, "target": "37,6,studded leather armor",
                            "seen_msgs": dict(before)}}
    lines, why, done = collect.step(st, mem, w, {"swim_ok": True}, mkey="gear", only=collect.GEAR)
    assert "GOTO 37 6" in lines, lines
    w2, mem2 = W(), {"gear": {"tried": [], "taken": [], "steps": 1, "target": "37,6,studded leather armor",
                              "seen_msgs": dict(before)}}
    lines, why, done = collect.step(st, mem2, w2, {"swim_ok": False}, mkey="gear", only=collect.GEAR)
    assert not any(l.startswith("GOTO") for l in lines), lines
    assert "37,6,studded leather armor" in collect.deep(w2, "z")
    assert "37,6,studded leather armor" not in collect.unreachable(w2, "z")  # not written off
    # the same old prompt still in the log next call isn't a new one (2026-11-27: it marked dry loot deep)
    st2 = dict(st, turn=11)
    lines, why, done = collect.step(st2, mem2, w2, {"swim_ok": False}, mkey="gear", only=collect.GEAR)
    assert done and not lines, (lines, done)  # skipped while unsafe
    lines, why, done = collect.step(st2, mem2, w2, {"swim_ok": True}, mkey="gear", only=collect.GEAR)
    assert "GOTO 37 6" in lines, lines  # fetched once it's safe


def swim_safety_reads_the_surroundings():
    """swim_safe: full HP, no fight lately, nothing that moves or shoots in view or known within 15 (one
    seen moving off counts wherever it was); rooted melee kinds don't count."""
    import world
    from scripts import explore

    class W:
        def __init__(self, threats):
            self.t = threats
        def kind(self, name):
            return {"mobile": False} if "glowpad" in name else {"mobile": True}
        def threats(self, zone):
            return self.t
    st = {"turn": 100, "player": {"zone": "z", "x": 10, "y": 10, "hp": 30, "maxhp": 30}, "map": {"objects": []}}
    old = world.CURRENT
    try:
        world.CURRENT = W([])
        assert explore.swim_safe(st, {}, {}) is True
        assert explore.swim_safe(st, {"last_fight_turn": 95}, {}) is False
        assert explore.swim_safe(dict(st, player=dict(st["player"], hp=20)), {}, {}) is False
        world.CURRENT = W([{"name": "wet glowpad", "x": 12, "y": 10, "last_turn": 90}])
        assert explore.swim_safe(st, {}, {}) is True  # rooted, can't come
        world.CURRENT = W([{"name": "snapjaw scavenger", "x": 40, "y": 10, "last_turn": 90}])
        assert explore.swim_safe(st, {}, {}) is True  # 30 away
        world.CURRENT = W([{"name": "snapjaw scavenger", "x": 20, "y": 10, "last_turn": 90}])
        assert explore.swim_safe(st, {}, {}) is False  # 10 away
        world.CURRENT = W([{"name": "snapjaw scavenger", "x": 70, "y": 10, "last_turn": 90, "moved_turn": 95}])
        assert explore.swim_safe(st, {}, {}) is False  # whereabouts unknown
        old_st = dict(st, turn=5000)
        world.CURRENT = W([{"name": "snapjaw scavenger", "x": 70, "y": 10, "last_turn": 90, "moved_turn": 4990}])
        assert explore.swim_safe(old_st, {}, {}) is True  # a sighting thousands of turns old says little now
    finally:
        world.CURRENT = old


def pacing_between_subsystems_hands_over():
    """Siwur 2026-11-27: the fight routine (a glowpad in view from one cell) and the gear walk (from the
    other) took turns, so the steps landed on (36,6) and (37,6) for good. step.py's pacing failsafe sees
    every script's steps; the replayed gear case's real positions must hand over, and a real walk mustn't."""
    import json
    from pathlib import Path
    import step
    case = json.loads((Path(__file__).parent / "fixtures" / "cases" / "gear_giveups_are_not_stuck.json").read_text(encoding="utf-8"))
    mem, why = {}, None
    states = case["states"][6:] * 2  # from (36,6) on, the real back-and-forth with (37,6)
    for i, st in enumerate(states):
        st = dict(st, turn=st["turn"] + i)  # turns pass
        why = step.pacing(mem, st, ["GOTO 37 6" if i % 2 else "GOTO 37 2"], False) or why
    assert why and why.startswith("pacing"), why
    mem = {}
    for i in range(30):  # a real walk east: never on two cells
        st = {"wait": "map", "turn": 100 + i, "player": {"x": 10 + i, "y": 5}}
        assert step.pacing(mem, st, ["GOTO 60 5"], False) is None
    mem = {}
    for i in range(30):  # attacks between steps reset it (step out to heal, step back in)
        st = {"wait": "map", "turn": 100 + i, "player": {"x": 10 + i % 2, "y": 5}}
        assert step.pacing(mem, st, ["GOTO 11 5"] if i % 3 else ["CMD CmdAttackE"], False) is None


def look_card_reads_in_full():
    """Siwur 2026-11-26: menu.py item ... look printed a cut-off line mixed with the inventory behind the
    card. popup_text takes only the card's own lines (a real look card's screen)."""
    import json, sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    import menu
    rows = json.loads((Path(__file__).parent / "fixtures" / "look_card_rows.json").read_text(encoding="utf-8"))
    assert menu.popup_text(rows) == ["small violet tube", "A strange substance fills a channel of glass.",
                                     "Weight: 0 lbs.", "Perfect"], menu.popup_text(rows)


def stained_names_are_one_kind():
    """Siwur 2026-11-27: "salt-encrusted iron long sword" kept its own weapon record beside "iron long
    sword" for the same item; any <x>-stained / -encrusted / -covered / -soaked prefix is a state."""
    import world
    assert world.kind_name("salt-encrusted iron long sword") == "iron long sword"
    assert world.kind_name("sap-and-blood-stained watervine") == "watervine"
    assert world.kind_name("wet snapjaw scavenger") == "snapjaw scavenger"
    assert world.kind_name("two-handed iron long sword") == "two-handed iron long sword"


def stale_sightings_dont_block():
    """Siwur 2026-11-27: snapjaws last seen thousands of turns earlier kept counting as threats near us
    (camping, swimming). A mobile kind's sighting older than THREAT_MEMORY_TURNS is dropped; a rooted
    one's isn't (it's still there)."""
    import world
    from scripts import explore

    class W:
        def __init__(self, t):
            self.t = t
        def kind(self, name):
            return {"mobile": False, "verdict": "fight", "ranged": True} if "vine" in name else {"mobile": True, "verdict": "fight"}
        def threats(self, zone):
            return self.t
    st = {"turn": 5000, "player": {"zone": "z", "x": 10, "y": 10}}
    old = world.CURRENT
    try:
        world.CURRENT = W([{"name": "snapjaw scavenger", "x": 12, "y": 10, "last_turn": 1000}])
        assert explore.known_threats(st, 15) == []
        world.CURRENT = W([{"name": "snapjaw scavenger", "x": 12, "y": 10, "last_turn": 4800}])
        assert len(explore.known_threats(st, 15)) == 1
        world.CURRENT = W([{"name": "seed-spitting vine", "x": 12, "y": 10, "last_turn": 1000}])
        assert len(explore.known_threats(st, 15)) == 1  # rooted: still where it was
    finally:
        world.CURRENT = old


CHECKS = [(f.__name__, f) for f in (proficiency_counts_in_to_hit, weapon_records_are_per_character,
                                     missile_weapon_fills_empty_slot, new_liquids_and_features_are_listed,
                                     sword_estimate_not_zero, torch_miss_is_not_the_weapons,
                                     thrown_hit_parses_and_is_ranged, rest_when_only_rooted_far,
                                     owned_item_is_declined, popup_never_gets_a_bare_pass,
                                     rewritten_plan_is_new, flying_prey_is_not_hunted,
                                     charge_only_from_three_cells, feature_kinds_are_world_neutral,
                                     chests_are_opened_like_by_hand, chest_menu_is_not_an_item_menu,
                                     swims_for_loot_only_when_safe, swim_safety_reads_the_surroundings,
                                     look_card_reads_in_full, stained_names_are_one_kind, stale_sightings_dont_block,
                                     pacing_between_subsystems_hands_over)]
