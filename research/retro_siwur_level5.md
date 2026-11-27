# Retrospective: Siwur, level 1 to level 5 (2026-11-26/27)

Same character as `retro_siwur.md` (save `1f19697d`), after the reload. Gemini/Antigravity played him to
a spider fight on Red Rock stratum 1 (`handover_2026-11-26.md`). Claude took over at turn 142586 (level 1,
10/18 HP, the spider at 1 HP) and reached the goal, **level 5**, at turn 146400: about 3,800 game turns,
no deaths, not a recorded run. The owner watched and stepped in several times. Their interventions are
the most useful part of this retro.

Proposed fixes and operations are listed at the end. **None of them has been applied**; this is for review.

(2026-11-27, later the same day: the owner approved the fixes, and they're applied; see design.md, "Fixes
from the Siwur level-5 retro". Findings: item 7, hunger, is the owner's own cook rule, not a bug. Item 11,
Charge, works from 4; the failure was a wall. Item 12, the ray, likely killed the vine unseen. Proficiency
for Long Blade showed no to-hit bonus, so it's unchanged. The operations are still pending.)

## Timeline

| Turn | What happened |
|---|---|
| 142586 | Took over from Gemini: finished the cave spider by hand (two misses took us to 7/18), **level 2**. Freezing Ray 2. |
| 142942 | Stratum 1 explored. Down with the game's walk-to-stairs prompt (`CmdMoveD`, `y`); the owner had pointed out that Gemini didn't know it. |
| 142993 | Stratum 2: an iron long sword (1d4, pen 6, one-handed) replaced the bronze battle axe. |
| 143011 | A seed-spitting vine shot us from out of view (6 damage) in a water channel. Freezing Ray east chilled two dreadroots but did no damage. Killed four dreadroots by hand. The vine was never found. |
| 143057 | **Level 3** (giant centipede): Strength 23, Multiple Legs 2, Long Blade, Defensive Stance on (DV -1 to 1). |
| 143154-143254 | A close fight with a cave spider in water (ray 5, then the sword). A three-way fight (a dreadroot and two scavengers) won with no damage: dreadroot first, the ray one-shot the wet scavenger, then waited for the other. |
| 143261 | Gear: leather cap, studded leather (AV 2 to 4), and a bronze two-handed sword carried for hard fights. |
| 143355 | A **slumberling** (level 21, 85 HP, "Impossible", asleep) 3 cells off: backed away, marked it avoid. The rest of stratum 2 was on its side. Cooked by the stairs, then down. |
| 143497 | Stratum 3, **level 4** (giant centipede): Freezing Ray 3. |
| 143684 | **Rofuluagoufoaho, the hulking Snapjaw Firesnarler** (50 HP, pyrokinesis) with a hunter and scavengers. The estimate gave 24 turns for us to kill him vs 2 for them to kill us. Fled west while burning (24/30), out of his line round a corridor bend. |
| 143752 | The explorer walked back into him (avoid only covers 12 cells round the last sighting). Fled again through his heat, back to the stairs and up to stratum 2. Stopped and talked it through. The owner chose to hunt the marsh zones. |
| 143800-144386 | Up through Red Rock (walk-to-stairs both ways), one world-map step south to the salt marsh (11,21). First zone: +475 XP, HP never below 27. |
| 144406-145121 | Second zone (11.21.0.1): a new kind (snapjaw warrior, set to fight). Four false stops: "glowpad is stunned" twice, a dragonfly sighting, the camp meal's text. |
| 145547-145586 | **The fight routine paced A-B-A-B between two hostile glowpads for 40 turns**; the owner spotted it. Fixed by committing to a target, refined by the owner: never walk past danger. Added a pacing hand-over. |
| 145589-145662 | Chests looted by hand (auto-loot never opened containers): a short bow and arrows found, bow equipped. A walk swam into a deep pool and the torch went out; relit by hand. |
| 145741-145868 | The explorer stalled at the swim prompt over loot across deep water. Fixed live, at the owner's direction: retry after sightings, give-ups kept per zone, chests opened automatically. |
| 146040 | **The run crashed: I edited a script while the bot was running** (an import added after its first use). The new chest routine also picked up a chest itself (it pressed `g` on the chest's own menu). |
| 146097-146154 | Swim-when-safe first live run: a stale swim message marked dry loot as deep, and snapjaw sightings 1,600-4,700 turns old kept the zone "unsafe". Both fixed. The sweep then stopped at once: the load was 299/369 (81%, over `max_load`), and the report didn't say so. |
| 146154-146340 | Walked zone by zone to **Joppa** (no world-map step). Argyve: gave the small violet tube (+75 XP) and kept the unidentified weird artifact. Tam: sold about 20 spare weapons and 7 spare armour pieces (197 drams) and bought chain mail, leather boots and 20 arrows, ending 96 drams of water ahead (106 carried). Cooked a meal. |
| 146400 | North outskirts, a glowpad: **level 5**. "Your genome enters an excited state!": a forced rapid advancement, Freezing Ray 3 to 6. Held there; 164 SP and 1 MP unspent. |

Explore hand-overs over the session (narration log): 4 zone explored, 4 "unexpected", 4 "stuck", 2 level up,
2 near known danger, 1 each of terrified, upgrade, under fire, close fight, outnumbered, armour, new enemy
joined, avoid enemy, new enemy, goal. **8 of the 23 (the "unexpected" and "stuck" ones) were our scripts'
fault, not the game's.**

## What went well

- **No deaths, and both deadly encounters were read correctly from the numbers.** The level-21 slumberling
  was left asleep. The Firesnarler was fled twice before contact, with the escape route chosen to break
  line of sight. That is "learning over avoiding" done right: avoid what is hopeless by the numbers.
- **Hard fights a turn at a time, re-reading the board each time.** The three-way fight: the dreadroot
  first (its terror spoils moves), then the ray where its smallest roll still kills, then letting the
  last scavenger come. The spider in water: ray first.
- **The town visit followed the lessons.** Every shop's stock was read and judged against the character:
  the empty feet slot filled, chain mail for DV, ammunition for the bow. Surplus was sold in one combined
  trade (the rounding lesson). The free meal was taken while Hungry. The unidentifiable weird artifact
  was kept rather than handed over blind.
- **Ranged weapon:** the bow from a chest went into the empty missile slot at once (lesson from Uumurem).
- **The new tools paid off:** `tools/brief.py` at every hand-over, `--say`/`--think` on actions,
  `research/controls.md` (the walk-to-stairs prompt used six times).
- **Tests from real states:** new replay cases and checks for the glowpad flip-flop, danger breaking a
  commitment, pacing, sighting stops, gear give-ups, the chest flow (two real screen sequences), the chest
  menu, swim rules, and world-neutral feature kinds. All passing; vet 0 failing of 460.
- **Owner rules captured as they came,** in lessons.md: fix our own broken scripts live outside a recorded
  run; what we accept depends on how sure we are of what's around (swimming); committing to a target
  must never mean walking past danger.

## What went wrong, and why

Each item is checked against lessons.md and game_facts.md: a **regression** (we knew better) or **new**.

### Bot behaviour
1. **Target flip-flop for 40 turns** (new). The fight routine re-picked its target from what was in view
   on every call. The no-progress failsafe missed it because the answers alternated. Caught by the owner,
   not by the bot. Fixed (commitment plus pacing hand-over), not yet seen live.
2. **The explorer abandoned areas over its own bugs** (new as a rule; the owner: never give up on an area
   because of our own scripts). Causes: "You see X and stop acting" counted as stuck; unreachable loot
   forgotten on every plan change; gear give-ups counted as stuck; chests never opened since the start of
   the project (a gap against "Loot everything"). Fixed live; mostly seen working.
3. **"Avoid" is a static radius round the last sighting** (partly a regression: "know where hostiles are
   even out of view", "pursuers follow across zone edges"). The explorer walked back towards the
   Firesnarler, a mobile smell-tracker. Not fixed.
4. **False "unexpected" stops** (new): "the glowpad is stunned" (twice, two wordings) and the camp meal's
   own text. Each is one restart, but a viewer sees the bot halt for nothing. The glowpad one was patched
   in data. The meal text is not fixed.
5. **A walk swam into deep water** (regression against AGENTS.md "never path through deep water"; the rule
   was later reframed by the owner as context-dependent). The torch went out, and nothing noticed. Fixed:
   the walk stops, swimming only when safe, torch relight added (not seen live yet).
6. **The overloaded sweep stopped silently** (new): "picked up 0 item(s)" with no word that the load limit
   (80%) was the reason. Found only by simulating it.
7. **Hunger:** the explorer didn't cook while Hungry twice; I cooked by hand both times. Cause not
   investigated (the cook's "hostiles nearby" check counts ones out of sight?).
8. **`tools/profile.py` misread the skills** after the Skills page groups were collapsed, so the saved
   profile lists only Long Blade. `threat.skill_bonus` doesn't know Long Blade Proficiency, so the
   estimate under-rates the sword. Both new; not fixed. The profile wasn't recorded at levels 4 and 5.
9. **`tools/menu.py item ... look`** cut the description short (new; worked round by hand).
10. **The snapshot lists at most 300 features** (new; a mod cap). Deep water round the player went missing
    in a busy zone.
11. **Charge "no clear line" from 4 cells**, then it worked on the next try. The unvetted "Charge only
    from 3-4 cells" is mixed: a wall may still block from 4.
12. **The ray did no damage to two dreadroots in its line** (only "freezing"). Unexplained; not
    investigated.

### My own process
13. **I edited live scripts while the bot ran, and crashed the run** (regression: game_facts.md said
    "compile before the bot can run it"). The brain reloads the scripts on every call. Now written down:
    hold the run first.
14. **The first chest routine picked up the chest itself.** I'd assumed a "g) get" after the last item
    was an item's menu. It came from real play the same hour; my replay tests covered only the screens I
    had pressed through by hand.
15. **The swim fixes shipped with two flaws found only live** (a stale message read as new, sightings never
    aging). Each was reasonable in isolation, but neither was tested against the message log's memory or
    the world file's real age data.
16. **PowerShell quoting broke inline `python -c` three times** (regression: game_facts.md "editing
    pitfalls"). Writing a scratch script each time worked.
17. **I paused the bot for a non-problem once** (checking remembered dragonflies looked like another
    flip-flop). It was cheap, but I could have read the code first.
18. **The replay case `gear_giveups_are_not_stuck` doesn't discriminate:** it reads the live world file,
    which already holds the give-ups.

### Judgement calls worth the owner's view
- **Giving Argyve the violet tube unidentified:** no one in Joppa can identify artifacts. The tube looked
  like a consumable tonic; the weird artifact is priced 57 drams.
- **Freezing Ray for the level-5 rapid advancement** over Multiple Legs.
- **Skill points spent on Long Blade at level 3** (100 SP) because the found sword happened to be a long
  blade.

## Unvetted changes: what live play showed

| Change | Seen live? |
|---|---|
| brief.py, --say/--think | **Working**: used throughout |
| Walk stops at deep water | **Working**: stopped twice, correctly |
| Walk ignores rooted dangers 2+ away | **Working**: walks past glowpad pools |
| Sighting stops retried | **Working**: dragonfly zone explored to the end |
| Unreachable loot kept per zone | **Working**, then superseded by deep/expiring give-ups |
| Container opening | **Partly**: an empty chest opened and closed cleanly; the chest-menu bug fixed after, not re-seen |
| Fight commitment / pacing hand-over | Not seen again (no recurrence; also not exercised) |
| Swim when safe, torch relight | Not seen: we left the zone right after the fixes |
| World-neutral feature kinds | Not seen: no new named feature this stretch |

## Proposed fixes (not applied; for review)

Bot code, each to be vetted and replayed:
1. **Mobile avoid kinds:** treat a known avoid hostile that moves (and tracks by smell) as a zone-level
   danger. Hand over, or keep the explorer out of the whole area it was last seen in, instead of a
   12-cell circle round its last cell. Add the Firesnarler states as a replay case.
2. **Camp-meal text** ("You gather whatever you can find for your meal ... stir") as known cook messages.
   Freeze the hand-over state as a case.
3. **Say why a sweep ends:** "load 81% of capacity: not picking up more" in the zone report and the
   hand-over.
4. **Hunger:** find why the explorer didn't cook while Hungry (two cases this session).
5. **`tools/profile.py`:** expand every skill group (Keypad6 on each `[+]`) before reading. Then re-record
   Siwur's profile.
6. **`threat.skill_bonus`:** add Long Blade Proficiency once its effect is confirmed (the wiki, or the
   rolls in our records).
7. **`tools/menu.py item ... look`:** capture the whole description popup.
8. **Replay isolation:** run cases against a fresh copy of the world file (or one frozen with the case), so
   `gear_giveups_are_not_stuck` and the like discriminate.
9. **Investigate** the ray's zero damage on the chilled dreadroots, and Charge's "no clear line" from 4.
10. **Mod batch** (needs a game restart): raise the features cap and list the nearest cells first.

Process:
11. Hold the run before any script edit (done as a note; could be enforced: step.py refusing to load a
    script that fails to import, with a clear hand-over instead of an exception stop).
12. Write scratch scripts instead of inline `python -c` from PowerShell.

## Proposed operations (not done; for the owner)

- **Commit** this session's work, then **push** with the pending `11f53a4` and `4145186` after the PII scan.
- **Points at level 5:** 164 SP and 1 MP unspent (the next goal is the owner's).
- **Leftover loot** in marsh zone 11.21.0.1: a waterskin, loot across deep water (now fetched when safe),
  and the wet chest.
- **Identify the weird artifact** somewhere that can (a vendor with the skill), then decide on Argyve's
  second knickknack.
- **Open quests:** the watervine vermin (a girshling corpse, deeper in Red Rock, past the Firesnarler);
  Namritara Glassfold; Ekavuh.
- **Fight review** (`python tools/fights.py --since 142586`), retro step 5, not yet run. Then update
  unvetted.md with the table above.
- **Fixtures still to freeze:** the Firesnarler walk-back, the meal-text and glowpad-stun hand-overs, and
  the overloaded silent sweep.
