# Conversations

What talking does in this game, learned by doing it by hand first (2026-11-24, Joppa). Script only what repeats.

## How a conversation works (mechanics)

- **Start:** stand next to the person (`GOTO` / `tools/approach.py`), `CMD CmdTalk`, then a raw direction key (`KEY RightArrow`, `KEY Keypad1` for diagonals...). The direction prompt is wait `key`.
- **The screen:** a box titled `[ Name ]`: their text, then numbered options (`> 1) ...`). It's all in the text snapshot, wait `key`. Pick an option with a raw digit key (`KEY 3`).
- **Option tags:** `[End]` closes it, `[begin trade]` trades, `[begin water ritual; 1 dram of water]` costs water, `[Accept Quest]` takes a quest.
- **A new quest** pops up "You have received a new quest, <name>!" with `[press space]`.
- **One key per screen.** On Argyve's screens I pressed `1` three times without reading, and the third press accepted a quest whose offer I hadn't read. Conversation options change from screen to screen.
- **The quest log:** `CMD CmdQuests` shows every quest with its steps as text; `KEY Escape` closes it. The snapshot's `quests` field errors until the mod fix (StringMap enumeration).
- **Odd text:** `♪` in conversation text is a carriage return shown as its CP437 symbol (mod glyph mapping; fix next batch).

## Joppa, first visit

| Person | Where | What they offered |
|---|---|---|
| Elder Irudad | hut north-centre (38,3) | Lore about Joppa (between the Great Salt Desert and the jungles of Qud to the east), wares, water ritual, trade. On "work", pointed to Mehmet (vermin) and Argyve (trinkets). Pays for the vermin quest. |
| Mehmet | south watervine patch (42,19) | **Quest: What's Eating the Watervine?** Go to Red Rock (2 parasangs north), kill the vermin eating the watervine (spider-like, seen in the brine; red shale flecks in the pool), bring a corpse back; the Elder pays. Also water ritual and trade. |
| Argyve, the tinker | sheet-metal hut, south-west (6,19) | Mumbles and dismisses us, then **Quest: Fetch Argyve a Knickknack**: find an artifact in the regions around Joppa ("scoop the surface of the marsh, or head east to the rust wells, or wander into the Desert"). |
| Not talked to yet | | Warden Yrame, Ctesiphus, Tam (dromad merchant), the farmers |

Generic pattern so far: most villagers share the same options (name, village, work, water ritual, trade, end). Unique content sits behind "work".
