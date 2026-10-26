---
name: tasks
description: >
  Use when a domain's design.md changed and only tasks.md needs regenerating, or when existing
  tasks need GitHub issues created and linked. Does not trigger when design.md is missing or
  stale (run /sdd:plan), does not trigger during a /sdd:ship run, and does not write or revise
  design content itself.
---

Before delegating, Read `${CLAUDE_PLUGIN_ROOT}/agents/planner.md` in full. In Codex, pass
that exact canonical role definition and only this stage's scoped inputs to a fresh native
subagent; do not assume a registered custom role. Resolve the target role's `tier`
against its `provider_defaults` entry for the active host provider (`openai` in Codex).
Pass that model as the native `model` argument only when the host confirms support; missing mappings,
invalid tiers, unknown providers, deprecated models or unverifiable support use `inherit`
(the parent session model; omit the Codex model override). If the host rejects the model,
retry once without the override, preserving the full role and scoped inputs. Do not
retry unrelated spawn failures as model errors. Log the role, tier, provider, selected
model and any fallback reason. Never translate Claude model labels across providers.
Read and apply the Cross-harness delegation
contract in `${CLAUDE_PLUGIN_ROOT}/standards/agent-pipeline.md`.

**Usage:** `/sdd:tasks <domain> [--issues]`

Spawn the `planner` agent with `--tasks-only` and the domain name.

The planner will:
1. Read `docs/specs/<domain>/requirements.md` and `design.md`
2. Generate or update `docs/specs/<domain>/tasks.md`
3. With `--issues`: create a GitHub issue per task and link them in tasks.md

Use this to regenerate the task list after design changes, or to add issue links to an existing tasks.md. If `requirements.md` or `design.md` is missing, run `/spec` then `/plan` first.
