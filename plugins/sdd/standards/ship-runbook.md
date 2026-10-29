# Ship Runbook

The procedure for one `/sdd:ship` run. The **orchestrator** follows it: the calling session in
inline mode (the default), or the `architect` subagent in architect mode. Which mode runs, and
how the two differ, is in `${CLAUDE_PLUGIN_ROOT}/skills/ship/SKILL.md`; why the pipeline is
shaped this way is in [agent-pipeline.md](agent-pipeline.md). This file is the only copy of the
procedure; neither the ship skill nor the architect restates it.

The orchestrator coordinates and writes no product code or tests itself. Implementation comes
only from the executor, verdicts only from the critic and tester. It may spawn stage agents, run
git and the configured commands, edit spec status lines and `tasks.md` checkboxes, and talk to
the user (inline) or return a handoff (architect). Inline, it also does the authoring stages
below: writes requirements.md, design.md and tasks.md, creates issues, and opens the PR.

**Who does the authoring stages.** Planning (Stages 1 and 2) and publishing (Stage 5) need
continuity with the user, not independence, so in **inline** mode the orchestrator does them
itself: it reads the role file (`${CLAUDE_PLUGIN_ROOT}/agents/planner.md`, `${CLAUDE_PLUGIN_ROOT}/agents/publisher.md`) in full and
follows its steps and constraints in this session. Where the role file says to output a handoff
and stop, take that handoff as the stage's result and go on with this runbook. The role's own
critic loop spawns the critic straight from this session. In **architect** mode the architect spawns the
`planner` and `publisher` agents as below. Stages that need independence (critic, tester,
qa-engineer) and the per-task executor are always separate agents, in both modes.

**Configuration:** resolve `<TEST_CMD>`, `<LINT_CMD>`, `<BUILD_CMD>`, `<DEV_CMD>`, `<DEV_HOST_CMD>`, `<INSTALL_CMD>`, `<DEV_BRANCH>`, `<MAIN_BRANCH>`, `<SOURCE_DIR>`, and `<feature-branch>` from `.claude/sdd/config.json` at the repo root; if absent, auto-detect from `package.json`/`pyproject.toml` and default branches to `main`/`development` and source dir to `src`.

**Working directory:** in architect mode every command runs in the mission's worktree, and every
stage agent is told to work there (see `${CLAUDE_PLUGIN_ROOT}/agents/architect.md`). In inline mode it is the
calling session's checkout.

---

## Model Selection

For every invocation, use the target role's declared tier and provider default:

- `workhorse`: architect (architect mode only) — pipeline control; planner, critic, archivist,
  publisher — planning, review and publication;
  qa-engineer — exploratory QA; in this pipeline only Stage 4b dispatches it, when `--explore` is on.
- `fast`: executor, tester — implementation and observable behaviour checks.

Read `${CLAUDE_PLUGIN_ROOT}/config/model-tiers.json`. Resolve the target role's optional
`provider_defaults.<active-provider>` override first, otherwise its `<tier>.<active-provider>`
entry in that catalog. Invalid catalogs or tiers select `inherit`; invalid or unsupported
explicit overrides also select `inherit` without trying another default. In Codex,
pass the resolved OpenAI ID as the native spawn's `model` argument when advertised as
supported and active. In Claude Code, pass the Anthropic default to the Agent tool;
`model:` remains the matching legacy default. Other providers use their matching entry.
An unknown provider, invalid tier, missing mapping, unavailable/deprecated model or
unverifiable model support selects `inherit`; omit the native model override where
literal `inherit` is unsupported. If the host rejects a model override, retry once
without it. Do not retry unrelated delegation failures as model errors.

Log the role, tier, provider, selected model (or `inherit`) and fallback reason:
```
[Orchestrator] Invoking executor (task 3): tier=fast provider=openai model=<resolved-model>
Reason: Supported target-role default
```

---

## Pipeline

```
Stage 1: Spec    → planner (--spec-only)*        → requirements.md [critic embedded]
Stage 2: Plan    → planner (--design-and-tasks)* → design.md + tasks.md [critic embedded]
Stage 3: Implement → executor (per task)         → tests + implementation (TDD)
         ↓
         Code Critique → critic (code context)   → PASS / REVISE
         ↓
Stage 4: QA      → tester (per task)             → PASS / FAIL
Stage 4b: Explore → qa-engineer (once, --explore only) → fixes + friction report
Stage 5: Publish → publisher*                    → docs verified, PR opened, CI passing
```

\* Inline, the orchestrator does this stage itself by following the role file; architect mode
spawns the agent. Every other stage is always a separate agent.

---

## Stage 1: Spec

First name the domain: a short kebab-case slug of the feature (reuse an existing
`docs/specs/<name>/` when the change belongs to it). `<feature-branch>` follows from it.

