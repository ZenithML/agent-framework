# Learner model — Standard

The one record of what a learner knows. Every learn skill reads and writes it through
`scripts/learn.py`; nothing else touches the files.

## Stored records

State lives in `$LEARN_HOME`, or `./.learn` when unset. Plain files, so a learner can read,
move, back up or delete all of it.

| File | Holds | Changes |
|---|---|---|
| `learner.json` | installed pack, preferences (session minutes, weekly minutes, desired retention) | learner-owned |
| `goals.json` | goals: statement, concept ids, target date, why, success test, status | learner-owned |
| `evidence.jsonl` | one graded record per line | append-only, idempotent on `id` |
| `work/<scenario>-<variant>.db` | generated datasets the learner queries | disposable, rebuilt from the seed |

An evidence record:

```json
{"id": "uuid", "at": "2026-11-21T20:10:00+00:00", "item": "spray-2", "variant": 1,
 "concepts": {"soc.detect.spray": 1, "soc.siem.aggregate": 0.5},
 "kind": "attempt", "score": 1.0, "grader": "sql", "grader_confidence": 1.0,
 "hints": 1, "seconds": 300, "confidence_before": 0.6, "error_tag": null,
 "session": null, "skill": "learn-session", "detail": {"recall": 1.0, "false_positives": 0}}
```

`kind` is one of `attempt`, `diagnostic`, `teach-back`, `project`, `self-report`, `reveal`,
`exposure`. `grader` is `choice`, `exact`, `sql`, `sigma`, `order` (objective), `human`,
`rubric-llm` or `self`.

## Derived views

Recomputed by replaying the evidence in time order on every call. Never stored.

| View | Rule |
|---|---|
| P(known) | `(1 + successes) / (2 + successes + failures)`, each record weighted by concept weight × grader confidence × hint factor (`1 − 0.25 × hints`, at least 0.25) |
| Memory | FSRS-4.5 per concept, from primary-concept records with grader confidence ≥ 0.6. Score ≥ 0.9 with no hints is Good, ≥ 0.6 is Hard, below is Again |
| Prerequisite credit | A success on a concept counts as an implicit Good review of each direct prerequisite whose retrievability has dropped below 0.9. A failure marks the prerequisites to check |
| Placement inference | A diagnostic success adds 0.5 success to every ancestor; a diagnostic failure adds 0.5 failure to every descendant |
| Mastered | P(known) ≥ 0.8, at least 2 primary records, one hint-free success on an item never seen before (a revealed item counts as seen), and retrievability ≥ 0.85 |
| Fading | Meets the mastery criteria except retrievability, which has dropped below 0.85 |
| Frontier | In scope, not mastered or fading, P(known) below 0.8, and every prerequisite at P(known) ≥ 0.65 |
| Due | Retrievability below the learner's desired retention (default 0.9) |
| Misconceptions | Error tags per concept: suspected (once), confirmed (twice), resolved (a later success) |

## Grader confidence caps

| Grader | Cap |
|---|---|
| choice, exact, sql, sigma, order | 1.0 |
| human | 0.9 |
| rubric-llm | 0.6 |
| self | 0.3 |

A caller can lower a record's confidence but never raise it above the cap.
