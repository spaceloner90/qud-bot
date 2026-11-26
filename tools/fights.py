"""Fight review: rebuild the game's message stream from live/log.jsonl, cut it into fights, and summarise
each one, so the LLM can look for mistakes and improvements (the user, 2026-11-24: re-evaluate our own
fights; e.g. reload in downtime, the dreadroot).

  python tools/fights.py [--since TURN] [--last N]

Per fight: turns, HP at start/end and lowest, damage taken and dealt, kills and XP, our actions (melee,
shots, rays, charges, reloads), wasted actions (shots into walls, "no clear line", cooldown tries),
effects suffered, the bot's hand-offs, and flags worth a look. Output is plain text.
"""
import argparse, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

TAKEN = re.compile(r"^The (.+?) (?:critically )?hits (?:you )?\(x\d+\) (?:with .+? )?for (\d+) damage")
DEALT = re.compile(r"^You (?:critically )?hit (?:the (.+?) )?\(x\d+\) (?:with .+? )?for (\d+) damage")
DIES = re.compile(r"^The (.+) dies!$")
XP = re.compile(r"^You gain (\d+) XP")
COMBAT = re.compile(r"(hits|misses|hit \(|hit the|dies!|penetrate|freezing|charge|You miss|lead slug|bleeding|terror)", re.I)
EFFECT = re.compile(r"^You (are overwhelmed with terror|are dazed|begin bleeding|become confused|are stunned)")


def stream(since):
    """(turn, message, hp, maxhp) for each new game message, in order; and bot lines (turn, text)."""
    prev, out, bot = None, [], []
    for line in (ROOT / "live" / "log.jsonl").open(encoding="utf-8"):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        s = r.get("state")
        if not isinstance(s, dict) or not s.get("turn") or s["turn"] < since:
            continue
        msgs = list(s.get("messages") or [])
        p = s.get("player") or {}
        new = msgs
        if prev is not None:
            new = []
            for n in range(min(len(prev), len(msgs)), 0, -1):
                if prev[-n:] == msgs[:n]:
                    new = msgs[n:]
                    break
            else:
                new = msgs
        for m in new:
            for part in m.split("\n"):
                if part.strip():
                    out.append((s["turn"], part.strip(), p.get("hp"), p.get("maxhp")))
        prev = msgs
        ans = r.get("answer") or ""
        for l in ans.splitlines():
            if l.startswith(("CMD ", "KEY ", "GOTO ")):
                bot.append((s["turn"], l.strip()))
    return out, bot


def fights(msgs, gap=5):
    cur, last = [], None
    for t, m, hp, mx in msgs:
        if COMBAT.search(m) and not m.startswith("Bot"):
            if cur and last is not None and t - last > gap:
                yield cur
                cur = []
            last = t
        if cur or COMBAT.search(m):
            if last is not None and t - last > gap and cur:
                yield cur
                cur, last = [], None
                continue
            cur.append((t, m, hp, mx))
    if cur:
        yield cur


def summarise(f, narration):
    t0, t1 = f[0][0], f[-1][0]
    hps = [hp for _, _, hp, _ in f if hp is not None]
    taken, dealt, kills, xp, acts, waste, eff = {}, 0, [], 0, {}, [], []
    for t, m, hp, mx in f:
        a = TAKEN.match(m)
        if a and not m.startswith("You"):
            taken[a.group(1)] = taken.get(a.group(1), 0) + int(a.group(2))
        d = DEALT.match(m)
        if d:
            dealt += int(d.group(2))
            if d.group(1) and any(w in d.group(1) for w in ("shale", "wall", "rock", "sandstone")):
                waste.append(f"{t}: shot into {d.group(1)}")
        if "fails to penetrate the shale" in m or "fails to penetrate the wall" in m:
            waste.append(f"{t}: {m[:60]}")
        k = DIES.match(m)
        if k:
            kills.append(k.group(1))
        x = XP.match(m)
        if x:
            xp += int(x.group(1))
        for key, pat in (("melee", r"^You (critically )?hit \(x"), ("shot", r"with a lead slug"), ("ray", r"^You emit a freezing ray"),
                         ("charge", r"^You charge"), ("reload", r"^You reload"), ("miss", r"^You miss")):
            if re.search(pat, m):
                acts[key] = acts.get(key, 0) + 1
        e = EFFECT.match(m)
        if e:
            eff.append(f"{t}: {e.group(1)}")
    notes = [(t, x) for t, x in narration if t0 - 1 <= t <= t1 + 1]
    handoffs = [f"{t}: {x[:110]}" for t, x in notes if x.startswith(("!!", "stage")) and "done" in x or x.startswith("!!")]
    waste += [f"{t}: {x[:90]}" for t, x in notes if "no clear line" in x or "cooling down" in x]
    flags = []
    if hps and min(hps) < 0.5 * max(hps):
        flags.append(f"HP fell to {min(hps)}")
    if sum(taken.values()) > dealt and kills:
        flags.append("took more damage than we dealt")
    if acts.get("reload") and t0 <= min(t for t, m, *_ in f if "reload" in m.lower()) <= t0 + 2:
        flags.append("reloaded at the start of the fight (could have been done in downtime)")
    if waste:
        flags.append(f"{len(waste)} wasted action(s)")
    if eff:
        flags.append("suffered: " + ", ".join(sorted({x.split(': ')[1] for x in eff})))
    return {
        "turns": f"{t0}-{t1}", "hp": f"{hps[0] if hps else '?'} -> {hps[-1] if hps else '?'} (low {min(hps) if hps else '?'})",
        "taken": taken, "dealt": dealt, "kills": kills, "xp": xp, "actions": acts,
        "wasted": waste, "effects": eff, "hand-offs": handoffs, "flags": flags,
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=0)
    ap.add_argument("--last", type=int, default=10)
    a = ap.parse_args()
    msgs, _ = stream(a.since)
    narration = []
    try:
        for l in (ROOT / "live" / "narration.log").read_text(encoding="utf-8").splitlines():
            t, _, x = l.partition("\t")
            if t.isdigit():
                narration.append((int(t), x))
    except FileNotFoundError:
        pass
    fs = [summarise(f, narration) for f in fights(msgs)]
    fs = [f for f in fs if f["kills"] or f["taken"] or f["dealt"] or f["flags"]]
    for f in fs[-a.last:]:
        print(f"== turns {f['turns']}  HP {f['hp']}  dealt {f['dealt']}  taken {sum(f['taken'].values())} {f['taken'] or ''}")
        print(f"   kills {f['kills']}  XP {f['xp']}  actions {f['actions']}")
        for k in ("wasted", "effects", "hand-offs"):
            if f[k]:
                print(f"   {k}: " + " | ".join(f[k][:6]))
        if f["flags"]:
            print("   FLAGS: " + "; ".join(f["flags"]))


if __name__ == "__main__":
    main()