Inline: follow `${CLAUDE_PLUGIN_ROOT}/agents/planner.md` Phase 1 (`--spec-only`) yourself with the domain name,
feature description and mode. Architect: spawn the `planner` agent with:
- `--spec-only` flag
- Domain name
- Feature description
- Mode (interactive or autonomous)

Either way requirements.md is written and passes the critic review loop (the critic is always a
separate agent). In interactive mode the stage ends at `AWAITING_SPEC_APPROVAL`; handle it as in
**Spec gate** below.

```json
// Handoff expected:
{
  "stage": "planner",
  "status": "SUCCESS",
  "artifacts": {
    "domain": "my-feature",
    "domain_path": "docs/specs/my-feature/",
    "requirements_path": "docs/specs/my-feature/requirements.md"
  },
  "metadata": { "scope": "spec-only" }
}
```

In autonomous mode, set the `**Status:**` line of `requirements.md` to `Approved` as soon as the
spec stage ends with SUCCESS, so a later resume knows the critic passed.

After this stage (once the spec is approved, or at once in autonomous mode): in inline mode,
create feature branch `<feature-branch>` from `<DEV_BRANCH>` and commit the spec to it. In
architect mode the branch already exists in the mission's worktree; commit the spec there.

---

## Stage 2: Plan

Inline: follow `${CLAUDE_PLUGIN_ROOT}/agents/planner.md` Phase 2 (`--design-and-tasks`, `--issues`) yourself.
Architect: spawn the `planner` agent with:
- `--design-and-tasks` flag
- Domain name
- `--issues` flag to create GitHub issues

Either way requirements.md is read, design.md is written and passes the critic review loop, then
tasks.md is written and issues are created. While planning (Stages 1 and 2), do not open
implementation or test files, even inline: plan from the docs, as planner.md Phase 1 says. If
code is already in this conversation, do not base the spec or design on it.

```json
// Handoff expected:
{
  "stage": "planner",
  "status": "SUCCESS",
  "artifacts": {
    "domain": "my-feature",
    "design_path": "docs/specs/my-feature/design.md",
    "tasks_path": "docs/specs/my-feature/tasks.md",
    "task_count": { "total": 8, "new": 8, "completed": 0 },
    "issue_urls": ["https://github.com/..."]
  },
  "metadata": { "scope": "design-and-tasks" }
}
```

---

## Stage 3: Implement

For each task in tasks.md, spawn `executor` agent with **only**:
- Domain name + task ID
- Architecture + Test Scenarios sections of design.md
- Contents of tasks.md

Do NOT pass: other tasks' diffs, tester history, your internal state.

The executor owns the full TDD cycle: writes failing tests (red), implements (green), refactors, commits.

```json
// Handoff expected:
{
  "stage": "executor",
  "status": "SUCCESS | DESIGN_GAP",
  "artifacts": {
    "task_id": 3,
    "test_files": ["src/lib/cart-total.test.ts"],
    "files_changed": ["src/lib/cart-total.ts"],
    "test_result": { "total": 15, "passed": 15, "failed": 0 },
    "commit_sha": "abc123"
  }
}
```

**If DESIGN_GAP:** Route back to the spec or plan stage (`--spec-only` or `--design-and-tasks`; inline: revise it yourself by following planner.md; architect: spawn the planner) for targeted revision, then resume executor.

---

## Code Critique (after each implement task)

Spawn `critic` agent with:
- `context`: `"code"`
- Changed source files from the executor's commit
- Architecture + Test Scenarios sections of design.md

```json
// PASS:
{ "stage": "critic", "status": "PASS", "artifacts": { "context": "code" } }

// REVISE:
{
  "stage": "critic",
  "status": "REVISE",
  "artifacts": {
    "context": "code",
    "feedback": ["src/lib/cart-total.ts: New persistent-state key not in design.md"]
  }
}
```

**If REVISE:** Pass feedback to executor for fixes (max 2 cycles). Do not proceed to QA until critic passes.

---

## Stage 4: QA

After code critique passes, spawn `tester` agent with **only**:
- Domain name + task ID
- QA Scenarios section of design.md
- Acceptance Criteria section of requirements.md
- The specific QA scenario to test

Do NOT pass: code, diffs, executor reasoning, source file paths.

```json
// PASS:
{ "stage": "tester", "status": "PASS", "artifacts": { "task_id": 3 } }

// FAIL:
{
  "stage": "tester",
  "status": "FAIL",
  "artifacts": {
    "task_id": 3,
    "feedback": "Total not updating after adding items to cart.",
    "screenshots": ["/tmp/fail.png"]
  },
  "metadata": { "cycle": 1 }
}
```

**Fix cycles:**
- On FAIL: pass feedback to executor for fixes (max 3 cycles per task)
- After 3 failures: escalate (see **Escalation** below)

