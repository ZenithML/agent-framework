---
name: architect
description: >
  Use when resuming a pipeline that halted or escalated, or when debugging one stage's handoff
  in isolation — the internal control plane, invoked directly rather than through /sdd:ship.
  Does not trigger for a normal change (use /sdd:ship, which spawns it with the right
  arguments), and does not trigger to run a single stage cleanly (use that stage's skill).
---

**Note:** This is the internal pipeline orchestrator. For normal use, invoke `/ship` instead — it calls this skill automatically.

Invoke the architect directly only to resume a failed pipeline or debug a specific stage.

## Pipeline stages

| Stage | Skill (direct invocation) | Agent | Output |
|-------|--------------------------|-------|--------|
| 1 — Spec | `/spec <domain>` | `planner` | `requirements.md` [critic embedded] |
| 2 — Plan | `/plan <domain>` | `planner` | `design.md`, `tasks.md` [critic embedded] |
| 2b — Tasks only | `/tasks <domain>` | `planner` | `tasks.md`, GitHub issues |
| 3 — Implement | `/implement <domain> <task-id>` | `executor` | Tests + implementation (TDD) |
| 3b — Code critique | `/critique code <domain>` | `critic` | PASS/REVISE |
| 4 — QA | `/qa <domain> <task-id>` | `tester` | PASS/FAIL report |
| 5 — Publish | `/publish <domain>` | `publisher` | docs verified, PR opened, CI passing |

Each stage is self-contained and can be run independently. The architect runs them in sequence with context isolation between stages.

## Invocation

Spawn the `architect` agent with the feature description and flags provided.

Pass the full feature description and `--autonomous` flag (if provided) to the architect agent.

See `${CLAUDE_PLUGIN_ROOT}/agents/architect.md` for the full orchestration spec.
