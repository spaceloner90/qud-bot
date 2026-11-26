# Retrospective: Siwur (died at level 1, 65 XP), 2026-11-26

The restart character for the recording. Died at turn 141435, about 700 turns in, to a snapjaw scavenger
(3 HP) in the salt marsh south of Red Rock. The user: "run failed against some fairly beatable enemies."
Everything that killed us was beatable; the failure is in my sequencing, not the bot's estimates.

## Timeline

| Turn | Event | HP after |
|---|---|---|
| 140726-141071 | Joppa explored (copper nugget, 2 bedrolls), Elder, Mehmet, Argyve: both quests | 18/18 |
| 141371 | World map: second step north got us lost, dropped into the salt marsh | 18/18 |
| 141372-141377 | A giant dragonfly swooped and landed; I meleed it: 6 HP lost for 1 damage, then the ray and the axe | 9/18 |
| 141377-141379 | Handed back to explore at 9/18; it "held" for a scavenger, which crit | 6/18 |
| 141379-141391 | A snapjaw warlord (20 HP) came; crossed the south edge to rest; it followed and broke the rest | 8/18 |
| 141391-141419 | Kited by hand: ray killed a scavenger and hit the warlord; teleport out of a strip boxed in by water; two more scavengers killed; second ray | 14/18 |
| 141420-141422 | Meleed the slowed warlord "while the freeze lasts": two misses (its DV 11), bites from both | 7/18 |
| 141423-141435 | My scratch kite loop swam into deep water by a croc; walking north at 8 HP into a scavenger, crit for 7 | dead |

## Why it failed

1. **Every fight after the first started hurt, and I never reset.** The dragonfly took us to 9/18 and
   from then on nothing began above half HP. The fix was available each time: break contact, rest to
   full out of sight, then engage. I handed back to explore at 9/18 with hostiles in view instead.
2. **I ignored the lessons I already had.** Oshwoshwuur beat a warlord losing 4 HP by waiting for ray and
   Charge, then engaging at full HP (retro_oshwoshwuur.md). I fought this one with the ray on cooldown,
   then went into melee at 14/18 against DV 11, where a level-1 character misses half its swings.
3. **The dragonfly in melee.** I knew "ray first" and still swung the axe first: three turns, 1 damage,
   6 HP lost. That first fight set the HP deficit for everything after.
4. **Hand-written loops instead of the vetted tools.** The confusion lesson was "every wait via
   tools/wait.py, no hand-written loops in fights" (two earlier deaths). My scratch kite script had
   none of the tools' checks: wrong terrain glyphs walked us into deep water next to a croc, and its
   last move stepped into the scavenger's reach.
5. **No healing between fights.** After the dragonfly nothing followed us, and I didn't rest to full.
   Bark was not the answer at 7/18 (the user: confusion mid-combat is as dangerous as we know it is);
   resting at each break in contact was, so we never reach 7/18 with enemies around.

## The bigger point (the user): regression, not new mistakes

These were all past learnings: hard fights a turn at a time, re-examining until it's safe to defer to
the scripts (design.md); terrain and better pathing (design.md, the deep-water lookup); pursuers cross
zones (memory qud-fight-lessons-maggatum, playbook). The Maggatum lessons were even indexed in my
loaded memory. I batched a chancy fight into loops, parsed terrain from glyphs, and treated a zone edge
as safety. Fix: qud-bot/CLAUDE.md now has a "When I play a fight myself" section that makes these rules,
not background reading.
6. **Escapes that didn't escape.** Pursuers cross zones (the Maggatum lesson): crossing the edge to rest
   bought 12 turns and ended with the warlord adjacent. Distance plus a heal would have worked better
   than an edge crossing.
7. **Upstream: lost on the world map** dropped a level-1 character into a busy zone. Unlucky, but a
   known chance on every world-map step.

## What would have worked (by the numbers we had)

After the dragonfly: rest to full where we stood (nothing hostile followed then). Scavengers (3 HP)
die in one or two hits at full HP. The warlord: wait at full HP with ray and Charge ready; ray when it
comes into line, Charge, melee, one action at a time; back off over known dry ground as it thaws, repeat
at the next ray.

## Changes to make

- The fight routine and my hand-overs: below ~60% HP with a mobile hostile coming and no cooldowns
  ready, the first move is to break contact and heal, not to fight.
- No scratch movement loops in fights: kiting goes into a vetted tool (tools/kite.py built from
  walk_check and wait.py's checks, deep water blocked), vetted before use.
- Rest to full at every break in contact while hurt; bark only with no enemy near.
