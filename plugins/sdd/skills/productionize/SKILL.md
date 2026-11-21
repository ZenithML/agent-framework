---
name: productionize
description: >
  Use when a proof of concept, prototype or hackathon codebase (or one area of it) should be made
  production-ready with evidence - score it against a production-readiness rubric, pin current
  behaviour with characterization tests, close the approved gaps through the /sdd:ship pipeline
  in labelled characterize, tidy and change tasks, and open a PR carrying a before/after evidence
  table. --report-only stops at the readiness report. Does not trigger for moving to a new
  framework, library or platform (that is /sdd:migrate), for a bug hunt (that is
  /sdd:bug-hunt), or for one new feature (that is /sdd:ship).
version: 1.0.0
owner: zenithml
updated: 2026-11-21
source: docs/specs/refactoring/design.md
changelog: |
  1.0.0 — Initial release.
---

> **Configuration.** This skill uses project-specific commands and branch names. Resolve each placeholder from `.claude/sdd/config.json` at the repo root (keys: `commands.test`→`<TEST_CMD>`, `commands.testOne`→`<TEST_CMD> <test-file>`, `commands.lint`→`<LINT_CMD>`, `commands.build`→`<BUILD_CMD>`, `commands.dev`→`<DEV_CMD>`, `commands.devHost`→`<DEV_HOST_CMD>`, `commands.install`→`<INSTALL_CMD>`, `commands.typecheck`→`<TYPECHECK_CMD>`, `commands.coverage`→`<COVERAGE_CMD>`, `commands.mutate`→`<MUTATE_CMD>`, `commands.bench`→`<BENCH_CMD>`, `branching.devBranch`→`<DEV_BRANCH>`, `branching.mainBranch`→`<MAIN_BRANCH>`, `source.dir`→`<SOURCE_DIR>`, `devServer.url`→ the dev URL, `devServer.credentialEnv`→ credential variable names, `branching.featurePrefix`→`<FEATURE_PREFIX>`, default `feature/`). If `.claude/sdd/config.json` is absent, auto-detect: read `package.json` scripts (npm/pnpm/yarn) or `pyproject.toml`/`Makefile` (python) for test/lint/build/dev commands; default the dev URL to `http://localhost:3000`; default branches to `main` (and `development` only if it exists on the remote); default `<SOURCE_DIR>` to `src`. Use the resolved values wherever a placeholder appears below.

This skill delegates to two roles: `${CLAUDE_PLUGIN_ROOT}/agents/critic.md` (assessment and
review) and `${CLAUDE_PLUGIN_ROOT}/agents/executor.md` (characterization tests and changes). Before each
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
contract in `${CLAUDE_PLUGIN_ROOT}/standards/agent-pipeline.md`. The script `${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py` is plain python3 (standard library),
so it runs the same in every host.

**Usage:** `/sdd:productionize <area | --all> [--report-only] [--autonomous] [--profile standard|strict]`

Take working-but-rough code to production quality and prove it: measure it, score it against
the rubric, lock its behaviour, close the gaps in small labelled steps, and show the numbers.

```
baseline evidence → readiness assessment (critic + facts) → report → [Human gate]
  → /sdd:ship run: [characterize] → [tidy] → [change] tasks → evidence gate → one PR
```

Read `${CLAUDE_PLUGIN_ROOT}/standards/refactoring.md` in full before Step 1. Its seven rules,
task labels, behaviour-preservation criteria, rubric (R1 to R10) and evidence gates are the
contract for this skill.

| Flag | Effect |
|---|---|
| (none) | Assess, report, Human gate on the gap list, then build and open the PR |
| `--report-only` | Stop after the readiness report; change nothing |
| `--autonomous` | No Human gate: close every P0 and P1 gap and open the PR unattended |
| `--profile` | Passed to the `/sdd:ship` run. Default `standard`; use `strict` when the area handles money, auth or personal data |

## Step 1: Resolve the area

1. `<area>` is a spec domain when `docs/specs/<area>/` exists, otherwise a path or a short
   description. Give it a slug (lowercase, `a-z0-9-`, at most 40 characters). `--all` means the
   whole of `<SOURCE_DIR>` with the slug `all`.
2. List its surface: source files, tests, and the entry points a user or caller reaches it
   through (routes, pages, commands, exported functions). These entry points are what the safety
   net must cover. Record the area's paths; every evidence snapshot uses them as `--paths`.

## Step 2: Baseline evidence

