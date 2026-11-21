# Refactoring with Evidence — Requirements

**Status:** Approved
**Last Updated:** 2026-11-21

## Problem Statement

The harness is built for new features: spec, tests first, implement. Two common jobs do not fit
that shape. Taking a proof of concept to production starts from code that works but has no
safety net, no readiness bar and no record of what "better" means. A migration (a framework, a
library, a language version, a data format) changes many files at once, where tests passing is
weak evidence that behaviour was kept. Agents doing either today make claims ("cleaner",
"safer", "faster") without numbers, mix structural and behavioural edits in one commit, and push
through steps that should have been reverted.

## Goals

1. One skill that scores an area against a production-readiness rubric with evidence, and closes
   the approved gaps through the existing `/sdd:ship` pipeline.
2. One skill that migrates from one thing to another in revertable waves, piloted first, each
   wave checked against a baseline.
3. Both pin current behaviour before changing it and keep structural and behavioural commits
   apart.
4. Both end with a before/after evidence table produced by a script, and a regression blocks
   the PR.
5. Nothing project-specific: everything comes from `.claude/sdd/config.json`, and no tool is
   added to a project without the user's decision.

## Out of Scope

- Running production deploys, data backfills or any contract step that cannot be undone.
- Installing coverage, mutation or benchmark tools. Missing keys are reported as gaps.
- Differential fuzzing, shadow traffic and architecture fitness functions as built-in gates
  (recorded in the research note as later work).
- Stacked PRs per migration wave.

## User Stories & Acceptance Criteria

### Story 1: Evidence

- Given `evidence.py snapshot --label <name>`, Then each configured check among typecheck, lint,
  build, test, coverage, mutate and bench is run and its pass/fail and duration recorded, with
  test counts, line coverage, mutation score, benchmark median, `METRIC name=value` lines and the
  size of `--paths` where readable, under `.review/` with a `.gitignore` of `*`.
- Given `evidence.py compare BEFORE AFTER`, Then a Markdown table is printed and the exit code is
  1 when a check that passed now fails, a check stays red, failing tests increase, passing tests
  decrease (unless `--allow-fewer-tests`), coverage or mutation score drops beyond the tolerance,
  the benchmark is slower beyond the tolerance, a gated metric regresses, or something measured
  before is missing after.

### Story 2: Productionize

- Given `/sdd:productionize <area>`, Then a baseline snapshot is taken before any change, and a
  report under `.review/productionize/` marks R1 to R10 Ready, Partial, Missing or N/A, each with
  evidence, and lists gaps with severities.
- Given `--report-only`, Then nothing outside `.review/` is written, and no branch, commit or PR
  is made.
- Given no `--autonomous`, Then no code changes until the user approves the gap list.
- Given approval, Then the ship runbook runs with tasks ordered `[characterize]`, `[tidy]`,
  `[change]`, and a red baseline suite is fixed first.
- Given the final comparison regresses after two fix cycles, Then no PR is opened.

### Story 3: Migrate

- Given `/sdd:migrate <from> <to>`, Then every use of `<from>` in scope is inventoried with a
  usage query printing `METRIC old_usages`, and the plan names a pattern, an oracle, waves and a
  rollback per wave.
- Given `--report-only`, Then nothing outside `.review/` is written.
- Given a red baseline, Then the migration stops before any wave.
- Given a wave that is still red after two fix cycles, Then its commit is reverted, its slices
  are listed as not migrated, and the next wave does not start on a red tree.
- Given a contract step that touches production state that cannot be restored, Then it is not
  run and is listed as a follow-up.

### Story 4: Executor modes

- Given `mode: characterize`, Then the executor writes tests that pass on unchanged code, shows
  each fails once under a deliberate break, and changes no product code.
- Given `mode: tidy`, Then the executor stops on a red suite, edits no test file (except
  translating tests that are the migration's subject, keeping every assertion), and returns
  `BEHAVIOUR_CHANGE` when a test would have to change.

## Constraints

- Scripts are python3 standard library only, like the existing gates.
- Reuse the `critic` and `executor` roles; no new agent.
- `commands.typecheck`, `commands.coverage` and `commands.bench` are optional schema additions
  (MINOR bump).

## References

- [`plugins/sdd/standards/refactoring.md`](../../../plugins/sdd/standards/refactoring.md)
- [`docs/research/refactoring-evidence.md`](../../research/refactoring-evidence.md)
