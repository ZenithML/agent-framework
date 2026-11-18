# Ship Runbook

The procedure for one `/sdd:ship` run. The **orchestrator** follows it: the calling session, which
runs inside one feature session or thread. There is no orchestrator subagent, no worktree setup and
no resume table; running several features at once is the host's job (one session or thread per
feature). The ship skill, `${CLAUDE_PLUGIN_ROOT}/skills/ship/SKILL.md`, resolves the flags and the
risk profile; why the pipeline is shaped this way is in [agent-pipeline.md](agent-pipeline.md).
This file is the only copy of the procedure; the ship skill does not restate it.

The orchestrator coordinates and writes no product code or tests itself. Implementation comes
only from the executor, verdicts only from the critic and tester. It may spawn stage agents, run
git, the configured commands and the gate scripts, edit spec status lines and `tasks.md`
checkboxes, and talk to the user. It also does the authoring stages below: writes requirements.md,
design.md and tasks.md, creates issues, and opens the PR.

**Who does the authoring stages.** Planning (Stages 1 and 2) and publishing (Stage 5) need
continuity with the user, not independence, so the orchestrator does them itself: it reads the
role file (`${CLAUDE_PLUGIN_ROOT}/agents/planner.md`, `${CLAUDE_PLUGIN_ROOT}/agents/publisher.md`) in full and
follows its steps and constraints in this session. Where the role file says to output a handoff
and stop, take that handoff as the stage's result and go on with this runbook. The role's own
critic loop spawns the critic straight from this session. Stages that need independence (critic,
tester, qa-engineer) and the per-task executor are always separate agents.

**Configuration:** resolve `<TEST_CMD>`, `<LINT_CMD>`, `<BUILD_CMD>`, `<DEV_CMD>`, `<DEV_HOST_CMD>`, `<INSTALL_CMD>`, `<DEV_BRANCH>`, `<MAIN_BRANCH>`, `<SOURCE_DIR>`, and `<feature-branch>` from `.claude/sdd/config.json` at the repo root; if absent, auto-detect from `package.json`/`pyproject.toml` and default branches to `main`/`development` and source dir to `src`.

**Working directory:** the calling session's checkout.

---

## Model Selection

For every invocation, use the target role's declared tier and provider default:

- `workhorse`: planner, critic, archivist, publisher — planning, review and publication;
  qa-engineer — exploratory QA; in this pipeline only Stage 4b dispatches it, when explore is on (the `standard` and `strict` default; `--no-explore` opts out).
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
         ↓
         Design Gate → scripts/gate-design.py    → matrix + BDD mapping checked mechanically
Stage 3: Implement → executor (per task)         → strict: Prosecutor (failing tests) then Defender (code)
         ↓
         Mutation Gate → <MUTATE_CMD> (strict, or --mutate) → surviving mutants fed back to executor
         ↓
         Code Critique → critic (code context)   → PASS / REVISE
         ↓
