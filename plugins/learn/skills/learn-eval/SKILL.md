---
name: learn-eval
description: >
  Use when the learn plugin's tutoring skills or a subject pack changed and their pedagogy must
  be checked before learners see them: runs the pack content gate, then plays three simulated
  learners against the session skill and scores the transcripts against the tutoring standard.
  Does not trigger to teach a real learner.
---

**Usage:** `/learn:learn-eval [pack]`

`LEARN` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/learn.py"`. The rubric is
[`standards/tutoring.md`](../../standards/tutoring.md). Scenarios are in
[`evaluations/baseline-evals.json`](evaluations/baseline-evals.json).

## Step 1: Content gate

Run `LEARN pack check <pack>` (default `soc-foundations`). It checks the concept graph, that
every concept has at least two items, and that every reference answer passes its own grader on
three generated variants. Any `FAIL` stops the evaluation: report the failures.

## Step 2: Simulated learners

Use a throwaway learner home so no real evidence is touched:
`export LEARN_HOME=$(mktemp -d)`, then `LEARN init --pack <pack>`.

For each scenario in `evaluations/baseline-evals.json`, run the session skill's procedure for
the named item while you, or a subagent if the host offers one, play the persona exactly as
described. Save each transcript to `$LEARN_HOME/transcripts/<scenario id>.md`.

## Step 3: Score

Score each transcript against every `must` and `must_not` in its scenario, quoting the line
that shows each verdict. Also check the evidence log (`$LEARN_HOME/evidence.jsonl`):

- every graded answer in the transcript has exactly one record, with the hints that were given;
- no record exists for an item the persona did not attempt;
- a `reveal` record exists if and only if the reference was shown.

## Step 4: Report

Print a table: scenario, verdict (PASS or FAIL), and the quoted evidence for each failure.
A single FAIL fails the evaluation. Do not change the skill to make it pass in the same run;
report and stop.

### Files in this skill

- `SKILL.md`
- `evaluations/baseline-evals.json`
