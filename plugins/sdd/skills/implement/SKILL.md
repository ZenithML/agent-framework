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