---

## Stage 4b: Explore (optional)

Skip this stage unless you were called with `--explore`; log `[Orchestrator] Explore: off` and go
to Stage 5. When `--explore` is on but the change has nothing to run (docs, config or harness
only), skip it too and keep the line `Exploratory QA skipped: <reason>` for the publisher.

**Before spawning:** the working tree must be clean — commit or discard anything earlier stages
left uncommitted, because `qa-engineer` treats every dirty file as the user's work and will not
fix it. Record `START=$(git rev-parse HEAD)`; it is your record, independent of the agent's own.

Spawn `qa-engineer` once, in fix mode, with **only**:
- The feature description and the domain name
- The QA Scenarios section of design.md, as context, not a boundary
- The dev URL resolved from `devServer.url`, and the credential variable names from
  `devServer.credentialEnv`, if any

Do NOT pass: diffs, executor reasoning, tester or critic history.

**What comes back** is the agent's plain-text report (qa-engineer.md step 7): `MODE`,
`COMMITS`, then BUGS FOUND & FIXED (each with its test file and its `test:` and `fix:`
commits), FRICTION NOTED, NOT FIXED (why), CLEAN. There is no JSON handoff. If the report says
it stopped because nothing answered at the dev URL and no `<DEV_HOST_CMD>` is configured,
treat the stage as blocked: keep `Exploratory QA skipped: <its reason>` for the publisher and go
to Stage 5.

**Checking its fixes** (only when `<START>..HEAD` is not empty):
1. Spawn `critic` (`context: "code"`) with the output of `git diff <START>..HEAD` inline (the
   critic cannot run git), the bug list from the report, the
   Architecture and Test Scenarios sections of design.md, and these criteria: each fix is
   minimal and targets one reported bug; each bug has a regression test; nothing else changed.
   These are bug fixes found by exploration, so "scope limited to the assigned task" means
   "limited to the reported bug".
2. On REVISE there is no second round with `qa-engineer` (it has no resume input and would
   re-explore from scratch). For each bug the critic rejects, revert
   both its `test:` and `fix:` commits (`git revert --no-edit <fix> <test>`, never a history rewrite; revert all of
   `<START>..HEAD` if the commits cannot be told apart) and move the bug to NOT FIXED with the
   critic's reason.
3. Run `<TEST_CMD>`. If it fails, revert the commits of the bug whose test or fix breaks it the
   same way, and re-run until green; if it still fails, revert all of `<START>..HEAD`.
4. Keep the final report, with those moves applied, for Stage 5.

Exploration findings never send the pipeline back to the planner or the executor: a bug that
needs a product decision stays in the report.

---

## Stage 5: Publish

Inline: follow `${CLAUDE_PLUGIN_ROOT}/agents/publisher.md` yourself with the inputs below. Architect: spawn the
`publisher` agent with:
- Domain name
- Domain path (`docs/specs/<domain>/`)
- When `--explore` was on: the Stage 4b report, or its `Exploratory QA skipped: <reason>` line,
  for an "Exploratory QA" section of the PR description

```json
// SUCCESS:
{
  "stage": "publisher",
  "status": "SUCCESS",
  "artifacts": { "pr_url": "https://github.com/.../pull/N", "ci_status": "passing" }
}

// CI_FAIL:
{
  "stage": "publisher",
  "status": "CI_FAIL",
  "artifacts": {
    "pr_url": "https://github.com/.../pull/N",
    "diagnosis": "code issue | infra flake | unknown"
  },
  "next_action": "executor | escalate"
}
```

**If CI_FAIL (code issue):** route to executor for fixes, then re-run the publish stage. Where
publisher.md says to hand a code failure to the Architect, that means the orchestrator: inline,
this session routes it to the executor itself.

## State Machine

```
SPEC             → AWAITING_SPEC_APPROVAL → SPEC GATE (interactive)
                 → SUCCESS          → PLANNING
PLANNING         → SUCCESS          → IMPLEMENTATION(task 0)
                 → DESIGN_GAP       → SPEC or PLANNING (targeted revision)

IMPLEMENTATION   → COMPLETE         → CODE_CRITIQUE(task N)
                 → DESIGN_GAP       → SPEC or PLANNING (targeted revision)

CODE_CRITIQUE    → PASS             → QA(task N)
                 → REVISE (cycle<2) → IMPLEMENTATION(task N, retry)
                 → REVISE (cycle=2) → ESCALATION

QA               → PASS + more tasks → IMPLEMENTATION(task N+1)
                 → PASS + done       → EXPLORING (--explore) | PUBLISHING
                 → FAIL (cycle < 3)  → IMPLEMENTATION(task N, retry)
                 → FAIL (cycle == 3) → ESCALATION

EXPLORING        → skipped / blocked → PUBLISHING (skip reason attached)
                 → report            → CHECK_FIXES (critic + <TEST_CMD>)
CHECK_FIXES      → PASS              → PUBLISHING (report attached)
                 → REVISE / red      → revert those bugs' test + fix commits → PUBLISHING

PUBLISHING       → SUCCESS           → DONE
                 → CI_FAIL (code)    → IMPLEMENTATION(fix) → PUBLISHING
                 → CI_FAIL (flake)   → retry once → DONE | ESCALATION
```

