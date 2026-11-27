"""Fight routine: the bulk of melee fights, handing anything unusual to the LLM ("raising the agent").

Called by explore (args.fight) whenever a hostile is in view, or a fight is still in progress.
engage() returns (lines, raise_reason): one action to play, or a reason to stop and hand over.

It fights only kinds the run's world file gives the verdict "fight" (set by the LLM after a Look;
tools/world.py kind ...). It raises for:
  new enemy    a hostile kind with no verdict yet (the LLM looks at it and decides)
  not fight    a kind with verdict "avoid" or "ask"
  outnumbered  more than args.max_hostiles hostiles in view
  hurt         HP under args.raise_hp_fraction of max
  unexpected   a message during the fight that is neither ordinary combat text nor a known effect of
               the kinds in view (a new ability, a status, something odd)
  long fight   more than args.max_fight_turns turns since the fight started
  hurt before engaging   a new target that doesn't move while HP is under args.engage_hp_fraction
               (or the kind's own engage_hp_fraction, for kinds that hit hard):
               it can't follow, so resting first is better (the LLM steps out of sight and rests)

Outcomes go into the world file: kills and XP per kind, and the largest single hit each kind dealt.
Nothing here names a particular creature: it works from the world file, so it suits any run.

args (on the explore stage): {"fight": true, "raise_hp_fraction": 0.5, "engage_hp_fraction": 0.7,
                              "max_fight_turns": 20, "max_hostiles": 2}
"""
import json, re
from pathlib import Path

from world import kind_name
from scripts import ability
import threat

# Ordinary text during fights and exploring, in any run (the game's own wording).
ORDINARY = [re.compile(p) for p in (
    r"^You (critically )?hit \(x\d+\) for \d+ damage",
    r"^There doesn't seem to be anywhere else to explore",  # autoexplore's zone-done note, mid-hunt (2026-11-25)
    r"^You are famished!",  # the hunger warning; explore eats at once (2026-11-25)
    r"^You make camp",  # our own camp meal between bouts (2026-11-25)
    r"^You toss .+ into a pot",
    r"^You extinguish the campfire",
    r"(stops|starts|begins) leaking",  # a wounded plant bleeding sap (2026-11-25)
    r"takes \d+ damage from (leaking|bleeding|your freezing effect)",
    r"^You (begin|stop) bleeding",  # bleeding is ordinary in a bite fight; HP checks still apply (2026-11-25)
    r"^You take (no|\d+) damage from bleeding",
    r"^One of your wounds stops bleeding",  # with several wounds, each heals on its own (2026-11-25)
    r"^You are (no longer )?dazed",  # explore's bad-effect handling waits it out (2026-11-25)
    r"^You have lost sight of ",  # a target out of view for a moment (2026-11-25)
    r"^You eat ",  # our own meal or snack mid-fight (2026-11-25: "You eat your bear jerky." stopped a fight)
    r"^You (critically )?hit the .+ \(x\d+\) with .+ for \d+ damage",  # missile hits ("with a lead slug")
    r"^You reload your .+ with ",
    r"^Your shot goes wild!",
    r"^The .+?('s carapace loosens| tightens (his|her|its|their) carapace)\.",  # tracked in fight states
    r"^You hit something to the ",  # a shot that hit something unseen
    r"^Your .+ fails to penetrate the .+'s armor!",
    r"^You chop off the .+'s .+!$",  # axe dismemberment on our hits
    r"^You cleave through the .+'s armor\.$",  # the axe's critical cleave (target AV down)
    r"^The .+ begins (bleeding|leaking)!$",  # plants leak instead of bleeding
    r"^The .+ takes \d+ damage from (bleeding|leaking)\.$",
    r"^The .+ (is|remains) (dazed|stunned|frozen|confused)[.!]$",  # effects on them (2026-11-27: "The glowpad is stunned!" stopped explore twice)
    r"^You gather whatever you can find for your meal",  # the camp meal's own text (2026-11-27: handed over as unexpected)
    r"^Your genome enters an excited state",  # the level-5 rapid mutation (its choice popup follows)
    r"^You (begin|stop) bleeding[.!]$",  # our own bleeding (cave spider bites); HP checks still apply
    r"^You take (no|\d+) damage from bleeding\.$",
    r"^You miss",
    r"^You don't penetrate",
    r"^The .+ ((critically )?hits \(x\d+\) for \d+ damage|misses you|doesn't penetrate your armor)",
    r"^Your .+ (was|were) cracked\.$",  # armour damaged by a crit (AV drops)
    r"^You take the .+ from the ",  # autoexplore picking up loot mid-fight
    r"^You take (the |an? )?.+[.!]$",  # a plain pickup ("You take the wooden arrow x5.")
    r"^The .+ hits you \(x\d+\) with .+ for \d+ damage",  # ranged hits ("with a seed")
    r"^The .+ dies!$",
    r"^You gain \d+ XP!",
    r"^You pass by ",
    r"^The .+ (begins|stops) flying\.$",  # dragonflies and the like taking off or landing
    r"^The .+ (swoops down to attack|falls to the ground)\.$",  # a flier landing to bite (2026-11-26): it's hittable now
    r"^You wade ",
    r"^You swim ",
    r"^The .+ is stuck in a frozen ",  # the ray froze the pool it stands in
    r"^You see .+ and stop exploring\.",
    r"^You flinch away as .+ whizzes past",
    r"^You pour fresh water from your waterskin over yourself\.",
    r"^The way is blocked by ",
    r"^You have gained a level",
    r"^You gain \d+ (hitpoints|Skill Points|Mutation Point)",
    r"^Bot",
)]

KILL = re.compile(r"^The (.+) dies!$")
XP = re.compile(r"^You gain (\d+) XP!")
HIT = re.compile(r"^The (.+?) (?:critically )?hits (?:you )?(?:with an? .+? (?=\(x))?\(x\d+\) (?:with .+ )?for (\d+) damage")
DIRS = {(0, -1): "N", (1, -1): "NE", (1, 0): "E", (1, 1): "SE", (0, 1): "S", (-1, 1): "SW", (-1, 0): "W", (-1, -1): "NW"}


