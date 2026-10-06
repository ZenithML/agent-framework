---
name: plan
description: >
  Use when a domain has an approved requirements.md and needs design.md plus tasks.md —
  architecture, decisions, test and QA scenarios, with critic review embedded. Does not trigger
  before requirements exist or are approved (run /sdd:spec first), does not trigger during a
  /sdd:ship run, and does not trigger to regenerate only the task list (that is /sdd:tasks).
---

**Usage:** `/sdd:plan <domain> [--issues]`

Spawn the `planner` agent with `--design-and-tasks` and the domain name.

Reads the existing `docs/specs/<domain>/requirements.md` and produces:
1. `design.md` — architecture, decisions, test scenarios, QA scenarios
2. Critic review of design.md (embedded — loops until PASS)
3. `tasks.md` — ordered implementation checklist
4. GitHub issues per task (with `--issues`)

Exits with a critic-verified `design.md` and `tasks.md`. If `requirements.md` is missing, run `/spec <domain>` first.

> Called automatically by `/ship` as Stage 2. Run manually when requirements already exist and you only need the design and task breakdown.

See `${CLAUDE_PLUGIN_ROOT}/agents/planner.md` for the full planning spec.
