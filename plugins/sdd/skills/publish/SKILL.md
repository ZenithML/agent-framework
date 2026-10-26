---
name: publish
description: >
  Use when a domain's tasks are complete and it should be taken to an open pull request — docs
  verified, description drafted from the specs, PR opened, CI watched. Does not trigger during a
  /sdd:ship run, which spawns the publisher, does not trigger with tasks still outstanding, and
  does not merge anything.
---

Before delegating, Read `${CLAUDE_PLUGIN_ROOT}/agents/publisher.md` in full. In Codex, pass
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

**Usage:** `/sdd:publish <domain>`

Spawns the `publisher` agent with the domain name and domain path (`docs/specs/<domain>/`).

The publisher owns the full shipping sequence:
1. Runs `/prepare-docs <domain>` — verifies tasks, updates INDEX.md, audits and commits docs checkpoint
2. Reads specs and drafts the PR description (summary, changes, `Closes #N`, test plan)
3. Runs `/create-pr` with the drafted description
4. Monitors CI — routes code failures back to executor, retries infra flakes once

> Called automatically by `/ship` as the final stage. Run manually when working outside the pipeline or resuming after a failure.

See `${CLAUDE_PLUGIN_ROOT}/agents/publisher.md` for the full publishing spec.
