# Ship orchestration — Design

**Status:** Approved
**Last Updated:** 2026-10-29

Source: [requirements.md](requirements.md).

## Decisions

| # | Decision | Why |
|---|---|---|
| D1 | The pipeline procedure moves out of `agents/architect.md` into `plugins/sdd/standards/ship-runbook.md`, written for "the orchestrator". | Both modes follow one file (G3). `agent-pipeline.md` stays the reference; the runbook is the procedure. |
| D2 | `pipeline.orchestrator`: `"inline"` (default) or `"architect"`; flags `--inline` / `--architect` override it for one run. | Mirrors `pipeline.explore` and its flags. |
| D0 | The orchestrator names the domain (a kebab-case slug of the feature) before Stage 1, in both modes, and passes it to the planner, which already takes `<domain>`. `<feature-branch>` is then known before Stage 1. | The architect needs the branch to create its worktree up front. |
| D3 | Inline mode: the `ship` skill's session reads the runbook in full and is the orchestrator. It may spawn stage agents, run git and the configured commands, edit spec status lines and `tasks.md` checkboxes, and talk to the user; since 0.16.0 it also writes the spec, design and tasks, creates issues and opens the PR (D13). It writes no product code or tests. | Keeps implementation and verdicts in isolated agents (Story 1); lets it record approval (Story 4). |
| D4 | Architect mode: the architect always makes its own worktree: `git worktree add .claude/worktrees/<domain> -b <feature-branch> <DEV_BRANCH>`, then adds `.claude/worktrees/` to `.git/info/exclude`. It runs every command with that path as working directory and gives the path to every stage agent. The `ship` skill spawns it with `run_in_background: true` (Claude Code) and **without** host worktree isolation, so first runs and resumes are spawned the same way. Codex, or `--foreground`, spawns it in the foreground. A denied tool call in a background architect ends the run with `ESCALATION` naming the tool. | Story 3. One checkout per mission, one code path for start and resume, nothing in the consumer's tracked `.gitignore`. |
| D5 | The architect handoff always carries `worktree_path` and `branch`, and a new status `AWAITING_SPEC_APPROVAL`. Resume is `--resume <domain> --worktree <path> [--approved] [--notes "<revision notes>"]`. | Story 4. |
| D13 | (0.16.0) Inline mode does planning and publishing in the calling session by following `planner.md` and `publisher.md`; architect mode keeps spawning them. Role files are not duplicated: the runbook points at them. A role's "output a handoff and stop" means "take that as the stage result" inline. | Planning and publishing need continuity with the user, not independence; no role text is copied. |
| D12 | In autonomous mode the orchestrator sets `requirements.md` to `Approved` when Stage 1 returns SUCCESS. | Only `Approved` means the critic passed and the spec is accepted, so resume can tell a finished spec from a crashed one. |
| D6 | Resume takes the first matching row of the resume table, most advanced state first; cycle counts restart at zero. No state file. | Story 5. Unambiguous, nothing new to keep in git. |
| D10 | `/sdd:ship --resume <domain>` resumes in either mode. The `architect` skill stays for debugging one architect run. | Story 5; one entry point for users. |
| D11 | Worktrees are never removed by the harness. The calling session reports the path; the user removes it after merge or when dropping the mission. | Removing a worktree can lose uncommitted work. |
| D7 | `architect` becomes `tier: workhorse`, `model: sonnet`. | It routes and counts; the planner and critic do the hard reasoning (G6). |
| D8 | The planner keeps its embedded critic loop. | See Out of Scope in requirements. |
| D9 | `.git/info/exclude`, not `.gitignore`, hides `.claude/worktrees/`. Tools in the main checkout that walk the tree without honouring git (some linters, test discovery) may still see worktrees; the runbook says so. | The harness does not edit tracked consumer files. |

### Alternatives considered

- *Remove the architect.* Rejected: a plain Claude Code or Codex user who runs several missions
  from one session has no other way to keep each mission's state out of that session.
- *Keep the architect as default and add `--inline`.* Rejected: one mission per session is the
  common case, and inline is cheaper there and makes the spec gate a normal question.

## Architecture

### Component design