Stage 4: QA      → tester (per task)             → PASS / FAIL
Stage 4b: Explore → qa-engineer (once; standard and strict) → fixes + friction report
Stage 4c: Review → /sdd:review-diff + scripts/gate-review.py → proof-of-bug findings, two passes at most
Stage 5: Publish → publisher*                    → docs verified, PR opened, CI passing
```

\* The orchestrator does this stage itself by following the role file. Every other stage is
always a separate agent, except Stage 4c, which runs the read-only `/sdd:review-diff` skill.

---

## Profiles

The ship skill resolves the profile (`--profile`, then `pipeline.profile`, then `standard`). It
scales the pipeline to the risk of the change. A stage marked `-` is skipped and logged as
`[Orchestrator] <stage>: skipped (profile <name>)`.

| Stage | `fast` | `standard` | `strict` |
|---|---|---|---|
| 1 Spec + critic | - | yes | yes |
| 2 Plan + critic | - | yes | yes, with the full Failure Modes & Degradation Matrix |
| Design Gate | - | `--profile standard` | `--profile strict` |
| 3 Implement | one `full` executor on the change description | one `full` executor per task | Prosecutor then Defender per task |
| Mutation Gate | - | only with `--mutate` | yes, when `commands.mutate` is set |
| Code Critique | - | yes | yes |
| 4 QA (tester) | - | yes | yes |
| 4b Explore | only with `--explore` | yes | yes |
| 4c Review | yes | yes | yes |
| 5 Publish + CI | yes | yes | yes |

`fast` is existing tests plus review-diff plus CI. It writes no domain docs: there is no
requirements, design or tasks file, the executor gets the change description as its one task and
adds a regression test with a fix, and the orchestrator runs `<TEST_CMD>` after it (red goes back to
the executor, max 2 cycles). Use it only for small bugfixes, UI tweaks and docs. If the work needs a
design decision, stop and ask the user to rerun with `--profile standard`.

Explicit flags win over the profile: `--explore` / `--no-explore` for Stage 4b and `--mutate` for
the Mutation Gate. `pipeline.explore` and `pipeline.mutate` in config set a repo default that the
profile does not override.

---

## Stage 1: Spec

First name the domain: a short kebab-case slug of the feature (reuse an existing
`docs/specs/<name>/` when the change belongs to it). `<feature-branch>` follows from it.

Skipped under `fast`: name the branch from a slug of the change and go to Stage 3.

Follow `${CLAUDE_PLUGIN_ROOT}/agents/planner.md` Phase 1 (`--spec-only`) yourself with the domain name,
feature description and mode. requirements.md is written and passes the critic review loop (the
critic is always a separate agent). In interactive mode the stage then waits for the user; handle it
as in **Spec gate** below.

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
spec stage ends with SUCCESS.

After this stage (once the spec is approved, or at once in autonomous mode): unless the session
is already on a feature branch for this change, create `<feature-branch>` from `<DEV_BRANCH>` and
commit the spec to it.

---

## Stage 2: Plan

Skipped under `fast`.

Follow `${CLAUDE_PLUGIN_ROOT}/agents/planner.md` Phase 2 (`--design-and-tasks`, `--issues`) yourself.
requirements.md is read, design.md is written and passes the critic review loop, then tasks.md is
written and issues are created. Under `strict`, design.md's Failure Modes & Degradation Matrix
must be complete: every row has a failure condition, expected behaviour and a test scenario, and
the matrix covers Transport/Network, Concurrency/State and Boundary & Payloads. While planning
(Stages 1 and 2), do not open implementation or test files: plan from the docs, as planner.md
Phase 1 says. If code is already in this conversation, do not base the spec or design on it.

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

### Design Gate

Skipped under `fast`. Once design.md has passed the critic, run the mechanical check:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gate-design.py docs/specs/<domain>/design.md --profile <profile>
```

It validates the Failure Modes & Degradation Matrix (all columns filled, no template
placeholders; under `strict`, the three required categories) and that every row's Test Scenario
maps to a scenario in the design's Test Scenarios, and that at least one BDD scenario exists.
Exit 0 passes; exit 1 prints one `FAIL:` line per problem. On a failure, revise design.md yourself
by following planner.md Phase 2, re-run the critic loop and the gate (max 2 cycles); if it still
fails, escalate. Never edit the script or relax the profile to get past it. Commit design.md and
tasks.md once the gate passes.

---

## Stage 3: Implement

Under `standard`, and under `fast` with the change description as the one task, spawn one
`executor` in `mode: full` per task (red, green, refactor, one commit), with the inputs below.
Under `strict`, Stage 3 is adversarial: tests and implementation are written in two separate
executor invocations so the code cannot be shaped around its own tests, and a mutation gate then
checks the tests actually bite.

Every invocation receives **only**:
- Domain name + task ID (under `fast`: the change description)
- Architecture + Test Scenarios (and Failure Modes Matrix, when present) sections of design.md
  (none under `fast`)
- Contents of tasks.md (none under `fast`)

Do NOT pass: other tasks' diffs, tester history, your internal state.

