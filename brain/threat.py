"""Live threat estimate (the user, 2026-11-24: all evaluations dynamic; a verdict from another character,
level or gear is not evidence). Compares how many turns we'd need to kill a creature with how many it
(and whoever else can reach us) would need to kill us, from:

  - the creature's live stats in the snapshot (hp, av, dv; mod v0.20),
  - our live stats: HP, AV and DV from the sidebar, the melee weapon's PV and damage dice,
  - what that kind has done to us so far (game knowledge, per kind "obs"): damage per attack, the hit
    multiplier "(xN)", attacks per turn, and our AV when it was seen.

Game rules used, read from the game's code (XRL.Rules.Stat.RollDamagePenetrations, Combat.
MeleeAttackWithWeaponInternal, MeleeWeapon.GetSimplifiedStats; 2026-11-24): each penetration check is a
triplet of 1d10-2 rolls (a roll of 8 rerolls and adds) plus min(bonus, cap), each compared with the
defender's combat AV; one success is one penetration, all three succeeding is another triplet with the
bonus 2 lower (the cap stays). The bonus is the weapon's PenBonus + the attacker's Strength modifier, the
cap its PenBonus + MaxStrengthBonus. **The displayed PV ("→5") is that capped bonus + 4**
(RuleSettings.VISUAL_PENETRATION_BONUS, display only), so the roll uses displayed - 4. To hit: 1d20 +
bonus must beat DV. Enemies' weapons aren't visible: their effective PV is solved from what they did to us
(mean multiplier at our AV then) and the same formula gives their multiplier at our AV now.
"""
import json, re
from functools import lru_cache

VISUAL_PV = 4            # RuleSettings.VISUAL_PENETRATION_BONUS: shown in the PV, not rolled
DICE = re.compile(r"(\d+)d(\d+)([+-]\d+)?")
WEAPON = re.compile(r"\x1a(\d+)\s*\x03(\d+d\d+(?:[+-]\d+)?)")   # "→5 ♥1d2" in the equipped list
SIDEBAR = re.compile(r"AV:\s*(\d+)\s+DV:\s*(-?\d+)")
AGILITY = re.compile(r"AG:\s*(\d+)")

# Parts that mean "more than its melee" (mod v0.23 exports a creature's part names): explosions, things
# spawned on death, breath, spit, thrown stones... (2026-11-24: an exploding tumbling pod).
SPECIAL_PART = re.compile(r"(OnDeath|Explo|Detonat|Burst|Discharge|Split|Spawn|Acid|Spore|Poison|Gas|Breath|Spit|Throw|Missile|Ranged|Reflect|Thorn|Stinger)", re.I)
HARSH = ("Tough", "Very Tough", "Impossible")
MIN_ATTACKS = 3          # fewer observed attacks than this: no estimate from observations
RESERVE = 0.25           # count only HP above a quarter of max as ours to spend
MARGIN = 0.75            # engage when we kill it in at most 75% of the turns it needs to kill us (0.6 flagged winnable fights: a snapjaw hunter 2 vs 4, a cave spider 4 vs 7)


def dice_avg(d):
    m = DICE.search(d or "")
    if not m:
        return 0.0
    n, s, k = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    return n * (s + 1) / 2 + k


@lru_cache(maxsize=None)
def singlet_beats(pv, av, depth=0):
    """P(one exploding 1d10-2 roll + pv > av)."""
    p = 0.0
    for face in range(1, 11):
        v = face - 2
        if v == 8 and depth < 3:  # max: reroll and add
            p += 0.1 * singlet_beats(pv + 8, av, depth + 1)
        else:
            p += 0.1 * (1.0 if v + pv > av else 0.0)
    return p


def expected_penetrations(pv, av):
    e, reach, k = 0.0, 1.0, 0
    while reach > 1e-4 and k < 10:
        p = singlet_beats(pv - 2 * k, av)
        e += reach * (1 - (1 - p) ** 3)
        reach *= p ** 3
        k += 1
    return e


