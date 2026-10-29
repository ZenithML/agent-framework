---
name: architect
description: >
  Use when debugging one architect-mode run directly — the subagent that follows the ship
  runbook in its own worktree, invoked here rather than through /sdd:ship. Does not trigger for
  a normal change or a resume (use /sdd:ship, or /sdd:ship --resume), and does not
  trigger to run a single stage cleanly (use that stage's skill).
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

**Note:** This is the orchestrator for `/ship` in architect mode. For normal use, and to resume
a run in either mode, invoke `/ship` (`/ship --resume <domain>`) instead.

Invoke the architect directly only to debug one architect-mode run.

## Pipeline stages

| Stage | Skill (direct invocation) | Agent | Output |
|-------|--------------------------|-------|--------|
| 1 — Spec | `/spec <domain>` | `planner` | `requirements.md` [critic embedded] |
| 2 — Plan | `/plan <domain>` | `planner` | `design.md`, `tasks.md` [critic embedded] |
| 2b — Tasks only | `/tasks <domain>` | `planner` | `tasks.md`, GitHub issues |
| 3 — Implement | `/implement <domain> <task-id>` | `executor` | Tests + implementation (TDD) |
| 3b — Code critique | `/critique code <domain>` | `critic` | PASS/REVISE |
| 4 — QA | `/qa <domain> <task-id>` | `tester` | PASS/FAIL report |
| 4b — Explore (only with `--explore`) | `/qa-explore <feature-or-flow>` | `qa-engineer` | Bugs fixed test-first, friction report |
| 5 — Publish | `/publish <domain>` | `publisher` | docs verified, PR opened, CI passing |

Each stage is self-contained and can be run independently. The orchestrator runs them in sequence with context isolation between stages, following `${CLAUDE_PLUGIN_ROOT}/standards/ship-runbook.md`.

## Invocation

Spawn the `architect` agent with the feature description and flags provided.

Pass the full feature description, and `--autonomous`, `--explore`, and
`--resume <domain> --worktree <path> [--approved | --notes "..."]` (each only if provided) to the
architect agent. Without `--explore`, Stage 4b is skipped. Handle its handoff as the ship skill's
**Architect mode** section says.

See `${CLAUDE_PLUGIN_ROOT}/agents/architect.md` for the architect's own rules and
`${CLAUDE_PLUGIN_ROOT}/standards/ship-runbook.md` for the procedure.