Under `fast`, after the executor commits, run `<TEST_CMD>` yourself. If it is red, send the output
back to the executor (max 2 cycles), then escalate. Skip to Stage 4c.

### 3a. Prosecutor — author the failing tests (`strict`)

Spawn `executor` in `mode: test-author`. It writes failing tests from the design's Test
Scenarios and Failure Modes Matrix, confirms they fail for the right reason (missing
implementation, not broken syntax), and commits tests only. It writes nothing under
`<SOURCE_DIR>` except test files. Its goal is to break any implementation that does not honour
the design.

### 3b. Defender — implement against read-only tests (`strict`)

Spawn a fresh `executor` in `mode: implement` with the committed test files marked
**READ-ONLY**. It implements the minimum code to pass them, refactors, commits. It must not edit,
delete, skip or weaken any assertion in those files. If it believes a test contradicts the
design, it returns a `TEST_DISPUTE` handoff instead of changing the test.

```json
// Handoff expected:
{
  "stage": "executor",
  "status": "SUCCESS | DESIGN_GAP | TEST_DISPUTE",
  "artifacts": {
    "task_id": 3,
    "test_files": ["src/lib/cart-total.test.ts"],
    "files_changed": ["src/lib/cart-total.ts"],
    "test_result": { "total": 15, "passed": 15, "failed": 0 },
    "commit_sha": "abc123"
  }
}
```

**If DESIGN_GAP:** Route back to the spec or plan stage (`--spec-only` or `--design-and-tasks`; revise it yourself by following planner.md, then re-run the Design Gate) for targeted revision, then resume executor. Under `fast` there is no design: stop and ask the user to rerun with `--profile standard`.

**If TEST_DISPUTE:** Re-run the Prosecutor with the dispute (test, quoted design clause, reason).
The Prosecutor either fixes the test or defends it by citing the design clause. If the
disagreement survives one round, treat it as a `DESIGN_GAP` and route to the planner. Max 1
dispute round per task; the Defender never resolves a dispute by editing tests.

### 3c. Mutation Testing Gate (`strict`, or `--mutate`)

Runs after the unit tests pass, when `commands.mutate` (`<MUTATE_CMD>`) is configured and the
profile is `strict`, `pipeline.mutate` is true or `--mutate` was passed. If `<MUTATE_CMD>` is unset, skip the gate
and record the warning in the run notes.

1. Compute the changed source files: `git diff --name-only <base>..HEAD -- <SOURCE_DIR>`,
   excluding test files.
2. Run `<MUTATE_CMD>` scoped to them (substitute `{changed_files}`), so only the diff is mutated.
3. For each surviving mutant, pass the executor (`mode: kill-mutant`) the file, line, and mutation
   description. It writes a failing test that kills the mutant (red), then confirms the mutant is
   caught, with the production code unchanged unless the mutant exposed a real defect. Commit.
4. Re-run the mutation command. Max 2 cycles. A mutant that is provably equivalent (no
   observable behaviour change) is recorded as such, with its reason, and not counted.
5. If mutants still survive after 2 cycles, escalate to the human; do not proceed to Critique.

---

## Code Critique (after each implement task)

Skipped under `fast`.

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

**If REVISE:** Pass feedback to executor for fixes (max 2 cycles). Do not proceed to QA until critic passes. The critic runs after the Mutation Gate, so it reviews tests that have already survived mutation.

---

## Stage 4: QA

Skipped under `fast`. After code critique passes, spawn `tester` agent with **only**:
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

Exploratory QA is on under `standard` and `strict` and off under `fast`; `--explore` and
`--no-explore` override the profile for one run, and `pipeline.explore` sets the repo default. Skip
this stage when explore is off; log `[Orchestrator] Explore: off` and go to Stage 4c. When explore
is on but the change has nothing to run (docs, config or harness only), skip it too and keep the
line `Exploratory QA skipped: <reason>` for the publisher.

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
to Stage 4c.

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

## Stage 4c: Review

