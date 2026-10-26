---
name: spec
description: >
  Use when a named domain needs its requirements.md written or revised — user stories,
  acceptance criteria and Given/When/Then scenarios, with critic review looped in until it
  passes. Does not trigger during a /sdd:ship run, which invokes the planner directly, and does
  not trigger for design or task breakdown (that is /sdd:plan).
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

**Usage:** `/sdd:spec <domain> [--autonomous]`

Spawn the `planner` agent with `--spec-only` and the domain name.

The planner will:
1. Read existing state in `docs/specs/<domain>/` and `docs/INDEX.md`
2. Create or update `requirements.md`
3. Spawn the `critic` agent to review requirements (completeness, Given/When/Then, no ambiguity)
4. On REVISE: apply feedback and re-run critic (max 2 cycles)
5. On PASS: in interactive mode, surface to user for final approval before exiting

Exits with a critic-verified `requirements.md`. Run `/plan <domain>` next to produce design.md and tasks.md.

> Called automatically by `/ship` as Stage 1. Run manually when you only need to define or update requirements.

See `${CLAUDE_PLUGIN_ROOT}/agents/planner.md` for the full planning spec.
