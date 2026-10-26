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
subagent; do not assume a registered custom role. Resolve the target role's `tier`
by reading `${CLAUDE_PLUGIN_ROOT}/config/model-tiers.json`. For the active host provider
(`openai` in Codex), prefer the target role's optional `provider_defaults.<provider>`
override; otherwise use the catalog's `<tier>.<provider>` entry. Missing or malformed
catalogs and invalid tiers select `inherit`. An explicit invalid or unsupported override
also selects `inherit`, without trying the tier default.
Pass that model as the native `model` argument only when the host confirms support; missing mappings,
invalid tiers, unknown providers, deprecated models or unverifiable support use `inherit`
(the parent session model; omit the Codex model override). If the host rejects the model,
retry once without the override, preserving the full role and scoped inputs. Do not
retry unrelated spawn failures as model errors. Log the role, tier, provider, selected
model and any fallback reason. Never translate Claude model labels across providers.
Read and apply the Cross-harness delegation
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