Every profile runs this stage. It is the diff review that replaces a human's first read, with a
proof-of-bug rule so a review cannot block the pipeline on speculation. A review converges in at
most two passes, and `${CLAUDE_PLUGIN_ROOT}/scripts/gate-review.py` enforces the rules.

**Before starting:** the working tree must be clean (commit or discard what earlier stages left),
because review-diff reads the committed change.

1. **Pass 1.** Run `/sdd:review-diff` (read-only; it writes `.review/findings.json`). Then:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gate-review.py .review/findings.json
   ```
   If the gate fails on the file itself (a `high` finding without a reproduction, a verdict that
   contradicts the findings, a malformed field), run `/sdd:review-diff` once more with the printed
   problems; the reviewer downgrades unprovable highs rather than inventing proof. If it still
   fails, escalate.
2. **Verdict `pass`:** go to Stage 5. Carry the summary and any `medium` / `low` findings to the
   publisher as non-blocking review notes.
3. **Verdict `revise`:** keep pass 1 with `cp .review/findings.json .review/pass1.json`. For each
   `high` finding, spawn `executor` (`mode: full`) with the finding's file, line, failure scenario
   and reproduction only: it turns the reproduction into a failing test, fixes the code, and
   commits. Do not pass the review transcript or other findings.
4. **Pass 2.** Run `/sdd:review-diff --verify`, then:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gate-review.py .review/findings.json --previous .review/pass1.json --final
   ```
   The gate checks that pass 2 follows the fix commit on the same base, lists only unresolved
   highs and proven regressions, and ends in `pass`. If it fails, escalate with the remaining
   findings; there is no third pass and no new speculative findings in pass 2.
5. Run `<TEST_CMD>` after any fix commit; red goes back to the executor once, then escalate.

---

## Stage 5: Publish

Follow `${CLAUDE_PLUGIN_ROOT}/agents/publisher.md` yourself with the inputs below:
- Domain name and domain path (`docs/specs/<domain>/`); under `fast` there is none, so skip the
  domain-doc steps and draft the description from the change description and the commits
- When explore was on: the Stage 4b report, or its `Exploratory QA skipped: <reason>` line,
  for an "Exploratory QA" section of the PR description
- The Stage 4c summary and non-blocking findings, for the "Review notes" section

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

**If CI_FAIL (code issue):** route to executor for fixes, then re-run the publish stage. publisher.md
hands a code failure to the orchestrator, which is this session; it routes the failure to the
executor itself.

## State Machine

```
SPEC             → SUCCESS (interactive) → SPEC GATE → PLANNING
                 → SUCCESS (autonomous)  → PLANNING
                 (fast: skipped)         → IMPLEMENTATION
PLANNING         → SUCCESS          → DESIGN_GATE
                 → DESIGN_GAP       → SPEC or PLANNING (targeted revision)

DESIGN_GATE      → exit 0           → IMPLEMENTATION(task 0)
                 → exit 1 (cycle<2) → PLANNING (revise design.md)
                 → exit 1 (cycle=2) → ESCALATION

IMPLEMENTATION   → COMPLETE         → CODE_CRITIQUE(task N)
                 → DESIGN_GAP       → SPEC or PLANNING (targeted revision)

CODE_CRITIQUE    → PASS             → QA(task N)
                 → REVISE (cycle<2) → IMPLEMENTATION(task N, retry)
                 → REVISE (cycle=2) → ESCALATION

QA               → PASS + more tasks → IMPLEMENTATION(task N+1)
                 → PASS + done       → EXPLORING (standard, strict, --explore) | REVIEWING (fast, --no-explore)
                 → FAIL (cycle < 3)  → IMPLEMENTATION(task N, retry)
                 → FAIL (cycle == 3) → ESCALATION

EXPLORING        → skipped / blocked → REVIEWING (skip reason attached)
                 → report            → CHECK_FIXES (critic + <TEST_CMD>)
CHECK_FIXES      → PASS              → REVIEWING (report attached)
                 → REVISE / red      → revert those bugs' test + fix commits → REVIEWING

REVIEWING        → pass 1 pass       → PUBLISHING
                 → pass 1 revise     → FIXING_FINDINGS (executor, highs only) → pass 2
                 → pass 2 pass       → PUBLISHING
                 → pass 2 revise / gate-review fails → ESCALATION (no third pass)

PUBLISHING       → SUCCESS           → DONE
                 → CI_FAIL (code)    → IMPLEMENTATION(fix) → PUBLISHING
                 → CI_FAIL (flake)   → retry once → DONE | ESCALATION
```

