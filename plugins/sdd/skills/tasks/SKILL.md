---
name: tasks
description: >
  Use when a domain's design.md changed and only tasks.md needs regenerating, or when existing
  tasks need GitHub issues created and linked. Does not trigger when design.md is missing or
  stale (run /sdd:plan), does not trigger during a /sdd:ship run, and does not write or revise
  design content itself.
---

**Usage:** `/sdd:tasks <domain> [--issues]`

Spawn the `planner` agent with `--tasks-only` and the domain name.

The planner will:
1. Read `docs/specs/<domain>/requirements.md` and `design.md`
2. Generate or update `docs/specs/<domain>/tasks.md`
3. With `--issues`: create a GitHub issue per task and link them in tasks.md

Use this to regenerate the task list after design changes, or to add issue links to an existing tasks.md. If `requirements.md` or `design.md` is missing, run `/spec` then `/plan` first.
