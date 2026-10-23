---
name: implement
description: >
  Use when one specific task id in a domain's tasks.md should be implemented test-first —
  failing tests, minimum code to pass, then refactor, in one commit. Does not trigger during a
  /sdd:ship run, which spawns the executor per task, does not trigger without a task id, and
  does not resolve design gaps (it reports them).
---

Before delegating, Read `${CLAUDE_PLUGIN_ROOT}/agents/executor.md` in full. In Codex, pass
that exact canonical role definition and only this stage's scoped inputs to a fresh native
subagent; do not assume a registered custom role. Read and apply the Cross-harness delegation
contract in `${CLAUDE_PLUGIN_ROOT}/standards/agent-pipeline.md`.

**Usage:** `/sdd:implement <domain> <task-id>`

Spawn the `executor` agent with the domain, task ID, and required context.

Before spawning, read and pass only:
- The Test Scenarios + Architecture sections of `docs/specs/<domain>/design.md`
- The full `docs/specs/<domain>/tasks.md`

The executor runs as an isolated subprocess (Read, Write, Edit, Bash, Grep, Glob — no browser tools) and:
1. Writes failing tests for the task (red phase)
2. Implements minimum code to pass those tests (green phase)
3. Refactors while keeping tests green
4. Reports design gaps — never resolves them silently
5. Commits and outputs a handoff payload

> Called automatically by `/ship` per task in Stage 3. Run manually to implement a single task outside the pipeline.

See `${CLAUDE_PLUGIN_ROOT}/agents/executor.md` for the full implementation spec.
