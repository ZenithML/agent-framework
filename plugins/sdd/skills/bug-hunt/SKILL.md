---
name: bug-hunt
description: >
  Use when one area of the codebase, or all of it, should be hunted for bugs in depth - a
  read-only static audit of the source plus a pass through the running app, merged into one
  prioritised report, then each confirmed bug fixed test-first and the lot opened as one pull
  request. Built to run unattended on a schedule with --autonomous; --report-only stops at the
  report. Does not trigger for poking at one flow (that is /sdd:qa-explore), for reviewing a
  diff or PR (that is /sdd:review-diff or /sdd:review-pr), or for doc conformance (that is
  /sdd:audit).
version: 1.0.0
owner: zenithml
updated: 2026-10-28
source: docs/specs/bug-hunt/design.md
changelog: |
  1.0.0 — Initial release.
---

> **Configuration.** This skill uses project-specific commands and branch names. Resolve each placeholder from `.claude/sdd/config.json` at the repo root (keys: `commands.test`→`<TEST_CMD>`, `commands.testOne`→`<TEST_CMD> <test-file>`, `commands.lint`→`<LINT_CMD>`, `commands.build`→`<BUILD_CMD>`, `commands.dev`→`<DEV_CMD>`, `commands.devHost`→`<DEV_HOST_CMD>`, `commands.install`→`<INSTALL_CMD>`, `branching.devBranch`→`<DEV_BRANCH>`, `branching.mainBranch`→`<MAIN_BRANCH>`, `source.dir`→`<SOURCE_DIR>`, `devServer.url`→ the dev URL, `devServer.credentialEnv`→ credential variable names, `branching.featurePrefix`→`<FEATURE_PREFIX>`, default `feature/`). If `.claude/sdd/config.json` is absent, auto-detect: read `package.json` scripts (npm/pnpm/yarn) or `pyproject.toml`/`Makefile` (python) for test/lint/build/dev commands; default the dev URL to `http://localhost:3000`; default branches to `main` (and `development` only if it exists on the remote); default `<SOURCE_DIR>` to `src`. Use the resolved values wherever a placeholder appears below.

This skill delegates to two roles: `${CLAUDE_PLUGIN_ROOT}/agents/critic.md` (static audit and fix
review) and `${CLAUDE_PLUGIN_ROOT}/agents/qa-engineer.md` (runtime pass and fixes). Before each
delegation, Read the target role in full. In Codex, pass that exact canonical role definition and only this stage's scoped inputs to a fresh native
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

**Usage:** `/sdd:bug-hunt <area | --all> [--report-only] [--autonomous]`

A deep bug hunt over one area: read all of its code for bugs, use it in the running app, merge
both into one prioritised report, then fix each confirmed bug test-first and open one PR.

```
static audit (critic, bugs) + runtime pass (qa-engineer, report-only)
  → triage report → [Human gate] → fixes (qa-engineer, --fix-list) → critic → one PR
```

| Flag | Effect |
|---|---|
| (none) | Full run, with a Human gate between the report and the fixes |
| `--report-only` | Stop after the report; change nothing |
| `--autonomous` | No Human gate: fix and open the PR unattended (for scheduled runs) |
| `--all` | Every area: each domain under `docs/specs/`, or `<SOURCE_DIR>` as one area if there are none |

## Not the same as `/sdd:qa-explore`

`/sdd:qa-explore` pokes at one flow in the running app and fixes what it finds, on the current
branch. `/sdd:bug-hunt` covers a whole area from both sides, the code and the running app, sorts
everything into one report you can approve before anything changes, and ends with a PR.

## Step 1: Resolve the area

1. `<area>` is a spec domain when `docs/specs/<area>/` exists, otherwise a path or a short
   description of a part of the code. Give it a slug (lowercase, `a-z0-9-`, at most 40
   characters; the domain name when there is one) for file and branch names.
