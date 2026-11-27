# Level 1-5 runs: game turns and real time

Every character that did the run, from `live/log.jsonl` (the owner, 2026-11-27). Regenerate with
`python tools/level_runs.py` (its docstring defines each column) and add new characters here. Same
build each time: Mutated Human Marauder.

| Character (save) | Played | Game turns to 5 | Bot acting | With pauses < 10 min | Span, start to level 5 | Notes |
|---|---|---|---|---|---|---|
| Ushrorooshum (`7b7d009c`) | 24 Nov 02:51 → 19:22 | 6,323 | 1h46m | 3h37m | 16h30m | The first run; went on to level 6. Two reloads. |
| Shwyragaun (`bb75178b`) | 24 Nov 23:45 → 25 Nov 01:47 | 9,124 | 1h11m | 2h02m | 2h02m | Most turns: long escapes from a Snapjaw King. |
| Uubas (`5543fef9`) | 24 Nov 23:18; 25 Nov 15:00 → 16:34 | 6,770 | 1h03m | 1h19m | 17h15m | One reload; a break overnight. |
| Oshwoshwuur (`3cd5aab7`) | 24 Nov 23:06; 25 Nov 16:00 → 17:53 | 4,332 | 0h59m | 1h19m | 18h46m | Fewest turns; one reload; a break overnight. |
| **Uumurem** (`9b6c18ef`) | 26 Nov 00:53 → 01:45 | 6,064 | 0h48m | 0h52m | 0h52m | The published recording; one session, no reloads. |
| Siwur (`1f19697d`) | 26 Nov 00:22; 17:00 (Gemini); 23:00 → 27 Nov 01:17 | 5,674 | 1h23m | 1h54m | 24h55m | Died once (reloaded); Gemini played part; about 25 min of live script fixes. `retro_siwur_level5.md`. |

Didn't reach level 5: claudio2 (`19c1443b`, a test character), Kamet (`77cd0cd8`, Classic, died at level
2), Yaun (`f28ee73c`, Classic, died at level 1), Yim (`b6ea2b22`, restarted at level 1 after the
compacted session lost knowledge).

Measured 2026-11-27. Time is the snapshot's own clock. Steps inside the game's autoexplore aren't logged
one by one, so "bot acting" is approximate.
