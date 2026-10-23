---
name: ship
description: >
  Use when a code change should run the whole pipeline end to end without stopping at each stage
  — a feature, fix or refactor described in one sentence. Spawns the architect, which sequences
  spec, plan, implement, critique, QA and publish. Does not trigger when the caller names a
  single stage (use that stage's own skill), when no change is described yet, or when resuming a
  pipeline that failed midway (invoke the architect directly).
---

Before delegating, Read `${CLAUDE_PLUGIN_ROOT}/agents/architect.md` in full. In Codex, pass
that exact canonical role definition and only this stage's scoped inputs to a fresh native
subagent; do not assume a registered custom role. Read and apply the Cross-harness delegation
contract in `${CLAUDE_PLUGIN_ROOT}/standards/agent-pipeline.md`.

**Usage:** `/sdd:ship <feature-description> [--autonomous]`

The primary entry point for all code changes. Spawns the `architect` agent to run the full pipeline:

```
spec → plan → (implement → critique → qa) per task → publish
```

**Modes:**
- **interactive** (default): human approval gate after `/spec` phase, before design begins
- **autonomous** (`--autonomous`): no human gates; runs to completion

Pass the full feature description and `--autonomous` flag (if provided) to the architect agent. The architect logs model selection reasoning at each stage and reports back with a completion summary or escalation.

See `${CLAUDE_PLUGIN_ROOT}/standards/agent-pipeline.md` for the full pipeline architecture.
