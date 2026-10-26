---
name: critique
description: >
  Use when one already-written artifact needs an adversarial second opinion on demand —
  requirements, design, or the code from a finished task — returning PASS or REVISE. Does not
  trigger during /sdd:spec or /sdd:plan, where critic review is already embedded, and does not
  trigger to fix what it finds.
---

Before delegating, Read `${CLAUDE_PLUGIN_ROOT}/agents/critic.md` in full. In Codex, pass
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

**Usage:** `/sdd:critique <context> <domain>`

- `context`: `requirements` · `design` · `code`
- `domain`: the domain being reviewed

Spawn the `critic` agent with the appropriate artifacts and criteria:

| Context | Artifacts passed |
|---|---|
| `requirements` | `requirements.md` |
| `design` | `requirements.md` + `design.md` |
| `code` | Changed source files + Architecture + Test Scenarios sections of `design.md` |

The critic is **read-only** and returns a structured PASS/REVISE handoff. It never modifies files.

> In the pipeline, critic review is embedded within `/spec` (requirements) and `/plan` (design). Code critique after each executor task is managed by the architect. Run `/critique` manually to re-check a specific artifact.

See `${CLAUDE_PLUGIN_ROOT}/agents/critic.md` for the full review spec.
