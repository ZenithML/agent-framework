---
name: ship
description: >
  Use when a code change should run the whole pipeline end to end without stopping at each stage
  — a feature, fix or refactor described in one sentence. Runs inline in this session, scaled by
  risk with --profile fast, standard or strict: spec, plan, implement, critique, QA, exploratory
  QA, diff review and publish. Does not trigger when the caller names a single stage (use that
  stage's own skill) or when no change is described yet.
---

Before every delegation, Read
the target role's `${CLAUDE_PLUGIN_ROOT}/agents/<role>.md` in full. In Codex, pass
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

**Usage:** `/sdd:ship <feature-description> [--profile fast|standard|strict] [--autonomous] [--explore | --no-explore] [--mutate]`

The primary entry point for all code changes. The full (`standard`) pipeline:

```
spec → plan → gate-design → (implement → critique → qa) per task → [explore] → review-diff → publish
```

The procedure for every run is `${CLAUDE_PLUGIN_ROOT}/standards/ship-runbook.md`. Read it in full before the
first stage. This session follows it: there is no separate orchestrator agent. To work on several
features at once, start one session or thread per feature in your host (for example
agent-anywhere); each one runs `/sdd:ship` for its own change.

**Modes:**
- **interactive** (default): human approval gate after the spec, before design begins
- **autonomous** (`--autonomous`): no human gates; runs to completion

## Profiles: scale the pipeline to the risk

Resolve the profile: `--profile` when given, otherwise `pipeline.profile` from
`.claude/sdd/config.json`, otherwise `standard`. An unknown value stops the run and asks the user.
Log `[Ship] Profile: <profile> (<flag | config | default>)`.

| Profile | Runs | Use for |
|---|---|---|
| `fast` | existing tests, review-diff (proof of bug), CI; no spec, design, critic or QA | small bugfixes, UI tweaks, docs |
| `standard` (default) | spec and design with critic, tests, exploratory QA, review-diff | ordinary features and fixes |
| `strict` | full Failure Modes & Degradation Matrix, critic, Prosecutor/Defender tests, mutation gate, exploratory QA, review-diff | payments, auth, data loss, concurrency |

The runbook's **Profiles** section has the per-stage table. If a `fast` change turns out to need a
design decision (it touches an interface, data or auth), stop and ask the user whether to rerun
with `--profile standard`; do not escalate silently.

**Exploratory QA (`--explore`):** on in `standard` and `strict`, off in `fast`. The
`qa-engineer` plays with the whole feature in the running app once, fixes the bugs it confirms
(each with a regression test, reviewed by the critic) and lists UX friction in the PR. `--explore`
or `--no-explore` overrides the profile for one run; `pipeline.explore` in `.claude/sdd/config.json`
overrides the profile default for a repo, and the flag overrides both.

**Mutation gate (`--mutate`):** on in `strict`, off otherwise. After a task's unit tests pass,
`commands.mutate` runs on the files changed since the base branch and every surviving mutant goes
back to the executor to be killed by a new test before critique (see Stage 3 of the runbook).
`--mutate` forces it on; `pipeline.mutate` sets the repo default; skipped with a warning when
`commands.mutate` is unset.

## How it runs

This session is the orchestrator. Follow the runbook stage by stage. Do the planning stages
(spec, plan, tasks) and publishing yourself, following `${CLAUDE_PLUGIN_ROOT}/agents/planner.md` and
`${CLAUDE_PLUGIN_ROOT}/agents/publisher.md` as the runbook says. Spawn `critic`, `executor`, `tester` and
`qa-engineer` (when explore is on) as separate agents with exactly the scoped inputs the runbook
lists, under the delegation contract above. This session
writes no product code or tests: implementation comes only from the executor, verdicts only from the
critic and tester. It may write the spec, design and tasks, create issues, open the PR, run git
and the configured commands, edit spec status lines and `tasks.md` checkboxes, and talk to the
user.

- **Mechanical gates:** run `${CLAUDE_PLUGIN_ROOT}/scripts/gate-design.py` after the design passes
  the critic and `${CLAUDE_PLUGIN_ROOT}/scripts/gate-review.py` after each review-diff pass, as
  the runbook says. They are plain python3 scripts, so they run the same in Claude Code, Codex and
  agy; a failing gate is fixed, not skipped.
- **Spec gate** (interactive): once the spec has passed the critic, ask the user as the
  runbook's **Spec gate** says, and continue in this session.
- **End:** report the PR link, or the escalation and what the user needs to decide.

See `${CLAUDE_PLUGIN_ROOT}/standards/agent-pipeline.md` for why the pipeline is shaped this way.
