# Fight reviews

Made with `python tools/fights.py --since TURN` (fights cut from the game's message stream; per fight:
HP, damage taken and dealt, kills, actions, wasted actions, effects, hand-offs, flags). Done as part of
taking stock (research/taking_stock.md). Each finding becomes a change, a note, or an explicit "accept".

## 2026-11-24, turns 51600–52001 (Red Rock stratum 3 after Joppa: chain mail, steel axe, musket)

Six fights, 0–6 damage taken each (HP never below 21/27), kills: 2 giant amoebas, 3 seed-spitting vines,
2 jilted lovers, 1 dreadroot. The new gear works; the waste was in the routine.

| Finding | Change |
|---|---|
| Reloaded at the start of 3 fights (the musket sat empty between fights) | explore reloads in downtime: empty missile weapon + ammo + nothing hostile in view → `CmdReload` |
| 2 shots into shale (no clear line to the target) | a shot or ray hitting something else holds fire at that target for 10 turns (fight.py `no_shot`) |
| Charge retried 4× with no clear line | the same line rule now covers Charge |
| Freezing Ray dropped back to the abilities list (blocked) and explore stopped on the "popup" | ability.py backs out with Escape and reports "no clear line" |
| Hand-offs for things now routine: giant amoeba (avoid), "fails to penetrate the shale", crits, armour cracked, leaking | amoeba → fight + shoot; those messages are ordinary |
| Terror from a dreadroot's aura while a vine was shooting us (51885) | dreadroots are killed on sight (fight + harmless; ray from range or the axe, no ammo); terror with only harmless kinds in view is waited out |
| Musket used on easy enemies would waste scarce slugs | shoot only dangerous kinds / when hurt / kinds marked shoot; reserve of 10 |
| Under fire from out of view (the vine, 51885) raised the LLM | accepted for now: stepping towards an unseen shooter is a judgement call |

Open questions for the next review:
- Do we see the line of fire before shooting? The picker draws the path; the first wall hit still costs a slug.
- Does the downtime reload and dreadroot-on-sight rule show up in the next fights (flags gone)?

## 2026-11-24, turns 54392–54496 (Maggatum and the desert canyon south of it; level 5 → 6)

Two phases (tools/fights.py): 54393–54442 dealt 172, took 56, 15 kills (+324 XP: chameleon 125,
tortoise 125, the rest 5–12 each), HP 30 → 6 at worst; 54455–54496 dealt 23, took 36, 1 kill (the
amoeba, which gave level 6), HP 19 → 4. Teleport landed one cell away; ubernostrum and two salves
kept us alive. Reviewed autonomously first, as the user asked; the user then corrected the main lessons (marked below).

| Finding | Adjustment |
|---|---|
| ~~Went in without checking the site's XP; low-XP swarms should be avoided~~ **Wrong conclusion (the user):** the first fight (3 dogs + 2 amoebas) was winnable and would have given us a foothold in the area; "never engage" would bar the area forever | When there's no safe way to retreat, sticking it out can be the best option; judge a group by whether we can win it, not by its XP |
| **The big one (the user): pursuers follow across zones.** Dogs and an amoeba crossed the edge after us; out of sight is not safe. We stopped in the second zone and engaged the chameleon at once, then dragged its tortoises back into the first zone | After fleeing over an edge, assume the pursuers are right behind: keep moving away (or turn and fight at the edge on our terms), never start a new fight in the new zone; remember who was chasing |
| Running blindly in hostile areas pulls more enemies in; we moved into a corner against the tortoises, and the escape steps led us into more attacks | When forced to escape blindly, beeline in one feasible direction that doesn't pass enemies. No multi-step auto-pathing (GOTO/WALK/"walk to the edge") in the middle of a fight: step by step, re-reading the board each step |
| Irritable tortoises: "tightens his carapace" made even musket slugs fail (4 in a row); the axe mostly "doesn't penetrate" | Learn armour dynamically, not just per-kind notes (the user): the game's own numbers say how hard a target is (our penetration rolls vs its AV, see design.md "Reading armour"); pick the weapon that can get through, and know a carapace can be loosened |
| My priority loop attacked an empty cell for 4 turns after a dog died (stale target) | Loops re-read positions every step (they do now) and never repeat an attack whose target cell is empty |
| The kite loop oscillated N/S beside slow tortoises instead of gaining distance | Kiting picks a direction once (away from the slow group) and keeps it for several steps |
| Teleport was spent with the cursor 12 cells out; it landed 1 cell from the start | Teleport's uncertainty radius is 12: aim 15–20 cells away, at known open ground, to make a near landing unlikely |
| Look on the horned chameleon showed nothing (cursor maths or camouflage?) | Still to test: Look at a visible creature with the same cursor maths; if it works, the snapshot should flag creatures the player can't see |
| Two run stops from my own malformed keys (empty KEY, shell quoting) | send.py and macro.py now refuse malformed lines |
| Menus were slow (one key per round trip) | Build menu macros (item by name → action, trade by list) right after this fight (the user) |
| Healing items: ubernostrum heals 3/turn for ~10 turns; salve about the same for ~4 turns; applying took no turn | Noted in the world file; use them before HP 10, not at 5 |

