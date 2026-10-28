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

> **Configuration.** This skill uses project-specific commands and branch names. Resolve each placeholder from `.claude/sdd/config.json` at the repo root (keys: `commands.test`→`<TEST_CMD>`, `commands.testOne`→`<TEST_CMD> <test-file>`, `commands.lint`→`<LINT_CMD>`, `commands.build`→`<BUILD_CMD>`, `commands.dev`→`<DEV_CMD>`, `commands.devHost`→`<DEV_HOST_CMD>`, `commands.install`→`<INSTALL_CMD>`, `branching.devBranch`→`<DEV_BRANCH>`, `branching.mainBranch`→`<MAIN_BRANCH>`, `source.dir`→`<SOURCE_DIR>`, `devServer.url`→ the dev URL, `devServer.credentialEnv`→ credential variable names). If `.claude/sdd/config.json` is absent, auto-detect: read `package.json` scripts (npm/pnpm/yarn) or `pyproject.toml`/`Makefile` (python) for test/lint/build/dev commands; default the dev URL to `http://localhost:3000`; default branches to `main` (and `development` only if it exists on the remote); default `<SOURCE_DIR>` to `src`. Use the resolved values wherever a placeholder appears below.

Before each delegation, Read the target role in full: `${CLAUDE_PLUGIN_ROOT}/agents/critic.md`
for the static audit and `${CLAUDE_PLUGIN_ROOT}/agents/qa-engineer.md` for the runtime pass and
the fixes. In Codex, pass
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
   description of a part of the code. With `--all`, run Steps 2 to 4 once per area and Steps 5
   to 7 once for all of them.
2. List the area's surface: its spec files if any (`requirements.md`, `design.md`), the source
   files that implement it (follow imports from the files the spec names, or `Grep` for the
   area's name under `<SOURCE_DIR>`), its tests, and the routes, pages or commands a user reaches
   it through.
3. Record `START=$(git rev-parse HEAD)` and check the working tree is clean. If it is not, stop
   and ask the user to commit or stash first (with `--autonomous`, stop and report): the fixes
   must not mix with work in progress.

## Step 2: Static audit (read-only)

Spawn `critic` with `context: "bugs"`, the area's source files, its tests and its spec files as
artifacts. It returns findings, each with file, line range, category, severity (P0 to P3) and
root cause. It changes nothing.

## Step 3: Runtime pass (read-only)

Spawn `qa-engineer` with `--report-only`, the area's routes, pages or commands as the flow, the
dev URL from `devServer.url` and the credential variable names from `devServer.credentialEnv`.
Never stand up infrastructure: the agent starts `<DEV_HOST_CMD>` only when it is configured. If
the app cannot be reached, skip this step, keep the static findings, and say in the report that
the runtime pass did not run and why.

## Step 4: Triage

Merge both lists into one:

1. **Deduplicate.** A static finding confirmed at runtime is one bug with both kinds of evidence.
2. **Severity.** P0: data loss, security, or a core flow broken. P1: a significant logic or UX
   bug. P2: a minor bug or code-quality issue that can misbehave. P3: cosmetic or theoretical.
3. **Fixable?** A bug needs a test that can show it. Keep static-only findings that a unit or
   integration test can reproduce; move the rest, and anything that needs a product decision,
   to "Not fixing" with the reason. UX friction from the runtime pass stays as friction.

Write the report to `.review/bug-hunt/<area>.md` (create `.review/.gitignore` containing `*` if
it is missing, so the report is never committed): a summary (counts by severity), then one
section per bug with title, severity, category, root cause, file links, steps to reproduce and
the evidence, then friction, then "Not fixing".

If `--report-only`, show the report path and summary and stop.

## Step 5: Human gate

Unless `--autonomous`, show the summary and the report path and ask the user to approve the fix
list (they may drop bugs). Fix only what they approve. With `--autonomous`, fix every bug marked
fixable.

## Step 6: Fix

1. Create the branch `<featurePrefix>bug-hunt-<area>` (`bug-hunt-all` for `--all`) from
   `<DEV_BRANCH>`.
2. Spawn `qa-engineer` with `--fix-list` and the approved bugs in priority order (P0 first),
   each with its root cause, evidence and steps to reproduce. It skips exploring and runs its
   red → root cause → green → revert proof for each, committing test and fix separately.
3. Spawn `critic` with `context: "code"` on the files changed in `<START>..HEAD`, the area's
   design.md Architecture section if there is one, and these criteria: each fix is minimal and
   targets one listed bug, each has a regression test, nothing else changed. For each bug the
   critic rejects, revert both its `test:` and `fix:` commits (`git revert`, never a history
   rewrite) and move it to "Not fixing" with the reason.
4. Run `<TEST_CMD>` (and `<LINT_CMD>` when configured). If it fails, revert the commits of the
   bug that breaks it and rerun until green.
5. Update the report with the outcome of each bug.

## Step 7: Publish

If at least one fix survived, run `/sdd:create-pr` with the title
`fix(<area>): bug hunt — <n> bugs fixed` and the report as the description body (summary, fixed
bugs with their tests, not fixing, friction). Otherwise open no PR and report why.

## Scheduling

`--autonomous` makes the run unattended, so it suits a nightly or weekly job, for example
`/sdd:bug-hunt --all --autonomous` from your scheduler of choice. Keep the schedule outside the
repository's harness: this skill does not create one.

See `${CLAUDE_PLUGIN_ROOT}/agents/critic.md` (`bugs` context) and
`${CLAUDE_PLUGIN_ROOT}/agents/qa-engineer.md` (`--report-only`, `--fix-list`).