Run, on the code as it is:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py snapshot --label baseline --out .review/evidence/<slug> --paths <area paths>
```

Unset `commands.*` keys are skipped and noted; list each as a gap under R1, R6 or R8 rather
than adding a tool. If `<TEST_CMD>` is red at baseline, record it as a P0 gap ("suite is red at
baseline") and keep going with the assessment; Step 5 must close it before any other task.

## Step 3: Readiness assessment (read-only)

1. **Facts, gathered in this session.** For each rubric item, collect what a command or search
   can show without changing anything: a lockfile and pinned versions, CI workflows and what they
   run, `Grep` for hard-coded secrets, hosts and credentials, empty `catch`/`except` blocks,
   network calls without a timeout, `TODO`/`FIXME`/`HACK`, debug prints, unbounded queries; the
   ecosystem's dependency audit only when it is already available offline in the project (for
   example `npm audit`, `pnpm audit`, `pip-audit`). Never install a tool for the assessment.
2. **Judgment, from the critic.** Spawn `critic` with `context: "bugs"`, the area's source,
   tests and spec files as artifacts, and these added criteria: "Also report every gap against
   the production-readiness rubric (R1 to R10) in the refactoring standard, with the rubric id as
   the category." Its pipe-form findings (`<file>:<lines> | <category> | <P0-P3> | <root cause>`)
   become gaps.
3. **Score.** For each of R1 to R10, mark Ready, Partial, Missing or N/A, and give the evidence
   for the mark: a file and line, a command and its result, or what was searched for and not
   found. A mark without evidence is Partial at best.
4. **Gaps.** Each gap gets an id (`G1`, `G2`…), its rubric id, severity (P0: data loss, security,
   or the core flow can break in production; P1: an outage or an incident nobody would see; P2:
   operational pain; P3: polish), the evidence, and the smallest change that closes it.

Write `.review/productionize/<slug>.md`: scorecard (R1 to R10 with mark and evidence), gaps by
severity, baseline evidence (the snapshot summary), and the suspect behaviour worth a product
decision. Create `.review/.gitignore` containing `*` if it is missing.

If `--report-only`, show the report path and the scorecard and stop.

## Step 4: Human gate

Unless `--autonomous`, show the scorecard and gap list and ask the user which gaps to close
(default: all P0 and P1). Anything that changes what users see or what the product promises is
the user's call: list it, never decide it. With `--autonomous`, the list is every P0 and P1 gap
whose fix does not change user-facing behaviour. An empty list stops here: no branch, no commits,
no PR.

## Step 5: Build through the ship pipeline

Follow `${CLAUDE_PLUGIN_ROOT}/standards/ship-runbook.md` from Stage 1 with the domain
`productionize-<slug>`, the profile from `--profile`, `--autonomous` when given, and the approved
gaps plus the readiness report as the feature input. The runbook applies unchanged, with these
additions:

1. **Requirements:** one story per approved gap, its acceptance criteria stating the evidence
   that closes it (a test, a check that now passes, a metric).
2. **Tasks, labelled and ordered** as the standard's Task labels say:
   - First, the P0 "suite is red" gap when present, as a `[change]` task.
   - Then `[characterize]` tasks covering every entry point from Step 1 that the baseline tests do
     not already cover.
   - Then `[tidy]` tasks that make the gaps easy to close (extract a seam, isolate config, split
     a module), each behaviour-preserving.
   - Then one or more `[change]` tasks per gap, each naming its gap id.
3. **Stage 3, per label:** `[characterize]` spawns the executor in `mode: characterize`;
   `[tidy]` in `mode: tidy`; `[change]` as the runbook says for the profile. A `BEHAVIOUR_CHANGE`
   handoff from a tidy is routed like a `DESIGN_GAP`: replan it as a `[change]` task.
4. **Code critique for `[tidy]`:** pass the critic the standard's behaviour-preservation criteria
   in place of the design.md Test Scenarios check, with the task's diff inline (the critic cannot
   run git). For `[characterize]`, pass: "tests pass on unchanged code; assert outputs through
   entry points, not internals; the handoff shows each test was made to fail once".

## Step 6: Evidence gate

Before the runbook's publish stage:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py snapshot --label after --out .review/evidence/<slug> --paths <area paths>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py compare .review/evidence/<slug>/baseline.json .review/evidence/<slug>/after.json --md .review/evidence/<slug>/evidence.md
```

A regression is fixed, not explained away: send it to the executor as a fix cycle (max 2), then
rerun both commands. Pass `--allow-fewer-tests` only when a task deliberately removed tests, and
say which and why in the PR. If it still regresses, stop and report to the user; do not publish.
Re-score the rubric items the gaps touched, with the new evidence.

## Step 7: Publish

The runbook's publish stage opens the PR. Its title is `feat(<slug>): production-ready <area>`
(or the repository's own convention for the change), and its body adds, after the runbook's
sections:

- `## Readiness`: the scorecard before and after for the touched items, and every gap with its
  outcome (closed with evidence, or not closed and why).
- `## Evidence`: the table from `.review/evidence/<slug>/evidence.md`.
- `## Suspect behaviour`: what the characterization tests pinned that looks wrong, for the user
  to decide on later.

Never paste local evidence paths or credential values into the PR.

See `${CLAUDE_PLUGIN_ROOT}/agents/critic.md` (`bugs` and `code` contexts) and
`${CLAUDE_PLUGIN_ROOT}/agents/executor.md` (`characterize`, `tidy`).
