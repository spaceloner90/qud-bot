---
name: narrate
description: Qud bot narration rules. Use whenever the Qud bot's narration is on (live/voice_on exists), before and while acting for the bot or working on its code, so the user hears and reads what is going on.
---

# Narrating the Qud bot (the user, 2026-11-24)

While `live/voice_on` exists, the user follows the run by ear (the voice) and by the bot panel (the log).
Silence for minutes reads as "broken". Two channels, not 1:1:

- **Voice**: `python tools/say.py "<line>"`, spoken aloud. Short, plain speech, one or two sentences.
- **Panel log**: `python tools/think.py "<line>"`, the written train of thought. Can be longer and carry numbers.

## When to speak (voice)

- **Every decision I make**, with its reason, before or as I act: "One salve, no more: the checkpoint is
  close." Not "Trading" or "Fighting": what and why.
- **After a hand-off**: the bot says "Pausing to think: ..."; my first voice line is the decision.
- **While I work without the bot acting** (reading code, editing scripts, writing notes): say what I'm
  doing and why at the start ("Teaching the fight routine to hold position, so it stops walking into
  packs"), and again at least every 20-30 seconds of work, or when I finish ("Done; back to the fight").
- **Results**: kills that matter, XP milestones, a plan that worked or failed, a lesson learned.

## When not to

- Not routine repeats ("exploring to the next enemy"), not raw numbers lists, no file paths or code.
- Don't talk over the bot's own lines: one line per decision, not a running commentary.

## Panel log

Write a `think.py` line for each real decision (objective/goal changes, fight calls, what a review
found), so the log reads as a thought train with the objective on top.

A PostToolUse hook (`.claude/hooks/narrate_check.py`, wired in this project's `.claude/settings.json`) reminds me when the voice has been silent for 25 s
or more while narration is on. When it fires: say what I'm doing now, in one line, then carry on.
