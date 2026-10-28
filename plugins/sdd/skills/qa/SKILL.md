---
name: qa
description: >
  Use when one task's observable behaviour should be exercised against the QA Scenarios in
  design.md, through the running application rather than the source. Does not trigger during a
  /sdd:ship run, which spawns the tester per task, does not trigger for unit tests (that is
  /sdd:test) or for ad hoc exploration that fixes what it finds (that is /sdd:qa-explore),
  and never reads implementation code.
---

Before delegating, Read `${CLAUDE_PLUGIN_ROOT}/agents/tester.md` in full. In Codex, pass
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

**Usage:** `/sdd:qa <domain> <task-id>`

Spawn the `tester` agent with the domain, task ID, and required context.

Before spawning, read and pass only:
- The QA Scenarios section of `docs/specs/<domain>/design.md`
- The Acceptance Criteria section of `docs/specs/<domain>/requirements.md`
- The specific QA scenario to test

The tester agent runs as an isolated subprocess (Bash + Playwright MCP — no Write/Edit) and:
1. Detects the environment (local vs GitHub cloud agent)
2. Starts the dev server and tests observable behavior
3. Tests edge cases from design.md
4. Outputs a PASS/FAIL report with actionable behavioral feedback

**The tester never reads source code.**

> Called automatically by `/ship` after each implement + critique cycle. Run manually to re-check a specific QA scenario.

See `${CLAUDE_PLUGIN_ROOT}/agents/tester.md` for the full QA spec.
