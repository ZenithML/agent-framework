---
name: ship
description: >
  Use when a code change should run the whole pipeline end to end without stopping at each stage
  — a feature, fix or refactor described in one sentence — or to resume such a run with --resume.
  Runs spec, plan, implement, critique, QA and publish inline in this session by default, or
  through the architect subagent with --architect. Does not trigger when the caller names a
  single stage (use that stage's own skill) or when no change is described yet.
---

Before every delegation (the architect in architect mode, each stage agent in inline mode), Read
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

**Usage:** `/sdd:ship <feature-description> [--autonomous] [--explore | --no-explore] [--inline | --architect] [--foreground] [--resume <domain>]`

The primary entry point for all code changes:

```
spec → plan → (implement → critique → qa) per task → [explore] → publish
```

The procedure for every run is `${CLAUDE_PLUGIN_ROOT}/standards/ship-runbook.md`. Read it in full before the
first stage. This skill only decides who follows it.

**Modes:**
- **interactive** (default): human approval gate after the spec, before design begins
- **autonomous** (`--autonomous`): no human gates; runs to completion

**Exploratory QA (`--explore`), off by default:** after every task has passed QA, the
`qa-engineer` plays with the whole feature in the running app once, fixes the bugs it confirms
(each with a regression test, reviewed by the critic) and lists UX friction in the PR. It makes
a run slower and costlier and catches what the per-task scenarios miss; choose it for a careful
ship. A repo can turn it on for every run with `"pipeline": {"explore": true}` in
`.claude/sdd/config.json`; `--explore` or `--no-explore` overrides that setting for one run.

Resolve explore: `--explore` or `--no-explore` when given, otherwise `pipeline.explore` from
`.claude/sdd/config.json`, otherwise off.

## Who orchestrates: inline by default

| Mode | Who follows the runbook | Choose it when |
|---|---|---|
| `inline` (default) | This session, which also writes the spec, plan and PR | One mission per session, or a host that gives each mission its own session or thread. Cheapest; the spec is written in the conversation and the gate is a normal question to the user. |
| `architect` | The `architect` subagent, in its own git worktree | You stay in one session and start several missions from it, and each mission's state must stay out of this session. |

Resolve the orchestrator: `--inline` or `--architect` when given, otherwise
`pipeline.orchestrator` from `.claude/sdd/config.json`, otherwise `inline`. If both `--inline` and
`--architect` are given, stop and ask the user which one they mean. Log
`[Ship] Orchestrator: <mode> (<flag | config | default>)`.

## Inline mode

This session is the orchestrator. Follow the runbook stage by stage. Do the planning stages
(spec, plan, tasks) and publishing yourself, following `${CLAUDE_PLUGIN_ROOT}/agents/planner.md` and
`${CLAUDE_PLUGIN_ROOT}/agents/publisher.md` as the runbook says. Spawn `critic`, `executor`, `tester` and
`qa-engineer` (when explore is on) as separate agents with exactly the scoped inputs the runbook
lists, under the delegation contract above. This session
writes no product code or tests: implementation comes only from the executor, verdicts only from the
critic and tester. It may run git and the configured commands, edit spec status lines and
`tasks.md` checkboxes, and talk to the user.

- **Spec gate** (interactive): once the spec has passed the critic (`AWAITING_SPEC_APPROVAL`),
  ask the user as the runbook's **Spec gate** says, and continue in this session.
- **Resume:** with `--resume <domain>`, check out `<feature-branch>` first, then pick the stage
  from the runbook's **Resume** table.
- **End:** report the PR link, or the escalation and what the user needs to decide.

## Architect mode

Read `${CLAUDE_PLUGIN_ROOT}/agents/architect.md` in full, then spawn the `architect` agent with the feature description and `--autonomous` / `--explore` as
resolved. Do not pass this conversation.

- **Claude Code:** spawn it with `run_in_background: true` and **without**
  `isolation: "worktree"`: the architect makes its own worktree under `.claude/worktrees/`, so a
  first run and a resume are spawned the same way. Tell the user the mission is running and that
  this session is free. A background subagent cannot ask for permissions, so git, file edits and
  the PR tool must already be allowed; if they are not, pass `--foreground`.
- **Codex**, or `--foreground`: spawn it in the foreground; it still works in its own worktree.

Several architects can run at once, one per mission. When one returns:

- **`AWAITING_SPEC_APPROVAL`:** show the user its `requirements_path` (inside its `worktree_path`)
  and ask for approval or changes. Then spawn a fresh architect the same way with
  `--resume <domain> --worktree <worktree_path>` and `--approved`, or `--notes "<the user's changes>"`.
- **`ESCALATION`:** tell the user the reason. For `permission denied`, ask them to allow that tool
  or rerun with `--foreground`. Resume as above once it is settled.
- **`DONE`:** report the PR link.

Every handoff names `worktree_path` and `branch`. Tell the user the worktree stays until they
remove it with `git worktree remove <worktree_path>`, after the PR merges or when they drop the
mission. Never remove it yourself.

`/sdd:ship --resume <domain>` in architect mode finds the worktree with
`git worktree list` (the one on `<feature-branch>`) and resumes the architect there.

See `${CLAUDE_PLUGIN_ROOT}/standards/agent-pipeline.md` for why the pipeline is shaped this way.