## 2026-11-24, turns 54861–54993 (Maggatum again, after the reload)

The south-edge stand worked: two amoebas and four feral dogs died one at a time (HP 30 → 10, one salve).
Then I walked north "to cover" to rest and met the north group (amoeba, guard dog): HP 3, Teleport.

| Finding | Adjustment |
|---|---|
| **Left a good position (the user):** standing still regenerates even when the game refuses to rest, and enemies that come to us come one at a time into our position; walking to "better" cover took me into the next group | Hold the position that is working. Wait (CmdWait) to regenerate rather than move to a rest spot through unexplored ground; lure with a shot and step back rather than walk out |
| **Under-armoured (the user):** amoebas hit (x2)/(x3) for 4-5 because AV 4 lets most penetration rolls through; face, arms, hands, feet and back slots are empty | Next town trip: fill every empty armour slot, even AV 1 pieces |
| Teleport aimed 19 cells off landed 8 away, but behind a wall and out of sight; nobody followed | Aiming far still works; the landing is random within 12 |
| The stand's "hold" option (fight.py) shoots, rays and swings but never walks in | Keep it for stands |

## 2026-11-24, run 2 (claudio2), turns 110599–110664: death on Red Rock stratum 1 at level 1

The fight routine killed a cave spider (+50), then engaged a giant amoeba: Freezing Ray, Charge, then
axe blows of 1 damage against its 5 and 7 (crit, dazed). HP 18 → 3 in about four turns. I backed off
west toward the stairs up (amoebas are slow); it followed around the corner and stood next to the
stairs, and my step loop walked onto the stairs beside it. Killed at turn 110664.