def new_messages(state, memory):
    """Messages that appeared since the previous call (the snapshot keeps the last 15)."""
    msgs = list(state.get("messages") or [])
    prev = memory.get("msgs")
    memory["msgs"] = msgs
    if prev is None:
        return []
    for n in range(min(len(prev), len(msgs)), 0, -1):
        if prev[-n:] == msgs[:n]:
            return msgs[n:]
    return msgs


def is_prey(o, world):
    """A non-hostile creature we may attack anyway: its kind is marked prey in the world file (the LLM
    judged it harmless and unimportant: not a named NPC, quest giver or faction member; user,
    2026-11-24). Names starting with a capital are people, never prey."""
    if not o.get("creature") or o.get("hostile") or world is None:
        return False
    name = o.get("name") or ""
    k = world.kind(name)
    # One with an allegiance in its name ("glowfish and friend to fungi") may cost reputation with that
    # faction: not prey until the LLM decides otherwise (2026-11-25).
    if " and friend to " in name or " and member of " in name:
        return False
    # Flying prey can't be hit from the ground: CmdAttack at a flying giant dragonfly did nothing, 40 times
    # (2026-11-25). It's prey again once it lands.
    if "flying" in (o.get("effects") or []):
        return False
    return bool(k and k.get("prey")) and not name[:1].isupper()


def hostiles_in_view(state, world=None, hunt=False):
    """Creatures to fight, nearest first: hostiles, plus prey when hunting (args.hunt)."""
    p = state.get("player") or {}
    px, py = p.get("x", 0), p.get("y", 0)
    found = [o for o in (state.get("map") or {}).get("objects", [])
             if o.get("creature") and (o.get("hostile") or (hunt and is_prey(o, world)))
             and (o["x"], o["y"]) != (px, py)  # one listed on our own cell can't be attacked (2026-11-24: a loop)
             and not (world is not None and (world.kind(o["name"]) or {}).get("verdict") == "ignore")]
    return sorted(found, key=lambda o: max(abs(o["x"] - px), abs(o["y"] - py))), px, py


def record(new, world, state=None):
    """Kills, XP and hardest hits from this call's new messages. A kill also marks that creature
    dead in the world file, so it stops counting as a threat in its zone."""
    last_kill = None
    zone_id = ((state or {}).get("player") or {}).get("zone")
    for m in new:
        k = KILL.match(m)
        if k:
            if zone_id:
                world.mark_dead(k.group(1), zone_id, (state or {}).get("turn", 0))
            last_kill = world.set_kind(k.group(1))
            last_kill["kills"] = last_kill.get("kills", 0) + 1  # game knowledge: every character's kills
            # This character's own tally lives in the run's file (the user, 2026-11-25: a global count in
            # the log means nothing for this character).
            mine = world.data.setdefault("run", {}).setdefault("kills", {})
            kn = W_kind(k.group(1))
            mine[kn] = mine.get(kn, 0) + 1
            continue
        x = XP.match(m)
        if x and last_kill is not None:
            last_kill.setdefault("xp", []).append(int(x.group(1)))
            last_kill = None
            continue
        h = HIT.match(m)
        if h:
            kind = world.set_kind(h.group(1))
            kind["max_hit"] = max(kind.get("max_hit", 0), int(h.group(2)))
            # "hits you (x2) with a seed" is a missile; melee reads "hits (x1) for 3 damage with their bite":
            # learn that the kind shoots (the tactic then closes in instead of waiting, 2026-11-25).
            if " hits you (x" in m and ") with " in m:
                kind["ranged"] = True
            # A thrown one reads "The hulking baboon hits with a small boulder (x5) for 9 damage!" (2026-11-26).
            if re.search(r" hits with an? .+ \(x\d+\) for \d+ damage", m):
                kind["ranged"] = True


COOLDOWN = {"Freezing Ray": 20, "Charge": 15, "Teleport": 100, "Dismember": 30, "Sprint": 100}


def cooldowns(world):
    """Turn at which each ability is ready again. Kept in the run's world file, not stage memory, so a
    plan change doesn't forget them (it did: the ray was tried 7 turns after use, 2026-11-24). The
    abilities list corrects any guess: it shows "[N turn cooldown]" while one is cooling down."""
    return world.data.setdefault("cooldowns", {})


# What a shot hit: "You (critically) hit the shale (x1) with a lead slug..." / "Your lead slug fails to
# penetrate the shale's armor!"
SHOT = re.compile(r"^(?:You (?:critically )?hit the (.+?) \(x\d+\) with |Your .+ fails to penetrate the (.+?)'s armor)")


CARAPACE = re.compile(r"^The (.+?)(?:'s carapace (loosens)| (tightens) (?:his|her|its|their) carapace)")
NOPEN = re.compile(r"^(?:You don't penetrate the (.+?)'s armor|Your .+ fails to penetrate the (.+?)'s armor)")
PENHIT = re.compile(r"^You (?:critically )?hit (?:the .+? )?\(x\d+\)")


HANDOVERS = Path(__file__).resolve().parents[2] / "live" / "fight_handovers.jsonl"


def handover(state, reason, fight=None, est=None):
    """A fight hand-over to the LLM: logged with the situation, so the thresholds can be honed from what
    happened next (the user, 2026-11-25: the trade-off between taking turns by hand and handing back to
    scripts needs honing). Returns the reason, for the caller's STOP."""
    p = state.get("player") or {}
    try:
        with HANDOVERS.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"turn": state.get("turn"), "game": (state.get("game") or {}).get("id"),
                                "player": p.get("name"), "level": p.get("level"), "hp": p.get("hp"), "maxhp": p.get("maxhp"),
                                "reason": reason, "est": {k: v for k, v in (est or {}).items() if k in ("ours", "theirs", "ttk_them", "ttk_us", "ok")},
                                "fight_turns": (state.get("turn") or 0) - ((fight or {}).get("start_turn") or state.get("turn") or 0)}) + "\n")
    except Exception:
        pass
    return reason


