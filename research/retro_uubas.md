# Retry: Uubas to level 5 (2026-11-25)

Loaded at his Joppa-area checkpoint: level 1, 18 HP, bronze battle axe (1d2), leather armour. Run 1 of
him had died to exploding tumbling pods far north-east after a baboon troop blocked Red Rock. This time
Red Rock was skipped: only the salt-marsh tiles next to Joppa, zone by zone.

| Turn | Event |
|---|---|
| 156987 | Loaded on the world map at (12,21) |
| 158126 | Level 2 (glowpads by tools/siege.py hit-and-heal) |
| 158675 | Gnu herd (~18, level 12) + hostile chitinous puma in 11,21 east: straight to the world map |
| 158890 | Level 3 |
| 159545 | Walked back to Joppa on foot: checkpoint (the user's point), meal |
| 160462 | Level 4 (the fight routine's own siege) |
| 163096 | **Level 5** (tile 10,22 south-east) |

About 6100 game turns from level 1. Most XP: glowpads (25 each, dozens), glowfish (25), crocs (75).

Built or fixed during the run: tools/siege.py, then the siege inside the fight routine (rooted hostiles:
step out of reach below 60% HP, regenerate to full, back in; not a "long fight", no hand-over unless
under 25%); skip prey the estimate rejects; skip what needs a swim; stay holds time out; the idle
failsafe; eating/camping with only rooted enemies in sight; hunger clock for a loaded Hungry save; many
fight messages made ordinary (zone done, eating, camping, leaking, our bleeding). My mistakes: glowpads in
accept_kinds at level 1 (18 -> 8 with bleeding); two broken edits (a backslash through a heredoc, a
two-step edit) that stopped the run.
