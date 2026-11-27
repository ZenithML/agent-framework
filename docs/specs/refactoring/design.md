# Refactoring with Evidence — Design

**Status:** Approved
**Last Updated:** 2026-11-21

## Decision

Add two skills to the `sdd` plugin, `productionize` and `migrate`, a shared standard
(`standards/refactoring.md`), a stdlib script (`scripts/evidence.py`) and two executor modes
(`characterize`, `tidy`). `productionize` wraps a `/sdd:ship` run; `migrate` runs its own wave
loop, because waves over slices do not map onto spec tasks.

### Alternatives considered

| Option | Why not |
|---|---|
| A separate `refactor` plugin | Could not reuse `critic`, `executor` and the runbook through `${CLAUDE_PLUGIN_ROOT}`, and flat installs would need a second copy step |
| One generic `/sdd:refactor` skill | The two jobs differ where it matters: one starts from a readiness bar and closes gaps, the other moves call sites in waves with rollback |
| A new `critic` context for behaviour preservation | Inline criteria in `code` context (the bug-hunt pattern) cover it without another context to maintain |
| Evidence as prose written by the agent | Not reproducible; a script reads the same numbers in every host and gates on them |

## Architecture

- `plugins/sdd/scripts/evidence.py`: `snapshot` runs `commands.{typecheck,lint,build,test,coverage,mutate,bench}`
  through the shell from the repo root, parses runner summaries (Jest, Vitest, pytest, unittest,
  node, go), coverage (istanbul json-summary or text, coverage.py json or text, Cobertura, go),
  mutation (Stryker JSON, PIT, cargo-mutants, a generic "mutation score" line) and `METRIC` lines;
  report files count only when written during the run. `compare` builds rows and problems; exit 1
  on any problem.
- `plugins/sdd/standards/refactoring.md`: seven rules, task labels with executor mode and critic
  criteria, behaviour-preservation criteria, evidence gates, rubric R1 to R10, migration
  patterns, tools per ecosystem.
- `plugins/sdd/agents/executor.md`: `characterize` and `tidy` modes and the `BEHAVIOUR_CHANGE`
  handoff.
- `plugins/sdd/skills/productionize/SKILL.md` and `plugins/sdd/skills/migrate/SKILL.md`, both
  strict-frontmatter with three evals.
- Config schema: optional `commands.typecheck`, `commands.coverage`, `commands.bench`.

## Failure Modes & Degradation Matrix

| Category | Failure Condition | Expected System Behavior | Test Scenario |
|---|---|---|---|
| Boundary & Payloads | A configured command's output matches no known runner format | The count or percentage is recorded as null and shown as n/a; pass/fail still gates | Unrecognised output yields no test counts |
| Boundary & Payloads | A coverage or mutation report on disk predates the run | It is ignored | A stale report is ignored |
| Concurrency/State | A check measured in the baseline is not run afterwards | The comparison fails with "not measured after" | A check missing after is a regression |
| Transport/Network | A command hangs | It is stopped at `--timeout` and recorded as a failure (exit 124) | A command over the timeout is recorded as failed |

## Test Scenarios

**Scenario:** Unrecognised output yields no test counts
Given output with no runner summary, When parsed, Then test counts are null.

**Scenario:** A stale report is ignored
Given a coverage summary older than the run, When a snapshot reads coverage, Then it is not used.

**Scenario:** A check missing after is a regression
Given a baseline with lint and an after snapshot without it, When compared, Then exit 1 with "not measured after".

**Scenario:** A command over the timeout is recorded as failed
Given a command that runs past `--timeout`, When snapshotted, Then its exit is 124 and it is not ok.

**Scenario:** Regressions fail the comparison
Given coverage down 10 points, a lint failure and a failing test, When compared, Then each is listed as a problem and exit is 1.

**Scenario:** Skill contracts hold
Given the two SKILL.md files, Then they carry their usage lines, the Human gate, `--report-only`, the evidence commands, the executor modes, and no project-specific names.

## QA Scenarios

1. In a repo with `.claude/sdd/config.json` setting `test` and `coverage`, run `evidence.py snapshot --label baseline`, change nothing, snapshot `after`, compare: the table shows no regressions and exit 0.
2. Delete a test and snapshot again: compare exits 1 naming passing tests; with `--allow-fewer-tests` it exits 0.
3. Run `/sdd:productionize <area> --report-only`: only `.review/` changes.
4. Run `/sdd:migrate <from> <to> --report-only`: only `.review/` changes, and the plan names a pattern and a rollback per wave.