def heal(fight, state, world, hostiles):
    """The command for healing while we wait: the game's rest (CmdWaitUntilHealed, one call for the whole
    wait) when every hostile in view is rooted melee and 2+ cells off, else one turn (CmdWait).
    The user, 2026-11-26: we waited out 50 turns one call each in sight of a glowpad 13 cells off in its
    pool. If the game won't rest (the turn hasn't moved on since our last try), fall back to CmdWait for
    the rest of this fight."""
    p = state.get("player") or {}
    px, py, turn = p.get("x", 0), p.get("y", 0), state.get("turn")
    if fight.get("rest_tried") is not None and fight.get("rest_tried") == turn:
        fight["rest_refused"] = True
    if fight.get("rest_refused"):
        return "CMD CmdWait"
    # Every hostile in view, not only the ones the fight is weighing (which drops far ones).
    for o in [o for o in (state.get("map") or {}).get("objects", []) if o.get("creature") and o.get("hostile")] or hostiles:
        k = world.kind(o["name"]) or {}
        if k.get("mobile") is not False or k.get("ranged") or max(abs(o["x"] - px), abs(o["y"] - py)) < 2:
            return "CMD CmdWait"
    fight["rest_tried"] = turn
    return "CMD CmdWaitUntilHealed"


def tactic(kind):
    """How to fight a kind, by how it reaches us (the user, 2026-11-25: treat ranged and melee enemies
    differently; waiting for a seed-spitting vine to "come" let it shoot us 18 -> 8):
      hold    mobile melee: let it come to a spot we chose (it reaches us anyway, and we strike first)
      close   anything ranged: waiting only gives it free shots; close in (the ray first if it's ready)
      siege   rooted melee: it can't reach us unless we stand next to it; hit, step out to heal, return
    Unknown mobility counts as mobile, unknown range as melee (observed ranged hits set it)."""
    k = kind or {}
    if k.get("ranged"):
        return "close"
    if k.get("mobile") is False:
        return "siege"
    return "hold"


def W_kind(name):
    import world as W
    return W.kind_name(name or "")


# Equipped missile weapons show their ammo in brackets: "musket →8 ♥1d8 [lead slug]" / "[empty]".
LOADED = re.compile(r"\x1a\d+.*\[(?!empty\])[^\]]+\]\s*$")
EMPTY = re.compile(r"\x1a\d+.*\[empty\]\s*$")


def continue_fire(state, memory):
    """After CMD CmdFire: in the missile picker (locked on the nearest hostile), Space fires. Returns
    (lines, raise_reason); ([], None) when the picker didn't open (out of range, nothing to shoot)."""
    fight = memory.setdefault("fight", {})
    fight.pop("firing", None)
    rows = (state.get("screen") or {}).get("rows", [])
    if state.get("wait") == "picker":
        if "Space-select" in " ".join(rows[:2]):
            return ["KEY Space"], None
        return ["KEY Escape"], "missile picker without a target: " + " ".join(rows[:1]).strip()[:80]
    return [], None


def continue_ability(state, memory, world):
    """An ability use in progress (screens open): next key, or done. Returns (lines, raise_reason)."""
    fight = memory.setdefault("fight", {})
    name = fight.get("using")
    lines, why, done = ability.step(state, fight, name)
    if done:
        fight.pop("using", None)
        failed = fight.pop("ability_failed", None)
        if failed:
            fight.setdefault("no_shot", {})[W_kind(fight.get("ray_target"))] = state.get("turn", 0)
            fight.pop("ability_result", None)
            return lines + [f"SAY {name} has no clear line to {fight.get('ray_target')} (a wall in the way?): holding fire at it and closing in."], None
        cool = fight.pop("ability_cooldown", None)
        if cool:
            cooldowns(world)[name] = state.get("turn", 0) + cool["turns"]
            fight.pop("ability_result", None)
            return lines + [f"SAY {name} is still cooling down ({cool['turns']} turns), so I fight on without it."], None
        if why is None:
            cooldowns(world)[name] = state.get("turn", 0) + COOLDOWN.get(name, 20)
            result = fight.pop("ability_result", {})
            fight["msgs"] = list(state.get("messages") or [])  # the ability's own messages aren't "unexpected"
            world.note(name, f"used at turn {state.get('turn')}: " + " | ".join(m[:100] for m in result.get("messages", [])[-4:]),
                       turn=state.get("turn"), zone=(state.get("player") or {}).get("zone"))
    return lines, why