| Finding | Adjustment |
|---|---|
| **The shared verdict was wrong for this character (the user's warning, the same day):** "giant amoeba: fight, shoot" was judged at level 5 with a musket and chain mail; at level 1 (furs AV 2, bronze axe 1d2) it out-damages us about five to one | Verdicts get a level floor: below it the kind counts as avoid. Set from run 1's record: giant amoeba 4 (it nearly killed us at 2 and 3), defanged girshling 5, guard dog 5, horned chameleon 5, irritable tortoise 6 |
| My retreat loop checked only "map, alive" each step, so it walked onto the stairs next to the pursuer that had reappeared | A retreat step stops when a pursuer is adjacent to the next cell or already adjacent to us; then re-decide (Teleport at HP 3 was the right call then) |
| Charge opened on a dangerous target | Follows from the level floor: Charge and melee only go at kinds we fight at this level |

## 2026-11-24, Kamet (Classic), turns 13526–15211: Joppa to Red Rock stratum 2, stopped by the user

The user's verdict: a lot went well; the generation was unlucky (a named snapjaw hero, 74 HP, camped by
stratum 2's stairs), and we had nothing for "something far too strong stands in the way".

| Went well (keep) | |
|---|---|
| Getting lost in the marsh | explored the zone, walked on a zone in the right direction, bearings back |
| The croc | the estimate stopped us (9 vs 7); fought it deliberately from a held spot, ray first, barks as the backup: no bark needed |
| Spider + shooter | stepped out of the vine's line, waited for the ray, killed the jilted lover, then the vine in one blow; the spider later |
| The amoeba | with the sword the estimate was 6 vs 5; ray (freeze), hold, swing: killed it without the kite |
| The sword | compared by the game's penetration rule (1.7-2x the axe) before switching |
| The snapjaw pack | crits took us to 7; bark at once (Classic: death is final), stairs out while confused |

| Missing / to fix | |
|---|---|
| **A blocker we can't beat** (hero at the only way on) | No notion of giving up an objective and going elsewhere. Needed: mark the objective blocked (by what, at our level), pick another lead, come back when the estimate says we can win |
| Snapjaws bite up through the stairs | Rest away from stairs cells (two cells off was enough) |
| Plan relabel before a zone change | Re-ran the explore stage in the old zone twice: change zones first, then the plan |
| Speed fields need a game restart | "kite" can't fire until the v0.21 mod is loaded |

## 2026-11-24, Yaun (Classic), turns 27926–28579: death to a hulking baboon at level 1

Went well before it: Joppa explored and both quests in about 300 turns; Tam's prices read (weird artifacts
at 57 would finish Argyve's quest); leather armour bought with the trade macro (first live run, 5 s);
lost twice, walked out both times; a croc killed from a held spot with the ray (-2 HP); walked into Red
Rock's outskirts (+50).

The death: a hulking baboon (15 HP, AV 3, DV 0, never fought before, so no damage data). I accepted
it "like the croc": hold, ray first, hand over at 50%. It arrived, bit (x5) for 9 (HP 18 -> 9); the
routine rayed it point-blank; it bit (x6) for 9. Two turns.

| Finding | Adjustment (proposed, not built) |
|---|---|
| **I accepted a kind with no damage data** at level 1 in Classic, by analogy with the croc | Unknown damage = unknown danger: at low level keep it at range (ray, step back) until its first hits are seen, or avoid; "hulking" was a hint |
| The hand-off was "HP below 50%"; 9/18 is exactly 50%, and one bite was 9 | Hand over when HP is at or below **twice the largest hit seen this fight**, not a fixed fraction |
| The estimate needs 3 attacks of a kind before it counts | Inside a fight, this fight's own hits count at once: after one (x5) for 9 it would have said "two turns to kill me" |
| Look still doesn't work from the bot (its cursor ignores keys) and left the panel open, freezing all input for minutes | Fixed the freeze: the brain closes a stray Look panel. Look itself still to fix |
| The game wasn't fully restarted, so no creature level or speed in the snapshot | Restart the game after mod changes; the baboon's level would have flagged it |

## 2026-11-24, Oshwoshwuur (Roleplay), turns 203126–204479: death on Red Rock stratum 1 at level 1

Went well: Joppa explored and both quests in ~300 turns; leather armour bought and the furs sold with the
trade macro; boots declined to keep drinking water; no getting lost (Red Rock by turn 204075); five
dreadroots cleared at the stairs; the new estimate stopped us at a vine (and said "kite", wrongly, for a
rooted plant); a vine, a jilted lover and dreadroots killed, +75; a bark at HP 8 finished a second vine.

The death: confused after the bark, I waited out the confusion **with a hand-written loop that only
checked for the confusion ending**. A biting creature (8 HP, 1d3 bite; name garbled by the confusion)
came up and bit us from 18 to 5 while the loop kept pressing wait. Then at HP 5 I chose the ray over a
second bark; the picker first aimed at ourselves (confused?), then the ray landed, but it bit once more
for 5.

| Finding | Adjustment (proposed) |
|---|---|
| **My manual loops keep missing what the scripts check** (the stairs walk on run 2, this wait) | No hand-written wait/step loops in fights: a tools/wait.py that stops on any new hostile, HP drop or popup, used for every wait |
| At HP 5 against a ~4-a-turn biter I picked the ray (which didn't stop the next bite) over a full heal | At HP <= 2 hits, heal first (bark), then act; freeze doesn't stop the target's current turn |
| "kite" for a rooted vine | kiteable() says no for things that can't move; the hand-over says "rooted: ray from range or leave its line" |
| The picker targeted ourselves while confused | Ability picks while confused: move the cursor to the target explicitly |

## 2026-11-24, Uubas (Roleplay), turns 156326–159967: killed by an exploding tumbling pod

Went well: Joppa fully explored; the explorer now empties containers autoexplore opens (no reaction from
anyone; a copper nugget and torches from Argyve's workbench); leather armour for 1 dram after selling the
nugget and scrap; Red Rock reached without getting lost; broke off from a level-5 hulking baboon
(stones, x3 for 5) and later a whole baboon troop at the entrance, both times without a fight.

Then a misclick took Uubas six parasangs north-east, lost in flower fields. Walking back south past two
horned chameleons worked; then a **tumbling pod** (level 2, 5 HP, two 1d2-1 "manipulators"; the game's
own word: **Tough**) caught up. The estimate said "2 turns to kill it, 61 for it" and I attacked. It
exploded when it died (8), the second pod beside it too (14): dead from full HP in one turn.

| Finding | Adjustment (proposed) |
|---|---|
| **The game's word ("Tough") was right and our estimate was wrong**: the estimate only sees melee attacks, not explosions, spores, ranged attacks or abilities | When the game rates something Tough or worse but our estimate says easy, the estimate is missing something: don't engage; hand over with both, and step away |
| Tumbling pods explode on death and chain | Game knowledge now: tumbling pod, avoid, "explodes when killed" (8 and 14 at level 1) |
| A misclick moved the character far from home | Outside the starting area, the bot only walks back toward it |