def our_stats(state):
    rows = " ".join((state.get("screen") or {}).get("rows") or [])
    m, a = SIDEBAR.search(rows), AGILITY.search(rows)
    p = state.get("player") or {}
    weapon = None
    ids = state.get("equipped_ids") or []
    for i, e in enumerate(state.get("equipped") or []):
        w = WEAPON.search(e)
        if w and "[" not in e:  # "[lead slug]": a missile weapon
            from world import kind_name  # strips "bloody slimy" etc., as for creature kinds
            name = kind_name(e.split("\x1a")[0].strip())
            iid = ids[i] if i < len(ids) and ids[i] not in (None, "null") else None
            # Records are this character's (world.json, not shared game knowledge) and per item when the
            # mod gives ids (v0.27): the user, 2026-11-26, swings were pooled by name across characters.
            weapon = {"name": name, "pv": int(w.group(1)), "dice": w.group(2), "id": iid,
                      "key": f"{name}#{iid}" if iid else name}
            break
    # The sidebar shows combat AV/DV; the snapshot's raw DV stat is only the gear adjustment (2026-11-24:
    # raw -1, sidebar 6 = 6 + Agility mod 1 + raw -1).
    ag_mod = (int(a.group(1)) - 16) // 2 if a else 0
    av = int(m.group(1)) if m else p.get("av")
    dv = int(m.group(2)) if m else (combat_dv(p.get("dv"), ag_mod) if p.get("dv") is not None else None)
    skills = []
    try:
        import world as _w
        prof = _w.RUNS / _w.run_id(state) / "profile.json"
        pj = json.loads(prof.read_text(encoding="utf-8"))
        skills = (pj.get("current") or pj).get("skills") or []
    except Exception:
        pass
    return {"hp": p.get("hp") or 0, "maxhp": p.get("maxhp") or 1, "av": av, "dv": dv, "skills": skills,
            "ag_mod": (int(a.group(1)) - 16) // 2 if a else 0, "weapon": weapon}


def combat_dv(raw, agi_mod):
    """Combat DV from the raw DV stat (mod v0.20+): a base of 6 plus the Agility modifier plus the raw
    stat, which matches the player's sidebar (6 = 6 + 1 + -1)."""
    return 6 + (agi_mod or 0) + (raw or 0)


def target_dv(c):
    """A creature's combat DV: with mod v0.22's agi field the raw stat is corrected, else taken as is."""
    if c.get("agi") is not None:
        return combat_dv(c.get("dv"), c["agi"])
    return c.get("dv") or 0


def hit_chance(bonus, dv):
    """P(1d20 + bonus > dv)."""
    return max(0.05, min(0.95, sum(1 for r in range(1, 21) if r + bonus > dv) / 20))


PRIOR_SWINGS = 10  # the computed hit chance counts as this many swings against the observed record


def skill_bonus(us, weapon_name):
    """To-hit bonus from a weapon-class proficiency the character has (the profile's skill list):
    Axe Proficiency / Cudgel Proficiency give +2 with that class (wiki; skills_level2.md)."""
    skills = us.get("skills") or []
    n = weapon_name or ""
    classes = {"Axe Proficiency": ("axe",), "Cudgel Proficiency": ("cudgel", "mace", "club", "hammer", "staff")}
    return sum(2 for sk, words in classes.items() if sk in skills and any(w in n for w in words))


def to_hit_bonus(us, record):
    """Our to-hit bonus with this weapon, from the game's own numbers: each of our attack messages shows
    the roll with every bonus in it ("[17]", "[2 vs 10]"), so the mean roll minus 10.5 is the bonus. Few
    rolls on record: blended with Agility + proficiency, which counts as PRIOR_SWINGS rolls (2026-11-26:
    the estimate didn't know Axe Proficiency's +2 and mixed other characters' records)."""
    prior = us["ag_mod"] + skill_bonus(us, (us.get("weapon") or {}).get("name"))
    n = (record or {}).get("roll_n", 0)
    seen = (record or {}).get("rolls", 0) - 10.5 * n
    return (seen + PRIOR_SWINGS * prior) / (n + PRIOR_SWINGS)


def our_dpt(us, target, weapons=None):
    """Our expected melee damage per turn against target: hit chance x expected penetrations (exact rule,
    displayed PV - 4 against the target's AV) x the damage dice. The hit chance comes from our to-hit
    bonus with this weapon (to_hit_bonus: the game's rolls, else Agility + proficiency) against the
    target's DV."""
    w = us["weapon"]
    if not w or target.get("av") is None:
        return None
    o = (weapons or {}).get(w.get("key") or w["name"]) or {}
    hit = hit_chance(to_hit_bonus(us, o), target_dv(target))
    return hit * expected_penetrations(w["pv"] - VISUAL_PV, target["av"]) * dice_avg(w["dice"])


def solve_pv(mult, av):
    """The penetration bonus whose expected multiplier against av is mult (for enemies, from what they did)."""
    lo, hi = -10.0, 30.0
    if mult <= expected_penetrations(-10, av):
        return lo
    for _ in range(40):
        mid = (lo + hi) / 2
        if expected_penetrations(round(mid), av) < mult:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def mult_at(pv, av):
    """Expected multiplier for a fractional bonus: interpolate between the whole numbers."""
    a = int(pv // 1)
    f = pv - a
    return (1 - f) * expected_penetrations(a, av) + f * expected_penetrations(a + 1, av)


def attacks_dpt(creature, us):
    """Expected damage per turn from a creature's own attacks (mod v0.22: "attacks" with damage dice,
    penetration bonus, strength cap and hit bonus, plus its Strength and Agility modifiers), by the same
    rules as ours, against our AV and DV now. Its best attack counts fully, the others a third each (extra
    limbs don't all land every turn: an assumption, not read from the game). None without the data."""
    atk = creature.get("attacks") or []
    if not atk or us.get("av") is None:
        return None
    s, a = creature.get("str", 0) or 0, creature.get("agi", 0) or 0
    each = []
    for w in atk:
        bonus = (w.get("pen") or 0) + min(s, w.get("cap") if w.get("cap") is not None else s)
        hit = hit_chance(a + (w.get("hit") or 0), us.get("dv") or 0)
        each.append(hit * expected_penetrations(bonus, us["av"]) * dice_avg(w.get("dmg")))
    each.sort(reverse=True)
    return each[0] + sum(each[1:]) / 3


def their_dpt(kind, us, creature=None):
    """Expected damage per turn this creature does to us now: from what its kind did before when there
    are MIN_ATTACKS observations, else from its own attacks (attacks_dpt); None without either."""
    o = (kind or {}).get("obs") or {}
    if o.get("attacks", 0) < MIN_ATTACKS:
        return attacks_dpt(creature, us) if creature else None
    hits = o.get("hits", 0)
    if hits == 0:
        return 0.0
    per_pen = o["dmg"] / o["mult"]                    # damage per multiplier step
    mult_seen = o["mult"] / hits
    av_seen = round(o["av"] / o["av_n"]) if o.get("av_n") else (us["av"] or 0)
    mult_now = mult_at(solve_pv(mult_seen, av_seen), us["av"] or 0)
    hit_rate = hits / o["attacks"]
    per_turn = o["attacks"] / max(1, o.get("turns", 1))
    return per_pen * mult_now * hit_rate * per_turn


def estimate(state, world, target, others=()):
    """{"ours", "theirs", "ttk_them", "ttk_us", "ok", "why"}; ok is None when there isn't enough data."""
    us = our_stats(state)
    mine = our_dpt(us, target, world.data.get("weapons"))
    theirs, missing = 0.0, []
    for o in [target, *others]:
        d = their_dpt(world.kind(o["name"]), us, o)
        if d is None:
            missing.append(o["name"])
        else:
            theirs += d
    out = {"ours": mine, "theirs": theirs}
    if mine is None or missing:
        out.update(ok=None, why="no data for " + (", ".join(missing) if missing else "our weapon or its AV"))
        return out
    spend = max(1.0, us["hp"] - RESERVE * us["maxhp"])
    hp = target.get("hp") or 1
    # A loaded missile weapon gets one shot in before contact when the target isn't adjacent yet (the
    # musket killed an amoeba outright at level 5). Accuracy isn't modelled: half the shots count.
    p = state.get("player") or {}
    if max(abs(target.get("x", 0) - p.get("x", 0)), abs(target.get("y", 0) - p.get("y", 0))) >= 2:
        for e in state.get("equipped") or []:
            m = WEAPON.search(e)
            if m and "[" in e and "[empty]" not in e and target.get("av") is not None:
                shot = 0.5 * expected_penetrations(int(m.group(1)) - VISUAL_PV, target["av"]) * dice_avg(m.group(2))
                hp = max(0.5, hp - shot)
                out["opening"] = round(shot, 1)
                break
    out["ttk_them"] = hp / max(mine, 0.05)
    out["ttk_us"] = spend / theirs if theirs > 0 else float("inf")
    out["ok"] = out["ttk_them"] <= MARGIN * out["ttk_us"]
    diff = re.sub(r"\{\{\w\||\}\}|&\w", "", target.get("diff") or "").strip()
    out["diff"] = diff
    out["flags"] = [n for n in (target.get("parts") or []) if SPECIAL_PART.search(n)]
    out["why"] = (f"[{diff}] " if diff else "") + (f"I need about {out['ttk_them']:.0f} turns to kill it ({mine:.1f} a turn against {target.get('hp')} HP); "
                  + (f"it needs about {out['ttk_us']:.0f} to bring me down ({theirs:.1f} a turn)" if theirs > 0 else "it can't hurt me"))
    return out


# ---- observations: what each kind did to us (game knowledge) ----

ATTACK = re.compile(r"^The (.+?) (?:(critically )?hits (?:you )?\((x)(\d+)\) (?:with .+? )?for (\d+) damage|misses you|doesn't penetrate your armor)")


OURS = re.compile(r"^You (?:(critically )?hit \((x)(\d+)\) for (\d+) damage with your (.+?)[!.]|miss(?: with your (.+?)[!.])?)")


def observe(world, messages, state, target=None):
    """Add this call's attacks to game knowledge. Enemy attacks go to each kind's obs: attacks, hits, dmg,
    mult (sum of xN), av (sum of our AV at each hit), turns (distinct turns with an attack). Our melee
    swings go to weapons[name]: hits, misses, dmg, mult, av (sum of the target's AV). target: the creature
    we're swinging at (for its AV); without it our swings aren't recorded."""
    us = our_stats(state)
    turn = state.get("turn") or 0
    weapon = (us["weapon"] or {}).get("key") or (us["weapon"] or {}).get("name")
    weapon_name = (us["weapon"] or {}).get("name")
    if target is not None and weapon:
        ws = world.data.setdefault("weapons", {})
        for m in messages:
            a = OURS.match(m)
            if not a or " the " in m.split(" for ")[0]:  # "You hit the X (x1) with a lead slug": a shot
                continue
            o = ws.setdefault(weapon, {"hits": 0, "misses": 0, "dmg": 0, "mult": 0, "av": 0, "av_n": 0})
            roll = re.search(r"\[(\d+)(?: vs \d+)?\]\s*$", m)
            if a.group(2):
                from world import kind_name
                if a.group(5) and kind_name(a.group(5).strip()) != weapon_name:
                    continue  # the offhand (a torch) or another weapon
                o["hits"] += 1
                if roll:
                    o["rolls"] = o.get("rolls", 0) + int(roll.group(1))
                    o["roll_n"] = o.get("roll_n", 0) + 1
                o["mult"] += int(a.group(3))
                o["dmg"] += int(a.group(4))
                if target.get("av") is not None:
                    o["av"] += target["av"]
                    o["av_n"] += 1
            else:
                # A miss with the off hand (the torch) isn't the weapon's (2026-11-26: torch misses and
                # three fight-routine misses made the long sword read 0% to hit).
                from world import kind_name
                if a.group(6) and kind_name(a.group(6).strip()) != weapon_name:
                    continue
                o["misses"] += 1
                if roll:
                    o["rolls"] = o.get("rolls", 0) + int(roll.group(1))
                    o["roll_n"] = o.get("roll_n", 0) + 1
    for m in messages:
        a = ATTACK.match(m)
        if not a:
            continue
        k = world.set_kind(a.group(1))
        o = k.setdefault("obs", {"attacks": 0, "hits": 0, "dmg": 0, "mult": 0, "av": 0, "av_n": 0, "turns": 0, "last_turn": -1})
        o["attacks"] += 1
        if a.group(3):
            o["hits"] += 1
            o["mult"] += int(a.group(4))
            o["dmg"] += int(a.group(5))
            if us["av"] is not None:
                o["av"] += us["av"]
                o["av_n"] += 1
        if o.get("last_turn") != turn:
            o["turns"] += 1
            o["last_turn"] = turn


# ---- speed: can we keep away from it? ----

MS_SIDEBAR = re.compile(r"MS:\s*(\d+)")


def move_rate(qn, ms_raw, inverted):
    """Relative cells per unit time: quickness times movement (the raw MoveSpeed stat is a cost when the
    sidebar shows 200 - raw, i.e. lower raw = faster)."""
    if not qn:
        return None
    move = (200 - ms_raw) if inverted else ms_raw
    return qn * max(move, 1) / 100.0


def kiteable(state, target, margin=0.85):
    """True when the creature moves clearly slower than we do (so ray-and-step-back works), False when it
    doesn't, None when the snapshot lacks speeds (mod before v0.21)."""
    p = state.get("player") or {}
    if p.get("qn") is None or target.get("qn") is None:
        return None
    rows = " ".join((state.get("screen") or {}).get("rows") or [])
    shown = MS_SIDEBAR.search(rows)
    inverted = bool(shown and int(shown.group(1)) + (p.get("ms") or 0) == 200)
    ours, theirs = move_rate(p["qn"], p.get("ms") or 100, inverted), move_rate(target["qn"], target.get("ms") or 100, inverted)
    if not ours or not theirs:
        return None
    return theirs < margin * ours


# ---- gear comparison (the early gear grab, 2026-11-24) ----

ARMOUR = re.compile(r"\x04(-?\d+)\s*\t(-?\d+)")   # "♦2 ○-1" in inventory/equipped strings


def weapon_score(entry, ag_mod=0, av=3, dv=4):
    """Expected melee damage per turn of an inventory or equipped entry ("iron long sword →6 ♥1d4")
    against a typical target (AV 3, DV 4), by the game's penetration rule; None if it isn't a melee
    weapon. Skill bonuses to hit (axe proficiency...) aren't counted."""
    m = WEAPON.search(entry or "")
    if not m or "[" in entry:
        return None
    return hit_chance(ag_mod, dv) * expected_penetrations(int(m.group(1)) - VISUAL_PV, av) * dice_avg(m.group(2))


def gear_verdict(state, name):
    """After picking up `name`: a sentence for the LLM if it's worth acting on (a better weapon, or any
    armour to examine), else None."""
    from world import kind_name
    want = kind_name(name)
    entry = next((e for e in state.get("inventory") or [] if kind_name(e.split("\x1a")[0].split("\x04")[0].strip()).startswith(want)), None)
    if entry is None:
        return None
    us = our_stats(state)
    # A missile weapon ("short bow \x1a4 [empty]") when none is equipped fills an empty slot: a ranged option
    # we didn't have (2026-11-26: a bow and arrows from the first fight were never considered).
    if "[" in entry and "\x1a" in entry and not any("[" in e and "\x1a" in e for e in state.get("equipped") or []):
        ammo = [e.split("\x1a")[0].strip() for e in state.get("inventory") or []
                if re.search(r"arrow|bolt|slug|shot|bullet|dart", e) and e != entry]
        return (f"missile weapon: {want} fills the empty missile slot (ammo in the pack: {', '.join(ammo) or 'none'}); "
                "equip it if there's ammo for it")
    new = weapon_score(entry, us["ag_mod"])
    if new is not None:
        held = max([s for s in (weapon_score(e, us["ag_mod"]) for e in state.get("equipped") or []) if s is not None] or [0.0])
        torch = any("torch" in e for e in state.get("equipped") or [])
        if "two-handed" in want and torch:
            # It takes the torch's hand: in dark caves we went from 38 visible cells to 9 (2026-11-24).
            return None
        if new > 1.1 * held:
            return f"upgrade: {want} does about {new:.1f} a turn against AV 3, my current weapon {held:.1f}; equip it"
        return None
    a = ARMOUR.search(entry)
    # Shields give AV only on a successful block (~25% without the Block skill) and their DV penalty always
    # applies (learned 2026-11-24): not worth wearing; keep to sell.
    if a and re.search(r"buckler|shield", want):
        return None
    if a:
        # The same piece already worn, or the same AV/DV as something worn: nothing to decide (2026-11-25:
        # a second leather cap, a leather apron and a second leather armour each handed over for nothing).
        worn = [(kind_name(e.split("\x04")[0].strip()), ARMOUR.search(e)) for e in state.get("equipped") or []]
        if int(a.group(1)) <= 0 and int(a.group(2)) <= 0:
            return None  # gives nothing (sandals AV 0 DV 0, 2026-11-25)
        body = re.compile(r"armou?r|apron|robe|mail|coat|jerkin|tunic|vest|cuirass|plate")
        if any(n == want or (m and (int(m.group(1)), int(m.group(2))) >= (int(a.group(1)), int(a.group(2)))
                             and body.search(want) and body.search(n))
               for n, m in worn):
            return None
        return f"armour: {want} (AV {a.group(1)}, DV {a.group(2)}); examine it and wear it if it fills an empty slot or beats what's worn"
    return None
