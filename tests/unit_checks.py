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


CHECKS = [(f.__name__, f) for f in (proficiency_counts_in_to_hit, weapon_records_are_per_character,
                                     missile_weapon_fills_empty_slot, new_liquids_and_features_are_listed,
                                     sword_estimate_not_zero, torch_miss_is_not_the_weapons,
                                     thrown_hit_parses_and_is_ranged, rest_when_only_rooted_far,
                                     owned_item_is_declined, popup_never_gets_a_bare_pass,
                                     rewritten_plan_is_new, flying_prey_is_not_hunted,
                                     charge_only_from_three_cells)]
