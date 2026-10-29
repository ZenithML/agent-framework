# Ship orchestration: inline by default, architect on request — Requirements

**Status:** Approved
**Last Updated:** 2026-10-29

Scope: `plugins/sdd` 0.15.0 (Stories 1–6) and 0.16.0 (Story 7). Changes who coordinates a
`/sdd:ship` run, and in inline mode who does the planning and publishing.

## Problem Statement

`/sdd:ship` always spawns the `architect` subagent, and the architect spawns every stage agent.
The architect writes no code: it orders stages, counts retry cycles and scopes each stage's
inputs. The context isolation the pipeline relies on comes from the stage agents (critic,
tester, qa-engineer, executor), not from the architect itself.

Paying for the architect makes sense in one situation: a user stays in one session and starts
several missions from it, and each mission's pipeline state must stay out of that session. For
a single mission per session, which is the common case and the only case in hosts that give
every mission its own session or thread, the architect costs an extra frontier-model context,
adds a nesting level (main → architect → planner → critic is Claude Code's default depth limit
of 3), and turns the spec approval gate into a stop two subagent layers down, with no stated way
to resume.

The architect also runs in the foreground of the caller's checkout, so two missions started
from one session cannot run side by side: both would create branches in the same folder.

## Goals

- **G1 Inline by default.** `/sdd:ship` runs the pipeline in the calling session unless asked
  otherwise. That session spawns the same stage agents with the same scoped inputs and budgets.
- **G2 Architect on request.** `--architect`, or `pipeline.orchestrator: "architect"`, keeps the
  architect subagent for running several missions from one session.
- **G3 One runbook.** Stage order, inputs, budgets, state machine and context rules live in one
  file that both modes follow, so the two modes cannot drift.
- **G4 Parallel-safe architect.** In architect mode each mission runs in the background in its
  own git worktree, so missions started from one session do not share a checkout.
- **G5 A clear spec gate.** In both modes the human approval gate reaches the user from the
  calling session, and the run resumes from what is on disk.
- **G6 Cheaper coordinator.** The architect uses the `workhorse` tier, not `frontier`.

## Out of Scope

- Changing what any stage agent does, its tools, or its inputs.
- Moving the critic loop out of the planner agent. Since 0.16.0, inline planning runs in the
  calling session, so the chain is main → critic (depth 1). In architect mode it stays at depth 3,
  which the default limit allows.
- A persisted progress file. Resume derives the stage from the spec documents and git.
- Changes in consumer repos. Each consumer picks the mode in its own config after it upgrades.

## User Stories & Acceptance Criteria

### Story 1: Inline is the default

**Given** a repo whose `.claude/sdd/config.json` has no `pipeline.orchestrator`
**When** the user runs `/sdd:ship "<change>"`
**Then** the calling session reads the runbook in full and runs every stage itself as the
orchestrator, spawning planner, executor, critic, tester, qa-engineer (when explore is on) and
publisher with the runbook's scoped inputs, and spawns no architect.

**Given** inline mode
**Then** the calling session writes no product code or tests itself; implementation comes only
from the executor, verdicts only from the critic and tester.

### Story 2: Pick the mode per repo or per run

**Given** `pipeline.orchestrator` is `"architect"` in config
**When** the user runs `/sdd:ship "<change>"`
**Then** the architect subagent coordinates the run.

**Given** any config value
**When** the user passes `--inline` or `--architect`
**Then** the flag wins for that run. When both flags are passed, the skill stops and asks which
one is meant.

### Story 3: Architect missions run side by side

**Given** architect mode
**When** the user starts a second `/sdd:ship` while the first is still running
**Then** each architect works in its own git worktree under `.claude/worktrees/<domain>` on its
own feature branch.

**Given** architect mode in Claude Code
**Then** the architect runs in the background and the calling session stays free for the user,
unless `--foreground` is passed.
**Given** architect mode in Codex (no background subagents), or `--foreground`
**Then** the architect runs in the foreground, still in its own worktree.
**Given** a background architect whose tool call is denied (it cannot ask for permission)
**Then** it stops and returns `ESCALATION` with the denied tool, `worktree_path` and `branch`,
and the calling session tells the user to allow that tool or rerun with `--foreground`.

**Given** an architect finishes, stops at a gate or escalates
**Then** its handoff names its worktree path and branch, and the calling session tells the user
the worktree stays until they remove it (`git worktree remove <path>`) after the PR merges or
they drop the mission.

### Story 4: The spec gate reaches the user

**Given** interactive mode and inline orchestration
**When** the planner returns `AWAITING_SPEC_APPROVAL`
**Then** the calling session shows the user the requirements path and asks for approval or
changes. On changes it spawns the planner again with `--spec-only` and the user's notes, which
returns to the gate. On approval it sets the requirements status to `Approved` and continues
with Stage 2.

**Given** interactive mode and architect orchestration
**When** the planner returns `AWAITING_SPEC_APPROVAL`
**Then** the architect stops and returns a handoff with status `AWAITING_SPEC_APPROVAL`, the
requirements path, worktree path and branch; the calling session asks the user, then spawns a
fresh architect with `--resume <domain> --worktree <path>` and either `--approved` or
`--notes "<revision notes>"`.

### Story 5: Resume from what is on disk

**Given** a run that stopped (gate, escalation, crash or a new session)
**When** the user runs `/sdd:ship --resume <domain>` (in either mode), or the calling session
starts a fresh architect with `--resume <domain> --worktree <path>`
**Then** the orchestrator takes the first row of the runbook's resume table that matches what is
on disk, logs the row, and restarts cycle counts at zero.

### Story 6: Cheaper architect

**Given** the role catalog
**Then** `architect` declares `tier: workhorse` and `model: sonnet`, and the tier tables in
`agent-pipeline.md` and the runbook list it under `workhorse`.

### Story 7: Inline mode writes the spec, plan and PR itself (0.16.0)

**Given** inline mode
**When** a run reaches Stage 1, 2 or 5
**Then** the calling session follows `agents/planner.md` (Phase 1 or 2) or `agents/publisher.md`
itself instead of spawning those agents, and the critic loop it runs spawns the critic directly
from the calling session.

**Given** inline mode and the spec gate
**When** the user asks for changes
**Then** the calling session revises `requirements.md` itself, re-runs the critic loop and asks
again.

**Given** architect mode
**Then** the architect still spawns the `planner` and `publisher` agents.

**Given** either mode
**Then** critic, tester, qa-engineer and the per-task executor remain separate agents.

## Constraints

- Works in Claude Code and Codex, under the existing cross-harness delegation contract.
- Flat consumer installs keep working: the runbook ships under `standards/` and installs to
  `.claude/standards/`.
- Existing `--autonomous` and `--explore | --no-explore` behaviour is unchanged.
