---
name: learn-goal
description: >
  Use when a learner needs a learning goal set or changed: turns a vague aim such as "get
  better at SOC work" into concrete can-do outcomes from the subject pack, a target date, a
  weekly time budget, the reason it matters and a test of success, then saves it. Does not
  trigger to place the learner or to teach.
---

**Usage:** `/learn:learn-goal [the aim in the learner's words]`

`LEARN` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/learn.py"`.

## Step 1: Hear the aim

Ask what they want to be able to do, and why. Ask for a concrete situation ("triage our
SIEM alerts on my own", "pass the SOC analyst interview in January"). Keep it to two or three
questions; do not interview them.

## Step 2: Map it to concepts

Read the pack's concepts and can-do statements from
`${CLAUDE_PLUGIN_ROOT}/packs/<pack>/pack.json`. Pick the concepts whose can-do statements
match the aim. Prerequisites are added automatically, so choose the outcomes, not the
foundations. If the aim goes beyond the pack, say which part the pack covers and which it
does not; do not stretch a concept to fit.

## Step 3: Agree and save

Read back, in plain words:

- the outcomes (the chosen can-do statements),
- a target date that fits their weekly minutes (about 15 minutes per concept per week is a
  realistic pace for new material),
- how they will know they succeeded (for example "every chosen concept kept, and the
  detection items solved on fresh data").

When they agree, run:

```
LEARN goal set --statement "<their words>" --concepts <id,id,...> --target-date <YYYY-MM-DD> \
  --why "<reason>" --success-test "<test>" --replace
```

`--replace` retires the previous goal. Then suggest placement with `/learn:learn-diagnose`.