def engage(state, memory, args, world):
    fight = memory.setdefault("fight", {})
    new = new_messages(state, fight)
    record(new, world, state)
    hostiles, px, py = hostiles_in_view(state, world, args.get("hunt", False))
    # Prey in deep water isn't worth a swim (2026-11-25: chasing a glowfish, the game said "There is a deep
    # pool of salty water that way. Move ... again to enter it and start swimming"): leave that one be, as
    # long as it stays where it was.
    skip = fight.setdefault("skip", [])
    if any("deep pool" in m and "start swimming" in m for m in new) and fight.get("target_at"):
        skip.append(fight["target_at"])
    hostiles = [o for o in hostiles if (o.get("id") or f"{o['name']}@{o['x']},{o['y']}") not in skip
                or (o.get("hostile") and max(abs(o["x"] - px), abs(o["y"] - py)) <= 1)]  # one next to us is fought
    # What this call's blows did (game knowledge for the threat estimate): our swings count against the
    # target we were fighting, or the one hostile next to us.
    adjacent = [o for o in hostiles if max(abs(o["x"] - px), abs(o["y"] - py)) == 1]
    swung_at = next((o for o in adjacent if o["name"] == fight.get("target")), adjacent[0] if len(adjacent) == 1 else None)
    try:
        threat.observe(world, new, state, swung_at)
    except Exception:
        pass
    player = state.get("player") or {}
    turn = state.get("turn", 0)

    if not hostiles and args.get("stay"):
        # stay (with hold): keep this cell even when nothing is in view (fighting from a staircase: they
        # come to us, and the way out is one step away). Never for ever (the user, 2026-11-25: never
        # assume enemies will do something without safeties and wake-ups; the croc was dead and we held
        # for 150 turns): at full HP with nothing in view for stay_turns, hand over.
        fight["active"] = False
        p0 = state.get("player") or {}
        if (p0.get("hp") or 0) >= (p0.get("maxhp") or 1):
            fight["idle"] = fight.get("idle", 0) + 1
            if fight["idle"] > args.get("stay_turns", 10):
                fight["idle"] = 0
                return None, f"stay over: nothing in view for {args.get('stay_turns', 10)} turns at full HP"
        else:
            fight["idle"] = 0
        return ["CMD CmdWait"], None
    fight["idle"] = 0
    if not hostiles:
        if fight.get("active"):
            fight["active"] = False
            hp_, mx_ = player.get("hp") or 0, player.get("maxhp") or 1
            said = ["SAY That fight is over: HP %s/%s." % (hp_, mx_)]
            if hp_ < 0.6 * mx_:
                said.append(f"VOICE hurt: That one hurt. {hp_} of {mx_} left.")
            return said, None
        return None, None

    lines = []
    if not fight.get("active"):
        fight.update({"active": True, "start_turn": turn, "max_hit": 0, "hp_start": player.get("hp"),
                      "ids": [o.get("id") or o["name"] for o in hostiles], "close_noted": [], "lost_noted": False,
                      "trail": [], "approach": None})
        new = []  # what happened before the fight isn't the fight's business
    # Hand-overs for fights that need thinking, not the routine (the user, 2026-11-25: coming close to
    # death unexpectedly certainly qualifies; chancy fights are better played a turn at a time by the LLM).
    # The routine decides only *when* to hand over; what to do then is the LLM's judgment.
    #  - a new enemy joins a fight that's already going (the giant centipede at the vine corner)
    if fight.get("active") and args.get("handover_new_enemy", True):
        known_ids = fight.setdefault("ids", [])
        joined = [o for o in hostiles if (o.get("id") or o["name"]) not in known_ids
                  and max(abs(o["x"] - px), abs(o["y"] - py)) <= args.get("join_radius", 6)
                  and not (world.kind(o["name"]) or {}).get("harmless")]
        for o in hostiles:
            if (o.get("id") or o["name"]) not in known_ids:
                known_ids.append(o.get("id") or o["name"])
        # Only one that matters: a newcomer the estimate makes an easy kill on its own (2026-11-25: two
        # 3-HP bats handed the fight over) just joins the routine fight.
        def matters(o):
            # A rooted melee kind 2+ cells off can't join anything (2026-11-26: a glowpad 5 cells off in its
            # pool handed the run over as "new enemy joined").
            k = world.kind(o["name"]) or {}
            if k.get("mobile") is False and not k.get("ranged") and max(abs(o["x"] - px), abs(o["y"] - py)) >= 2:
                return False
            try:
                e = threat.estimate(state, world, o)
            except Exception:
                return True
            r = (e.get("ttk_them") or 0) / max(e.get("ttk_us") or 1e9, 0.01)
            return not (e.get("ok") and r <= args.get("join_easy_ratio", 0.3))
        joined = [o for o in joined if matters(o)]
        if joined and turn > fight.get("start_turn", turn):
            o = joined[0]
            return None, handover(state, f"new enemy joined: {o['name']} at ({o['x']},{o['y']}), {max(abs(o['x'] - px), abs(o['y'] - py))} away, HP {player.get('hp')}/{player.get('maxhp')}", fight)
    #  - HP going faster than the estimate said (more than twice the expected loss, and a real amount)
    if fight.get("active") and fight.get("expected_dpt") and not fight.get("lost_noted"):
        lost = (fight.get("hp_start") or 0) - (player.get("hp") or 0)
        turns_ = max(1, turn - fight.get("est_turn", turn))
        if lost >= max(4, 0.25 * (player.get("maxhp") or 1)) and lost > 2 * fight["expected_dpt"] * turns_ + 2:
            fight["lost_noted"] = True
            return None, handover(state, f"faster than expected: lost {lost} HP in {turns_} turns (estimate {fight['expected_dpt']:.1f} a turn), HP {player.get('hp')}/{player.get('maxhp')}", fight)

    # Who are we facing? Every kind in view needs a verdict.
    kinds = []
    # Only those near enough to matter need a verdict now; a far one (a guard dog 33 cells off,
    # 2026-11-24) is assessed when it comes within assess_radius.
    near = [o for o in hostiles if max(abs(o["x"] - px), abs(o["y"] - py)) <= args.get("assess_radius", 12)]
    # ignore_far: nothing within assess_radius means nothing to fight now (a creature we avoid can stand
    # far off without stopping the explorer; explore's danger_radius still stops it as one comes closer).
    if not near and args.get("ignore_far"):
        return None, None
    hostiles = near or hostiles[:1]
    for o in hostiles:
        k = world.kind(o["name"])
        if k is None:
            return None, f"new enemy: {o['name']} at ({o['x']},{o['y']}); Look at it and set its verdict"
        if k.get("verdict") != "fight":
            return None, f"{k.get('verdict')} enemy: {o['name']} at ({o['x']},{o['y']})"
        kinds.append(k)
    # Only those that can reach us count towards being outnumbered: an immobile one (a jilted lover, a
    # dreadroot) a few cells off can't join in (2026-11-24, one 4 cells away made it "3 hostiles").
    def reaches(o):
        k = world.kind(o["name"]) or {}
        # a rooted shooter reaches us too (2026-11-25: the vine was left for "immobile, later" while it shot us)
        return k.get("mobile") is not False or k.get("ranged") or max(abs(o["x"] - px), abs(o["y"] - py)) <= 1
    active = [o for o in hostiles if reaches(o)]
    # Outnumbered means close enough to join in now (within outnumber_radius), not merely in view.
    # Harmless kinds (dreadroots: no attacks, only an aura) don't count towards being outnumbered.
    close = [o for o in active if max(abs(o["x"] - px), abs(o["y"] - py)) <= args.get("outnumber_radius", 3)
             and not (world.kind(o["name"]) or {}).get("harmless")]
    if len(close) > args.get("max_hostiles", 2):
        return None, f"outnumbered: {len(close)} hostiles within {args.get('outnumber_radius', 3)} cells"

    effects = [e for k in kinds for e in k.get("effects", [])]
    for m in new:
        if "deep pool" in m and "start swimming" in m:
            continue  # handled above: that prey is skipped
        if not any(p.search(m) for p in ORDINARY) and not any(e in m for e in effects):
            return None, f"unexpected: {m[:160]}"

    hp, maxhp = player.get("hp"), player.get("maxhp")
    # Only rooted enemies around and the siege on: being hurt is the siege's cue to step out and heal,
    # not a reason to hand over (still handed over below a quarter, or at two of the biggest hits).
    siege_only = args.get("siege", True) and hostiles and all(
        (world.kind(o["name"]) or {}).get("mobile") is False for o in hostiles if o.get("hostile"))
    if hp is not None and maxhp and hp < (0.25 if siege_only else args.get("raise_hp_fraction", 0.5)) * maxhp:
        return None, f"hurt: HP {hp}/{maxhp} fighting {hostiles[0]['name']}"
    # Two more hits like the biggest one this fight would finish us: hand over whatever the fraction
    # (2026-11-24: a baboon bit for 9 at HP 18; 9/18 wasn't "below 50%", and the next bite killed).
    for m in new:
        h = HIT.match(m)
        if h:
            fight["max_hit"] = max(fight.get("max_hit", 0), int(h.group(2)))
    if hp is not None and fight.get("max_hit") and hp <= args.get("raise_hits", 2) * fight["max_hit"]:
        return None, f"hurt: HP {hp}/{maxhp}, and the biggest hit this fight was {fight['max_hit']}"
    # A kill starts the clock again: a run of glowpads killed one after another is progress, not one long
    # fight (2026-11-25: stopped at 21 turns right after a kill).
    if any(" dies!" in m or "You kill" in m for m in new):
        fight["start_turn"] = turn
    # Walking up to harmless prey across a zone isn't a long fight: only count with a hostile in view.
    # Only turns with a mobile hostile close by count (2026-11-25: a glowfish keeping to its pool 9 cells
    # off made a hunt "a long fight").
    if not any(o.get("hostile") and (world.kind(o["name"]) or {}).get("mobile") is not False
               and max(abs(o["x"] - px), abs(o["y"] - py)) <= 3 for o in hostiles):
        fight["start_turn"] = turn
    # A siege on rooted enemies is long by nature (a 50-HP glowpad at 2 a blow): only mobile ones count.
    if (any(o.get("hostile") for o in hostiles) and not siege_only
            and turn - fight.get("start_turn", turn) > args.get("max_fight_turns", 20)):
        return None, f"long fight: {turn - fight['start_turn']} turns against {hostiles[0]['name']}"

    # Enemy states read from the fight's messages (the user, 2026-11-24: know how hard a target is
    # dynamically). A tightened carapace doubles its AV bonus while it stays still: don't waste blows on
    # it (and it can't chase); a streak of blows that don't penetrate means switch weapon or leave.
    states = fight.setdefault("states", {})
    for m in new:
        c = CARAPACE.match(m)
        if c:
            states.setdefault(W_kind(c.group(1)), {})["carapace"] = "tight" if c.group(3) else "loose"
        n = NOPEN.match(m)
        if n:
            st = states.setdefault(W_kind(n.group(1) or n.group(2)), {})
            st["nopen"] = st.get("nopen", 0) + 1
        h = PENHIT.match(m)
        if h and fight.get("target"):
            states.setdefault(W_kind(fight["target"]), {})["nopen"] = 0
    def estate(o):
        st = dict(states.get(W_kind(o["name"]), {}))
        effects = " ".join(o.get("effects") or []).lower()  # mod v0.20: the creature's own effects
        if "carapace" in effects and ("tight" in effects or "tighten" in effects):
            st["carapace"] = "tight"
        return st

    # Those that can reach us first; immobile ones wait until nothing else is around; a shelled one
    # (tightened carapace) last.
    pool = active or hostiles
    # A shooter in view comes first, whatever else is nearer (2026-11-25: with a vine and a dreadroot both 2
    # cells off, we faced the dreadroot and regenerated in place while the vine shot us 16 -> 6).
    pool = sorted(pool, key=lambda o: (estate(o).get("carapace") == "tight",
                                       tactic(world.kind(o["name"])) != "close" and o.get("hostile", False) is not None
                                       and not (world.kind(o["name"]) or {}).get("ranged"),
                                       max(abs(o["x"] - px), abs(o["y"] - py))))
    target = pool[0]
    shooter_in_view = any(o.get("hostile") and (world.kind(o["name"]) or {}).get("ranged") for o in hostiles)
    dx, dy = target["x"] - px, target["y"] - py
    tk = world.kind(target["name"])
    dist = max(abs(dx), abs(dy))
    tstate = estate(target)

    # Live threat estimate (the user, 2026-11-24: all evaluations dynamic). From the target's stats and
    # what its kind has done to us, against our HP, AV and weapon now: if we'd lose the exchange, hand
    # over: "kite" when it moves slower than us (ray, step back, let it come), "too strong" otherwise. The
    # LLM can overrule for one plan with args.trust_estimate = false.
    # accept_kinds: kinds the LLM chose to fight despite the estimate (e.g. an even trade at full HP with
    # healing in the pack), for this plan only.
    if args.get("trust_estimate", True) and not tk.get("harmless") and W_kind(target["name"]) not in args.get("accept_kinds", []):
        others = [o for o in active if o is not target and max(abs(o["x"] - px), abs(o["y"] - py)) <= 2]
        try:
            est = threat.estimate(state, world, target, others)
        except Exception as ex:
            est = {"ok": None, "why": f"estimate failed: {ex}"}
        fight["estimate"] = {"turn": turn, "target": target["name"], "ok": est.get("ok"), "why": est.get("why")}
        if est.get("theirs") is not None and not fight.get("expected_dpt"):
            fight["expected_dpt"], fight["est_turn"] = est["theirs"], turn
            fight["hp_start"] = player.get("hp")
        #  - a close fight: the estimate says we win, but not by much (the vine corner, the centipede at 9
        #    HP). Mobile or shooting enemies only: rooted melee ones are the siege's, prey is left alone.
        ratio = (est.get("ttk_them") or 0) / max(est.get("ttk_us") or 1e9, 0.01)
        tac0 = tactic(world.kind(target["name"]))
        noted_close = fight.setdefault("close_noted", [])
        tkey = target.get("id") or target["name"]
        if (est.get("ok") and target.get("hostile") and tac0 in ("hold", "close") and tkey not in noted_close
                and ratio > args.get("close_fight_ratio", 0.45) and args.get("handover_close", True)):
            noted_close.append(tkey)
            return None, handover(state, f"close fight: {target['name']}: {est.get('why')} (ratio {ratio:.2f})", fight, est)
        # Find out before committing (the user, 2026-11-24: learning beats avoiding everything): parts
        # beyond melee, or the game's difficulty word harsher than our estimate, mean something we don't
        # model. Hand over once per kind with what we see; the LLM decides how (range first, step away
        # before the kill...) and lets the routine go on with accept_kinds.
        noted = fight.setdefault("found_out", [])
        kind_key = W_kind(target["name"])
        harsh = est.get("diff") in threat.HARSH and est.get("ok") is not False
        if (est.get("flags") or harsh) and kind_key not in noted:
            noted.append(kind_key)
            bits = []
            if est.get("flags"):
                bits.append("parts " + ", ".join(est["flags"]))
            if harsh:
                bits.append(f"the game rates it {est['diff']} while my estimate says {'easy' if est.get('ok') else 'unclear'}")
            return None, f"find out: {target['name']} has " + " and ".join(bits) + f"; {est.get('why')}"
        rooted = (world.kind(target["name"]) or {}).get("mobile") is False
        if rooted and target.get("hostile") and args.get("siege", True) and tactic(world.kind(target["name"])) == "siege":
            # Siege, as tools/siege.py does it (the user, 2026-11-25: the siege is very good): a rooted enemy
            # can't follow, so an even fight is safe by hit-and-heal. Below the floor, step out of its reach
            # and regenerate to full; then go back in. Waiting turns don't count as a long fight.
            hp0, mx0 = player.get("hp") or 0, player.get("maxhp") or 1
            dist0 = max(abs(target["x"] - px), abs(target["y"] - py))
            rooted_all = [o for o in hostiles if (world.kind(o["name"]) or {}).get("mobile") is False]
            if hp0 < args.get("siege_floor", 0.6) * mx0:
                fight["sieging"] = True
            if fight.get("sieging") and hp0 >= mx0:
                fight["sieging"] = False
            if fight.get("sieging"):
                fight["start_turn"] = turn
                if any(max(abs(o["x"] - px), abs(o["y"] - py)) <= 1 for o in rooted_all):
                    grid = (state.get("map") or {}).get("rows") or []
                    taken = {(o["x"], o["y"]) for o in (state.get("map") or {}).get("objects", []) if o.get("creature")}
                    cells = [(px + dx, py + dy) for dx in range(-2, 3) for dy in range(-2, 3)]
                    cells = [c for c in cells if 0 <= c[1] < len(grid) and 0 <= c[0] < len(grid[c[1]])
                             and grid[c[1]][c[0]] not in "▒ #~≈" and c not in taken
                             and all(max(abs(o["x"] - c[0]), abs(o["y"] - c[1])) > 1 for o in rooted_all)]
                    if cells:
                        c = min(cells, key=lambda c: max(abs(c[0] - px), abs(c[1] - py)))
                        return [f"SAY Down to {hp0}/{mx0} against {target['name']}: stepping out of its reach to heal.", f"GOTO {c[0]} {c[1]}"], None
                    return None, f"siege: no cell out of reach of {target['name']} at HP {hp0}/{mx0}"
                if fight.get("regen_said") != hp0 // 5:
                    fight["regen_said"] = hp0 // 5
                    return [f"SAY Out of {target['name']}'s reach at {hp0}/{mx0}: regenerating before going back in.", heal(fight, state, world, hostiles)], None
                return [heal(fight, state, world, hostiles)], None
            if dist0 >= 2 and hp0 < mx0:
                fight["start_turn"] = turn
                return [heal(fight, state, world, hostiles)], None  # top up before walking in
            est = dict(est, ok=True)  # in reach and healthy enough: fight it (below)
        rooted_far = rooted and max(abs(target["x"] - px), abs(target["y"] - py)) >= 2 and not args.get("siege", True)
        if est.get("ok") is False and (not target.get("hostile") or rooted_far):
            # ...or a rooted hostile that can't reach us (2026-11-25: hostile glowpads in their pool stopped
            # explore again and again with "kite"). tools/siege.py takes those on hit-and-heal.
            # Prey we can't take cheaply at our level isn't a reason to stop: leave it be (2026-11-25, Uubas
            # at level 1: a glowpad took 18 -> 8 with bleeding).
            skip = fight.setdefault("skip", [])
            skip.append(target.get("id") or f"{target['name']}@{target['x']},{target['y']}")
            return [f"SAY Leaving {target['name']} alone for now: {est['why']}"], None
        if est.get("ok") is False:
            slow = threat.kiteable(state, target)
            if slow:
                return None, f"kite: {target['name']} is slower than me; {est['why']}"
            return None, f"too strong: {target['name']}; {est['why']}" + ("" if slow is False else " (speed unknown)")
    if tstate.get("nopen", 0) >= 3:
        # Our blows keep failing to get through: the ray (it ignores armour) if it's ready, else the LLM.
        fight["armoured"] = target["name"]

    # Missile weapon (the musket, 2026-11-24: one shot did 22 and killed the giant amoeba). Its picker
    # locks onto the nearest hostile, so fire only when our target is the nearest with no tie; reload
    # when it's empty and nothing is adjacent (reloading takes a turn).
    if args.get("missile", True):
        equipped = state.get("equipped") or []
        loaded = any(LOADED.search(e) for e in equipped)
        empty = any(EMPTY.search(e) for e in equipped)
        dists = sorted(max(abs(o["x"] - px), abs(o["y"] - py)) for o in hostiles)
        # The picker locks onto the nearest; a tie is fine (any of them is a target we're fighting).
        nearest = dist == dists[0]
        # A shot that hit something else (a wall: "You critically hit the shale") means no clear line:
        # hold fire at that target for a while. Only shoot what can reach or shoot us (not an
        # immobile melee plant like the dreadroot: ammo for nothing).
        blocked = fight.setdefault("no_shot", {})
        for m in new:
            hit = SHOT.match(m)
            if hit and fight.get("last_shot") and W_kind(hit.group(1) or hit.group(2)) != W_kind(fight["last_shot"]):
                blocked[W_kind(fight["last_shot"])] = turn
        # Ammo is cheap ($0.03) but scarce (Tam had 47), and a shot plus reload costs ~2 turns against
        # one axe swing: shoot only where damage before contact matters (the user, 2026-11-24): kinds
        # marked shoot, dangerous kinds (avoid, ranged, or a hit of 5+ on us), or when we're hurt.
        # Never below a reserve of slugs, and never at what can't reach or shoot us.
        slugs = sum(int(m.group(1) or 1) for e in (state.get("inventory") or [])
                    for m in [re.match(r"lead slug(?: x(\d+))?", e)] if m)
        hurt = hp is not None and maxhp and hp < args.get("shoot_hp_fraction", 0.6) * maxhp
        dangerous = (tk.get("verdict") == "avoid" or tk.get("ranged") or tk.get("max_hit", 0) >= 5
                     or tk.get("max_turn_damage", 0) >= 8)
        reaches_us = tk.get("mobile") is not False or tk.get("ranged")
        worth = (reaches_us and tk.get("shoot") is not False
                 and (tk.get("shoot") or dangerous or hurt)
                 and (slugs > args.get("slug_reserve", 10) or hurt))
        clear = turn - blocked.get(W_kind(target["name"]), -999) > args.get("blocked_turns", 10)
        # Not point-blank: the musket's accuracy is low and a wild shot next to them wastes a turn
        # (2026-11-24, two girshlings adjacent: "Your shot goes wild!"). Adjacent ones get the axe.
        if loaded and nearest and worth and clear and 2 <= dist <= args.get("missile_range", 12):
            fight["last_shot"] = target["name"]
            fight["firing"] = {"turn": turn, "target": target["name"]}
            return lines + [f"SAY {target['name']} is worth a slug ({dist} cells off): shooting before it reaches me.", "CMD CmdFire"], None
        if empty and dist >= 2 and worth:
            return lines + ["SAY Reloading while it is still out of reach.", "CMD CmdReload"], None

    # Abilities. Targeted ones come locked onto "a" target in their picker and we can't see which, so
    # they're only used when the target is the only creature in view. Cooldowns are tracked by turn.
    if args.get("abilities", True):
        # Safe to fire a locked picker when the game's current target (snapshot "target", mod v0.15) is
        # our hostile; without that field, only when it's the only creature in view.
        creatures = [o for o in (state.get("map") or {}).get("objects", []) if o.get("creature")]
        locked = (state.get("player") or {}).get("target")
        if locked is not None:
            alone = locked.get("x") == target["x"] and locked.get("y") == target["y"]
        else:
            alone = len(creatures) == 1
        ready = cooldowns(world)
        def is_ready(n):
            return turn >= ready.get(n, -1)
        # Teleport is never scripted: it lands at random within 12 cells, which can be worse than the
        # fight (user, 2026-11-24). Only the LLM uses it, when death is otherwise near certain.
        pick = None
        # The ray also freezes: the cave spider took no turns while frozen (2026-11-24), so it's worth
        # using adjacent too, not only as an opener.
        # Not at a target a shot or ray just failed to reach (a wall in the way).
        line_clear = turn - fight.get("no_shot", {}).get(W_kind(target["name"]), -999) > args.get("blocked_turns", 10)
        if alone and line_clear and 1 <= dist <= 9 and is_ready("Freezing Ray"):
            pick = "Freezing Ray"
        elif alone and line_clear and 3 <= dist <= 4 and is_ready("Charge"):  # from 2 it failed every time ("no clear line"), from 4 it worked (2026-11-26)
            pick = "Charge"
        if pick:
            fight["using"] = pick
            fight["ray_target"] = target["name"]
            lines.append(f"SAY {pick} on {target['name']} from {dist} cells: " + ("damage plus a turn of freeze." if pick == "Freezing Ray" else "closing the gap with an attack."))
            more, why, done = ability.step(state, fight, pick)
            if why:
                fight.pop("using", None)
                return None, why
            return lines + more, None
    if (fight.get("target") != target["name"] and tk.get("mobile") is False and not tk.get("harmless") and hp is not None and maxhp
            and not (args.get("siege", True) and target.get("hostile"))  # the siege rests us before going in
            and hp < tk.get("engage_hp_fraction", args.get("engage_hp_fraction", 0.7)) * maxhp):
        # A new target that can't follow: better to rest first (step out of its sight); the LLM decides.
        return None, f"hurt before engaging: HP {hp}/{maxhp}, next is {target['name']}, which doesn't move"
    # Walking to a target, stay committed to it while it's out of view (2026-11-27, Siwur: two glowpads in
    # their pools, 9 and 13 cells off; from one cell only A was in sight, from the next only B, so every
    # step turned round and we walked A-B-A-B for 40 turns). Re-picking from what's in view each call
    # flips whenever a step hides the one we chose. Kept until we're next to its last known cell, a kill
    # message names it, or approach_patience turns pass.
    # Only while nothing in view can come at us (the user, 2026-11-27: rounding a corner into nearer, more
    # dangerous enemies and walking past them is not the same case): any hostile in view that moves or
    # shoots gets the normal choice, and the new-enemy hand-over above still applies.
    tid = target.get("id") or f"{target['name']}@{target['x']},{target['y']}"
    goal = fight.get("approach")
    in_view = {(o.get("id") or f"{o['name']}@{o['x']},{o['y']}") for o in hostiles}
    killed = {k.group(1) for m in new for k in [KILL.match(m)] if k}
    def can_come(o):
        k = world.kind(o["name"]) or {}
        return o.get("hostile") and (k.get("mobile") is not False or k.get("ranged"))
    danger_in_view = any(can_come(o) for o in hostiles)
    committed = (goal if goal and goal["id"] != tid and goal["id"] not in in_view and goal["name"] not in killed
                 and dist > 1 and not danger_in_view
                 and turn - goal["turn"] <= args.get("approach_patience", 40)
                 and max(abs(goal["x"] - px), abs(goal["y"] - py)) > 1 else None)
    if not committed:
        fight["approach"] = {"id": tid, "name": target["name"], "x": target["x"], "y": target["y"], "turn": turn}
    fight["target_at"] = target.get("id") or f"{target['name']}@{target['x']},{target['y']}"
    if fight.get("target") != target["name"] and not committed:
        fight["target"] = target["name"]
        k = world.kind(target["name"])
        lines.append(f"VOICE engage: {W_kind(target['name']).capitalize()}. Engaging.")
        n_mine = (world.data.get("run") or {}).get("kills", {}).get(W_kind(target["name"]), 0)
        lines.append(f"SAY Fighting {target['name']} ({k.get('difficulty', '?')}" + (f"; this character has killed {n_mine} before" if n_mine else "; a first for this character") + ").")
    # Our blows keep failing to get through and the ray isn't an option this turn: the LLM decides.
    if fight.get("armoured") == target["name"] and tstate.get("nopen", 0) >= 3:
        return None, f"armour: {tstate['nopen']} blows in a row didn't penetrate {target['name']}; ray on cooldown or blocked"
    # A shelled target (carapace tightened) that is the only one next to us: step away (it can't chase
    # while tightened) to a free cell next to no hostile.
    if max(abs(dx), abs(dy)) == 1 and tstate.get("carapace") == "tight":
        occupied = {(o["x"], o["y"]) for o in hostiles}
        grid = (state.get("map") or {}).get("rows") or []
        for (ddx, ddy), key in DIRS.items():
            x, y = px + ddx, py + ddy
            if (0 <= y < len(grid) and 0 <= x < len(grid[y]) and grid[y][x] in ".,'`\"~" and (x, y) not in occupied
                    and all(max(abs(o["x"] - x), abs(o["y"] - y)) > 1 for o in hostiles)):
                return lines + [f"SAY {target['name']} has its carapace tightened: stepping away (it can't chase while shelled).",
                                f"CMD CmdMove{key}"], None
    if max(abs(dx), abs(dy)) == 1:
        # An attack the game silently ignored (no hit, miss or penetration message): a flier that's
        # airborne without showing "flying" (the user, 2026-11-26: dragonflies are only reliably hittable
        # when they come down to bite). Two in a row at prey: leave that one for this zone.
        tid = target.get("id") or f"{target['name']}@{target['x']},{target['y']}"
        last = fight.get("attacked") or [None, None]
        if last[0] == tid and last[1] is not None and 0 <= (turn or 0) - last[1] <= 2:
            if not any(re.match(r"^You (hit|miss|don't penetrate|critically|cleave)", m) for m in new):
                fight["silent"] = fight.get("silent", 0) + 1
            else:
                fight["silent"] = 0
        else:
            fight["silent"] = 0
        if fight.get("silent", 0) >= 2 and not target.get("hostile"):
            fight["silent"] = 0
            fight.pop("attacked", None)
            fight.setdefault("skip", []).append(tid)
            return lines + [f"SAY My blows at {target['name']} aren't landing at all: leaving it."], None
        fight["attacked"] = [tid, turn]
        return lines + [f"CMD CmdAttack{DIRS[(dx, dy)]}"], None
    # Holding a position (the LLM's call, e.g. a wall at our back with no safe retreat, 2026-11-24
    # Maggatum): shots and rays above still fire, adjacent ones get the axe, otherwise wait for them.
    # Only a hostile comes to us; prey never does (2026-11-25: the bot "held its spot" for a glowfish 27
    # cells off until the fight timed out), so walk over to prey.
    # A hostile that isn't closing in (2026-11-25: glowpads turned hostile but stayed in their pool for 12
    # turns while we held) won't come: after hold_patience turns with no step closer, go to it.
    best = fight.setdefault("closest", {})
    if dist < best.get(target["name"], [99, turn])[0]:
        best[target["name"]] = [dist, turn]
    # Once we give up waiting for one, we go to it for good: our own steps shrink the distance too, which
    # isn't it closing in (2026-11-25: hold and approach alternated every 4 turns).
    going = fight.setdefault("going_to", [])
    stalled = target["name"] in going or turn - best[target["name"]][1] >= args.get("hold_patience", 4)
    if stalled and target["name"] not in going:
        going.append(target["name"])
    if args.get("hold") and target.get("hostile") and not stalled and tactic(world.kind(target["name"])) == "hold"             and not shooter_in_view:
        if not fight.get("holding"):
            fight["holding"] = True
            lines.append(f"SAY Holding my spot: {target['name']} is {dist} cells off, let it come to me.")
        return lines + ["CMD CmdWait"], None
    # Hurt, and it isn't coming to us: heal where we stand before going to it (the user, 2026-11-25: pause
    # to heal unless enemies are right next to us). Waiting doesn't count towards a long fight.
    if hp is not None and maxhp and hp < args.get("rest_fraction", 1.0) * maxhp and tactic(world.kind(target["name"])) != "close"             and not shooter_in_view:
        # (not for a shooter: standing still in its line is being shot, so close in instead)
        fight["start_turn"] = turn
        if fight.get("regen_said") != hp // 5:
            fight["regen_said"] = hp // 5
            lines.append(f"SAY Hurt ({hp}/{maxhp}) and {target['name']} isn't coming: regenerating here before going to it.")
        return lines + [heal(fight, state, world, hostiles)], None
    if fight.get("holding") and stalled:
        fight["holding"] = False
        lines.append(f"SAY {target['name']} isn't coming closer: going to it.")
    gx, gy = (committed["x"], committed["y"]) if committed else (target["x"], target["y"])
    # The catch-all: approach steps that keep landing on the same two cells are going nowhere, whatever
    # the cause (the no-progress failsafe in step.py misses it: the answers alternate and the position
    # changes). Hand over rather than walk in place.
    trail = fight.setdefault("trail", [])
    trail.append([px, py, turn])
    del trail[:-args.get("pace_steps", 8)]
    if len(trail) >= args.get("pace_steps", 8) and len({(c[0], c[1]) for c in trail}) <= 2:
        cells = sorted({(c[0], c[1]) for c in trail})
        fight["trail"] = []
        return None, handover(state, f"going back and forth between {' and '.join(map(str, cells))} for {len(trail)} steps "
                                     f"(towards {committed['name'] if committed else target['name']} at ({gx},{gy})); "
                                     "the routine can't reach it from here", fight)
    return lines + [f"GOTO {gx} {gy}"], None
