---
name: learn-diagnose
description: >
  Use when a learner is new to a subject pack or says the material is too easy or too hard:
  runs a short adaptive placement, at most ten items, that finds where their knowledge stops,
  and records each answer as diagnostic evidence. Never teaches during placement. Does not
  trigger for ordinary practice sessions.
---

**Usage:** `/learn:learn-diagnose`

`LEARN` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/learn.py"`.

Placement measures; it does not teach. The learner should leave knowing where they start, not
having been shown answers.

## Step 1: Set expectations

Tell the learner: up to ten short questions, some with data to query, no hints, and it is fine
to say "I don't know" (that is recorded as a miss and is useful).

## Step 2: Loop

1. Run `LEARN diagnose`. If it prints `Placement done`, go to Step 3.
2. Run `LEARN item <id>` and show the learner exactly what it prints. For data items, they can
   explore with `LEARN query --item <id> "<SELECT ...>"`; run the queries they ask for.
3. Ask how confident they are (0 to 1) before they answer.
4. Grade with `LEARN grade <id> --kind diagnostic --answer "<answer>" --confidence <c>`
   (`--answer-file` for a Sigma rule). "I don't know" is graded as a wrong answer: pass
   `--answer "?"`.
5. Say only whether it was right. No explanation and no hint until placement ends; the item's
   explanation is printed on a correct answer and may be shown then.

Do not use `--tutor` during placement.

## Step 3: Show the starting point

Run `LEARN status` and `LEARN plan`. Tell the learner which concepts look solid, which are next
on the frontier, and what the first session holds. Then offer to start it with
`/learn:learn-session`.
