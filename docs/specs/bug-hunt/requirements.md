# Bug Hunt — Requirements

**Status:** Approved
**Last Updated:** 2026-10-28

## Problem Statement

`/sdd:qa-explore` pokes at one flow in the running app. Nothing in the harness looks at a whole
area from both sides, its code and its running behaviour, and turns what it finds into one
reviewed PR. A consumer repo kept its own `/bug-hunt` for this, with its backend, paths and test
command baked in.

## Goals

1. One skill that audits an area's code (read-only), uses it in the running app (read-only),
   and merges both into one prioritised report.
2. The user approves the fix list before any code changes, unless the run is unattended.
3. Every fix lands test-first, is checked by the critic, and ships in one PR.
4. Nothing project-specific: it works from `.claude/sdd/config.json` alone.

## Out of Scope

- Creating the schedule itself. `--autonomous` makes a run unattended; the scheduler is the
  user's.
- New roles. The skill reuses `critic` and `qa-engineer`.

## User Stories & Acceptance Criteria

### Story 1: Report

- Given `/sdd:bug-hunt <area>`, Then the critic (context `bugs`) audits the area's code, and
  `qa-engineer --report-only` uses it in the running app, and both are merged into
  `.review/bug-hunt/<area>.md` with severities P0–P3, deduplicated, never committed.
- Given the app cannot be reached and `commands.devHost` is not set, Then no infrastructure is
  started and the report says the runtime pass did not run and why.

### Story 2: Gate

- Given no `--autonomous`, Then no code changes until the user approves the fix list.
- Given `--report-only`, Then nothing is changed, branched, committed or opened.

### Story 3: Fix and publish

- Given an approved list, Then `qa-engineer --fix-list` fixes each bug with a failing test first,
  the critic reviews `START..HEAD`, rejected or suite-breaking bugs have both their test and fix
  commits reverted, and one PR `fix(<area>): bug hunt — <n> bugs fixed` is opened when at least
  one fix survives.
- Given a finding no test can show, Then it is listed under "Not fixing", not changed.

## Constraints

- The static audit stays read-only (critic's tool contract).
- The working tree must be clean before a run that may fix.

## References

- [`../qa-explore/`](../qa-explore/requirements.md)
