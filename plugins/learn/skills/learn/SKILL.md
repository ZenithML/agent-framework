---
name: learn
description: >
  Use when someone wants to learn or practise a subject with a tutor that tracks what they
  actually know: start learning, see their progress, or ask what to study next. Shows honest
  progress from the evidence log and routes to goal setting, placement or a study session.
  Does not trigger to evaluate tutoring quality (that is /learn:learn-eval).
---

**Usage:** `/learn:learn [what you want to learn, or "progress"]`

The entry point of the learn plugin. It works out where the learner stands and hands over to
the right skill. Rules for talking to the learner are in
[`standards/tutoring.md`](../../standards/tutoring.md); the data model is in
[`standards/learner-model.md`](../../standards/learner-model.md).

`LEARN` below means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/learn.py"`. State lives in
`$LEARN_HOME`, or `./.learn` in the current directory.

## Step 1: Find the learner

Run `LEARN status`. If it says there is no learner yet:

1. Run `LEARN pack list` and tell the learner which subjects exist. Today that is
   `soc-foundations` (cyber resilience: SOC, SIEM, NDR).
2. Ask how long a session should be and how many minutes a week they can give.
3. Run `LEARN init --pack <pack> --session-minutes <n> --weekly-minutes <n>`.

## Step 2: Route

| Situation (from `LEARN status` and `LEARN goal list`) | Next |
|---|---|
| No active goal | `/learn:learn-goal` |
| Goal set, no evidence yet | `/learn:learn-diagnose` |
| Learner asked for progress | Run `LEARN report` and `LEARN status`, summarise in plain words: kept, fading, next |
| Anything else | `/learn:learn-session` |

## Step 3: Report progress honestly

When you summarise progress, use only what `status` and `report` print. Name concepts by
title, say how many are kept and which are fading, and what comes next. Do not count
sessions, minutes or streaks as progress.
