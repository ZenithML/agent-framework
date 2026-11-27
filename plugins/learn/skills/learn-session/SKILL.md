---
name: learn-session
description: >
  Use when a learner wants to study or practise now: plans a session sized to their time with
  due reviews first and new frontier concepts next, tutors each item Socratically with a hint
  ladder, grades every answer against an objective check, and records the evidence. Does not
  trigger for placement of a new learner or for setting goals.
---

**Usage:** `/learn:learn-session [minutes]`

`LEARN` means `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/learn.py"`. Follow
[`standards/tutoring.md`](../../standards/tutoring.md) throughout; the rules there override
anything that seems faster.

## Step 1: Plan

Run `LEARN plan` (add `--minutes <n>` if the learner gave a time). It lists steps of three
kinds:

- **review**: a concept whose memory is fading. Practise retrieval: one item, no teaching
  first.
- **learn**: a new concept whose prerequisites are in place. Teach, then practise.
- **confirm**: a concept that looks known but has not been shown on an unseen item. One item,
  no teaching first.

Tell the learner the plan in one or two lines. If the plan is empty, run `LEARN status`, say
why (nothing due, frontier blocked) and offer `/learn:learn-goal` to widen the goal.

## Step 2: Work each step

For each step, with its item id:

1. Run `LEARN item <id> --tutor` and read it yourself. It shows the prompt, the hint ladder,
   the reference and, for data items, the ground truth. Everything under `TUTOR ONLY` stays
   with you.
2. Show the learner the prompt, options or steps, and the dataset's tables. Do not show
   anything from the tutor section.
3. For a **learn** step, first ask what they already know about the concept. If they have no
   foothold, give a short worked example on different data (another host, another rule), then
   return to the item. Ground the explanation in the item's explanation and the pack's
   sources.
4. Ask for their confidence (0 to 1), then their answer. For data items, run the queries they
   ask for with `LEARN query --item <id> "<SELECT ...>"`, and let them iterate before they
   submit.
5. Grade: `LEARN grade <id> --answer "<answer>" --hints <rungs given> --confidence <c>
   --skill learn-session` (`--answer-file <path>` for a Sigma rule; write their YAML to a file
   in the scratch area first).
6. If it is wrong, use the feedback (recall, false positives, how many orderings were right)
   to ask a question that points at the gap, then give the next hint rung if they want it, and
   let them resubmit. Retries stay on the same dataset.
7. After two graded attempts and two hints, offer to reveal. Only if they accept, run
   `LEARN reveal <id>` and walk through why the reference works. Then move on; the planner
   will bring the concept back with another item.

## Step 3: Teach-back (learn steps only, when time allows)

Ask the learner to explain the concept in three or four sentences, as if to a new analyst.
Judge it against the concept's can-do statement and the item's explanation. Record it:
`LEARN record <id> --kind teach-back --grader rubric-llm --score <0-1> --note "<one line>"`.
Score what they said, not what they meant.

## Step 4: Close

Run `LEARN status`. Tell the learner, in two or three sentences, what moved (kept, fading,
still learning), anything flagged as a misconception or a prerequisite to check, and when
reviews come due. No praise for effort; name what they can now do.