| Component | Path | Change |
|---|---|---|
| Runbook | `plugins/sdd/standards/ship-runbook.md` (new) | Configuration, model selection, Stages 1–5 with inputs and handoffs, Stage 4b, state machine, context rules, rules, resume table, spec gate per mode |
| Architect role | `plugins/sdd/agents/architect.md` | Delegation preamble, role, invocation (`--autonomous`, `--explore`, `--resume`, `--worktree`, `--approved`, `--notes`), worktree setup, "follow the runbook", architect-only gate and handoff; `tier: workhorse`, `model: sonnet` |
| Ship skill | `plugins/sdd/skills/ship/SKILL.md` | Usage gains `[--inline \| --architect]`; resolve orchestrator; inline steps; architect dispatch (background, worktree), gate round trip, resume |
| Architect skill | `plugins/sdd/skills/architect/SKILL.md` | Resume and debug in architect mode, pointing at the runbook |
| Config | `plugins/sdd/config/config.schema.json` | `pipeline.orchestrator` enum `inline`/`architect`, default `inline` |
| Docs | `docs/configuration.md`, `docs/plugins.md`, `plugins/sdd/standards/agent-pipeline.md`, `plugins/sdd/skills/critique/SKILL.md` | Mode section, tier table, wording "the orchestrator" where the architect was assumed |
| Release | both manifests | sdd 0.15.0 |

### Resume table

First matching row wins; rows run from the most advanced state down.

| # | On disk | Next stage |
|---|---|---|
| R1 | A PR is open for `<feature-branch>` | Stage 5 (CI watch) |
| R2 | Every task in `tasks.md` checked | Stage 4b (when explore is on), then Stage 5 |
| R3 | `tasks.md` has an unchecked task | Code critique and QA for the last checked task (if any), then Stage 3 at the first unchecked task |
| R4 | `requirements.md` `Approved`, and `design.md` or `tasks.md` missing | Stage 2 |
| R5 | Revision notes given | Stage 1 with the notes, then the spec gate |
| R6 | `requirements.md` `Review`, and approval given | Set `Approved`, Stage 2 |
| R7 | `requirements.md` `Review`, no approval given | Spec gate (interactive); Stage 1 again (autonomous) |
| R7b | `requirements.md` `Draft` | Stage 1 again (the critic loop never passed) |
| R8 | No `requirements.md` | Stage 1 |

## Test Scenarios

Python `unittest` in `tests/`, no provider calls.

| # | Scenario | Asserts |
|---|---|---|
| T1 | `test_ship_orchestration.py` schema | `pipeline.orchestrator` is a string enum `["inline", "architect"]` with default `inline` |
| T2 | ship skill | Usage line has `[--inline \| --architect]` and `[--resume <domain>]`; names `pipeline.orchestrator`, says inline by default, stops and asks when both mode flags are given, reads `ship-runbook.md` in full, says it writes no product code, handles `AWAITING_SPEC_APPROVAL`, spawns the architect with `run_in_background` and without host worktree isolation, runs in the foreground for Codex or `--foreground`, reports a denied tool as `ESCALATION`, and tells the user how to remove the worktree |
| T3 | runbook | Has the stage sections, Stage 4b, State Machine, Context Engineering Rules, the spec gate for both modes, and the resume table with "first matching row", rows R1–R8 (with R7b) in that order, and "Cycle counts restart at zero"; lists architect under `workhorse` |
| T4 | architect role | References `ship-runbook.md`, `--resume`, `--worktree`, `--approved`, `worktree_path`, `AWAITING_SPEC_APPROVAL`, `git worktree add`, `.git/info/exclude`; its escalation handoff carries `worktree_path` and `branch`; tier `workhorse`, model `sonnet`; no State Machine copy |
| T5 | `test_ship_explore.py` | Stage 4b assertions read the runbook instead of `architect.md` |
| T6 | `test_agent_tiers.py` | Architect expected tier is `workhorse`; `agent-pipeline.md` tier table lists architect under `workhorse` |
| T7 | `test_ship_orchestration.py` flat install | Installed ship skill and architect reference `.claude/standards/ship-runbook.md` |
| T9 | `test_ship_orchestration.py` inline authoring | Ship skill says inline does planning and publishing itself and names both role files; runbook Stages 1, 2 and 5 each carry an `Inline: follow` and an `Architect: spawn` line; inline gate revises the spec itself; critic, tester, qa-engineer and executor stay separate agents |
| T8 | `./scripts/check-all.sh`, `./tests/run-fixtures.sh`, `./tests/install-paths.sh` | All pass |

## QA Scenarios

The running application for this repository is its gates and its installer.

| # | Scenario | Pass when |
|---|---|---|
| Q1 | Install into a fresh temp git repo with `scripts/install-skills.sh --harness claude,codex` | `.claude/standards/ship-runbook.md` exists; installed `ship` and `architect` point at `.claude/standards/ship-runbook.md`, not `${CLAUDE_PLUGIN_ROOT}` |
| Q2 | Read the installed ship skill | Its usage section names the default mode, both mode flags, `pipeline.orchestrator` and `--resume`, without opening another file |
| Q3 | All gates and fixtures | Pass |
