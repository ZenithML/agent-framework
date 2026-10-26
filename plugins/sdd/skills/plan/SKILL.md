---
name: plan
description: >
  Use when a domain has an approved requirements.md and needs design.md plus tasks.md —
  architecture, decisions, test and QA scenarios, with critic review embedded. Does not trigger
  before requirements exist or are approved (run /sdd:spec first), does not trigger during a
  /sdd:ship run, and does not trigger to regenerate only the task list (that is /sdd:tasks).
---

Before delegating, Read `${CLAUDE_PLUGIN_ROOT}/agents/planner.md` in full. In Codex, pass
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