2. List the area's surface: its spec files if any (`requirements.md`, `design.md`), the source
   files that implement it (follow imports from the files the spec names, or `Grep` for the
   area's name under `<SOURCE_DIR>`), its tests, and the routes, pages or commands a user reaches
   it through. If the source is more than about 60 files, split it into chunks of related files
   and run Step 2 once per chunk.
3. **`--all`:** the areas are the domains under `docs/specs/`, in alphabetical order. If there
   are none, take the top-level directories under `<SOURCE_DIR>` as areas (never the whole tree
   as one). Run Steps 2 to 4 per area, then Steps 5 to 7 once, with the slug `all`.

## Step 2: Static audit (read-only)

Spawn `critic` with `context: "bugs"` and the area's source files, tests and spec files as
artifacts. `REVISE` carries the findings (`<file>:<lines> | <category> | <P0-P3> | <root cause>`),
`PASS` means none. It changes nothing.

## Step 3: Runtime pass (read-only)

Spawn `qa-engineer` with `--report-only`, the area's routes, pages or commands as the flow, the
dev URL from `devServer.url` and the credential variable names from `devServer.credentialEnv`.
Steps 2 and 3 are independent: run them in parallel when the host can. Never stand up infrastructure: the agent starts `<DEV_HOST_CMD>` only when it is configured. If the app cannot
be reached, keep the static findings and say in the report that the runtime pass did not run and
why.

## Step 4: Triage

Merge both lists into one:

1. **Deduplicate.** A static finding confirmed at runtime is one bug with both kinds of evidence.
2. **Severity.** P0: data loss, security, or a core flow broken. P1: a significant logic or UX
   bug. P2: a minor bug that can misbehave. P3: cosmetic or theoretical.
3. **Fixable?** A bug needs a test that can show it. Keep static-only findings that a unit or
   integration test can reproduce; move the rest, and anything that needs a product decision,
   to "Not fixing" with the reason. UX friction from the runtime pass stays as friction.

Write the report to `.review/bug-hunt/<slug>.md` (`all.md` for `--all`, with one section per
area). Create `.review/.gitignore` containing `*` if it is missing, so reports are never
committed. The report holds a summary (counts by severity), one section per bug (id `B1`,
`B2`…, title, severity, category, root cause, file links, steps to reproduce, evidence), then
friction, then "Not fixing". Describe evidence in words: never paste local evidence paths or
credential values.

If `--report-only`, show the report path and summary and stop. Nothing else is written.

## Step 5: Human gate

Unless `--autonomous`, show the summary and the report path and ask the user to approve the fix
list (they may drop bugs). With `--autonomous`, the fix list is every bug marked fixable. If the fix list is empty, say so and stop: no branch, no commits, no PR.

## Step 6: Fix

1. **Start clean.** The working tree must be clean, with no merge, rebase or cherry-pick in
   progress; otherwise stop and ask the user to commit or stash (with `--autonomous`, stop and
   report). Fixes must never mix with work in progress.
2. **Branch from the audited code.** Note the current branch as `<ORIGINAL>`, then
   `git checkout -b <FEATURE_PREFIX>bug-hunt-<slug>` from the current HEAD, the code that was
   audited, and record `START=$(git rev-parse HEAD)`. The PR's base is `<DEV_BRANCH>`; if the
   current branch is not `<DEV_BRANCH>` and is not already merged into it, say in the PR that it
   builds on that branch.
3. Spawn `qa-engineer` with `--fix-list` and the approved bugs in priority order (P0 first; for
   `--all`, by area in the Step 1 order within each severity), each with its id, root cause,
   evidence and steps to reproduce. It runs its red → root cause → green → revert proof for each
   and commits test and fix separately, with the bug id in both commit messages.
4. **Review the fixes, once.** Spawn `critic` with `context: "code"`, the output of
   `git diff START..HEAD` inline (the critic cannot run git), the bug list, and these criteria,
   which replace the design.md Test Scenarios check for this call: each fix is minimal and
   targets one listed bug; each bug has a regression test; nothing else changed. Each feedback
   item must name the bug id it rejects. Here REVISE means "revert those bugs", not "revise":
   for each named bug, revert both its `test:` and `fix:` commits (`git revert --no-edit`) and
   move it to "Not fixing" with the reason. An item naming no bug is logged and ignored. There
   is no second round.
5. Run `<TEST_CMD>` (and `<LINT_CMD>` when configured). If it fails, revert the commits of the
   bug that breaks it and rerun until green.
6. **Tidy before the PR.** On this unpushed branch, drop each reverted bug's commits and their
   reverts so the PR shows only surviving fixes (`git rebase --onto` or a rebuild with
   `git cherry-pick` of the kept commits from START). If no fix survived, check out
   `<ORIGINAL>`, delete the bug-hunt branch, and report why nothing was fixed.
7. Update the report with the outcome of each bug.

## Step 7: Publish

If at least one fix survived, run `/sdd:create-pr` non-interactively (pass the title and body
directly, never prompt under `--autonomous`) with the title
`fix(<slug>): bug hunt — <n> bugs fixed` (`fix: bug hunt across all areas — <n> bugs fixed` for
`--all`) and the report as the description body: summary, fixed bugs with their tests, not
fixing, friction.

## Scheduling

`--autonomous` makes the run unattended, so it suits a nightly or weekly job, for example
`/sdd:bug-hunt --all --autonomous` from your scheduler of choice. Keep the schedule outside the
repository's harness: this skill does not create one.

See `${CLAUDE_PLUGIN_ROOT}/agents/critic.md` (`bugs` context) and
`${CLAUDE_PLUGIN_ROOT}/agents/qa-engineer.md` (`--report-only`, `--fix-list`).