---

## Post-run reflection

After Stage 5 (and after `/sdd:fix-pr` when it finishes a PR), run one lightweight retro. It
looks at what the run changed or struggled with and proposes a rule or gate change; it never
edits the harness itself.

1. List the notable harness-relevant events (a gate that fired, a critic loop that needed a
   second round, a skipped stage, a rule the run worked around). Give each a verdict:
   `helped | hurt | no observed effect | confounded`. Prefer `confounded` whenever several things
   changed at once or a single run is all that stands behind the difference. A PASS verdict or a
   merged PR does not establish that a change helped.
2. Emit at most one entry, or the single line `NO_ENTRY`:

   ```
   cue: <the shape of situation, not this task's facts>
   lesson: <a proposed rule or gate change naming the component: skill, script, hook, standard>
   evidence: <the events above it rests on>
   confidence: low | medium | high
   ```
3. A lesson names its component, so it is one step from a `Gate`-column row in
   [harness.md](harness.md#rules-in-this-document). Report it in the final summary as a
   proposal; do not write it into rules, memory or config unprompted.

`NO_ENTRY` is the expected answer for an uneventful run.

---

## Context Engineering Rules

| Stage | Receives | Never receives |
|-------|----------|----------------|
| planner (spec) | feature description, mode, existing docs, this conversation | code, test files |
| planner (plan) | requirements.md, mode, existing docs, this conversation | code, test files |
| executor | design.md (Architecture + Test Scenarios), tasks.md, one task ID | other tasks' diffs, tester history |
| critic (code) | changed source files, design.md (Architecture + Test Scenarios) | other tasks' diffs, tester feedback |
| tester | design.md (QA Scenarios), requirements.md, target scenario | code, diffs, executor reasoning |
| qa-engineer (Stage 4b) | feature description, domain, design.md (QA Scenarios, as context), dev URL, credential variable names | diffs, executor reasoning, tester or critic history |
| critic (code, Stage 4b) | `git diff <START>..HEAD` inline, bug list, design.md (Architecture + Test Scenarios), bug-fix criteria | the exploration transcript |
| executor (Stage 4c fix) | one high finding's file, line, failure scenario and reproduction | other findings, the review transcript |
| publisher | domain, domain path, Stage 4b report or skip reason when explore was on, Stage 4c summary | agent transcripts (it has none) |

---

## Rules

- Specs always come first — no code before Stage 2 completes (except under `fast`, which has no spec by design)
- Critic review is embedded in the planning stages for spec/design; the orchestrator manages code critique directly
- TDD is embedded in executor — red → green → refactor per task
- Tester is adversarial — its job is to find problems
- Domain specs are the single source of truth; route gaps back to spec, never resolve silently
- CI must pass before reporting DONE
- Gate scripts decide what a script can decide; a failing gate is fixed at its source, never skipped or edited

**Escalation** (any `ESCALATION` in the state machine): tell the user which budget ran out, which
gate keeps failing or which design gap needs a decision, and wait for them.

---

## Spec gate

Interactive mode only; `--autonomous` has no gate, and `fast` has no spec. `requirements.md` is at
`Review` and has passed the critic.

Show the user the requirements path and a short summary, and ask them to approve or say what to
change. On changes, revise requirements.md yourself, re-run the critic loop and ask again. On
approval, set the `**Status:**` line of `requirements.md` to `Approved` and continue with Stage 2.