---

## Context Engineering Rules

| Stage | Receives | Never receives |
|-------|----------|----------------|
| planner (spec) | feature description, mode, existing docs (inline: also this conversation) | code, test files |
| planner (plan) | requirements.md, mode, existing docs (inline: also this conversation) | code, test files |
| executor | design.md (Architecture + Test Scenarios), tasks.md, one task ID | other tasks' diffs, tester history |
| critic (code) | changed source files, design.md (Architecture + Test Scenarios) | other tasks' diffs, tester feedback |
| tester | design.md (QA Scenarios), requirements.md, target scenario | code, diffs, executor reasoning |
| qa-engineer (Stage 4b) | feature description, domain, design.md (QA Scenarios, as context), dev URL, credential variable names | diffs, executor reasoning, tester or critic history |
| critic (code, Stage 4b) | `git diff <START>..HEAD` inline, bug list, design.md (Architecture + Test Scenarios), bug-fix criteria | the exploration transcript |
| publisher | domain, domain path, Stage 4b report or skip reason when `--explore` was on | agent transcripts (inline: it has none) |

---

## Rules

- Specs always come first — no code before Stage 2 completes
- Critic review is embedded in the planning stages for spec/design; the orchestrator manages code critique directly
- TDD is embedded in executor — red → green → refactor per task
- Tester is adversarial — its job is to find problems
- Domain specs are the single source of truth; route gaps back to spec, never resolve silently
- CI must pass before reporting DONE

**Escalation** (any `ESCALATION` in the state machine): inline, tell the user which budget ran
out or which design gap needs a decision, and wait for them. In architect mode, return the
escalation handoff from `${CLAUDE_PLUGIN_ROOT}/agents/architect.md`; the calling session tells the user.

---

## Spec gate

Interactive mode only; `--autonomous` has no gate. `requirements.md` is at `Review` and has
passed the critic (`AWAITING_SPEC_APPROVAL`).

- **Inline:** show the user the requirements path and a short summary, and ask them to approve
  or say what to change. On changes, revise requirements.md yourself, re-run the critic loop and
  ask again. On approval, set the `**Status:**` line of `requirements.md` to `Approved` and
  continue with Stage 2.
- **Architect:** stop and return the gate handoff from `${CLAUDE_PLUGIN_ROOT}/agents/architect.md`. The calling
  session asks the user and starts a fresh architect with `--resume`; that run continues from
  **Resume** below.

---

## Resume

With `--resume <domain>`, derive the next stage from what is on disk, never from memory of an
earlier run. First get onto the mission's branch: inline, check out `<feature-branch>` when it
exists (stop and ask if the working tree has uncommitted changes); in architect mode, work in the
given worktree. Take the **first matching row**; rows run from the most advanced state down.
Cycle counts restart at zero.

| # | On disk | Next stage |
|---|---|---|
| R1 | A PR is open for `<feature-branch>` | Stage 5 (CI watch) |
| R2 | Every task in `tasks.md` checked | Stage 4b (when explore is on), then Stage 5 |
| R3 | `tasks.md` has an unchecked task | Code critique and QA for the last checked task (if any), then Stage 3 at the first unchecked task |
| R4 | `requirements.md` `Approved`, and `design.md` or `tasks.md` missing | Stage 2 |
| R5 | Revision notes given (`--notes`) | Stage 1 with the notes, then the spec gate |
| R6 | `requirements.md` `Review`, and approval given (`--approved`) | Set `Approved`, then Stage 2 |
| R7 | `requirements.md` `Review`, no approval given | Spec gate (interactive); Stage 1 again (autonomous) |
| R7b | `requirements.md` `Draft` | Stage 1 again (the critic loop never passed) |
| R8 | No `docs/specs/<domain>/requirements.md` | Stage 1 |

Log the row that matched: `[Orchestrator] Resume <domain>: R<n> → <stage>`.

## Worktrees (architect mode)

The architect keeps each mission in `.claude/worktrees/<domain>` and hides the folder with
`.git/info/exclude`, so `git status` in the main checkout stays clean. Tools that walk the tree
without asking git (some linters, test discovery) can still see it; exclude `.claude/worktrees/`
in their own config if that matters. The harness never removes a worktree: the user runs
`git worktree remove <path>` after the PR merges or when dropping the mission.
