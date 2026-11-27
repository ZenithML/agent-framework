---
name: migrate
description: >
  Use when code should move from one framework, library, language version, API, service or data
  format to another with behaviour kept and evidence shown - inventory every use of the old
  thing, choose a pattern (codemod waves, branch by abstraction, strangler fig, expand and
  contract, parallel run), pin behaviour, pilot one slice, migrate in revertable waves each
  checked against the baseline, and open a PR with the evidence. --report-only stops at the
  plan. Does not trigger for hardening a prototype in place (that is /sdd:productionize) or for
  a new feature (that is /sdd:ship).
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

**Usage:** `/sdd:migrate <from> <to> [--area <path>] [--report-only] [--autonomous]`

Examples: `/sdd:migrate jest vitest`, `/sdd:migrate enzyme "react testing library"`,
`/sdd:migrate "python 3.10" "python 3.13"`, `/sdd:migrate axios fetch --area src/api`.

Move code from `<from>` to `<to>` without changing what it does, in steps that can each be
undone, and prove it.

```
inventory → pattern + plan → baseline + safety net → [Human gate] → pilot slice
  → waves (executor tidy → checks → critic → snapshot, revert on regression) → contract → one PR
```

Read `${CLAUDE_PLUGIN_ROOT}/standards/refactoring.md` in full before Step 1. Its seven rules,
task labels, behaviour-preservation criteria, migration patterns and evidence gates are the
contract for this skill.

| Flag | Effect |
|---|---|
| (none) | Inventory, plan, Human gate, then pilot, waves and the PR |
| `--area` | Limit the migration to this path; the rest of the codebase is not touched |
| `--report-only` | Stop after the plan; change nothing |
| `--autonomous` | No Human gate: proceed with the recommended plan, but never add a tool or dependency beyond `<to>` itself and never run a contract step that cannot be undone |

## Step 1: Inventory

1. Slug: `<from>-to-<to>`, lowercase, `a-z0-9-`, at most 40 characters.
2. Find every use of `<from>` in scope (`--area`, else the repository, excluding vendored and
   generated code): imports and requires, configuration files, build and CI scripts, API calls,
   types, docs that tell people how to run things. `Grep` for each form; read the official
   migration guide of `<to>` (or `<from>`'s upgrade notes) when one exists, and list its
   breaking changes that apply here.
3. Write the **usage query**: one shell command that prints `METRIC old_usages=<n>` (for example
   a `grep -rE ... | wc -l` wrapped in `printf`). It is the progress measure and must reach 0, or
   the listed exceptions, by the end.
4. Group the uses into **slices** that can move on their own (a module, a directory, a route, a
   test folder), smallest dependency first. Note for each its size and what tests cover it.

## Step 2: Pattern and plan

1. Choose one pattern from the standard's Migration patterns table and say why it fits better
   than the next best. Look for an official codemod or upgrade tool first; a repeatable
   transform is a codemod, and the agent handles what it leaves.
2. Choose the **equivalence oracle** for the risk: the existing tests, plus characterization or
   golden-master tests where coverage of a slice is thin, plus a differential run of old and new
   on the same inputs where a silent difference is costly. When the tests themselves are being
   migrated (a test framework), the oracle is the test inventory: every baseline test still
   exists under the same name and passes, and the mutation score of the code under test does not
   drop.
3. Plan **waves**: the pilot (one small slice that is representative of the hard cases), then
   waves of slices, each small enough to review and revert as one commit. Write the rollback for
   each wave and for the contract step.
4. List any tool or dependency to add beyond `<to>` (a codemod runner, a test helper). Each one
   needs the user's approval: a project's stack is its owner's decision.

Write `.review/migrate/<slug>.md`: inventory with counts per slice, the usage query, breaking
changes, pattern and reason, oracle, waves with rollback, tools to add, and risks. Create
`.review/.gitignore` containing `*` if it is missing.

If `--report-only`, show the plan path and summary and stop.

## Step 3: Baseline and safety net

1. **Start clean.** The working tree must be clean with no merge or rebase in progress; otherwise
   stop and ask the user to commit or stash (with `--autonomous`, stop and report).
2. Branch `<FEATURE_PREFIX>migrate-<slug>` from the current HEAD and record
   `START=$(git rev-parse HEAD)`.
3. Snapshot the baseline, with the usage query as a metric command:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py snapshot --label baseline --out .review/evidence/<slug> --paths <slice paths> --metric-cmd '<usage query>'
   ```
   A red baseline stops the migration: report it; a migration over a red suite proves nothing.
4. For each slice the plan marks as thinly covered, spawn `executor` in `mode: characterize` with
   the slice's entry points. For a parallel run, the characterize task also writes the
   differential test (old and new called on the same inputs, outputs compared), skipped until
   the new path exists.

## Step 4: Human gate

Unless `--autonomous`, show the plan summary and ask the user to approve the pattern, waves,
oracle and any tools to add. They may change the plan. With `--autonomous`, follow the plan as
written, without any tool that needs approval; if the plan cannot work without one, stop and
report.

## Step 5: Pilot

Migrate the pilot slice as wave 0 (the wave loop below). Then, before the other waves, record
what failed and why (build errors, test failures, the codemod's misses), and fix the codemod,
the instructions or the plan so the next waves do not repeat it. If the pilot cannot be made
green in two attempts, stop and report: the plan is wrong (rule 7 of the standard).

## Step 6: Waves

For each wave, in order:

1. Spawn `executor` in `mode: tidy` with the wave's slices, the plan's pattern and oracle, the
   breaking changes, the pilot's lessons, and, for a test framework migration, the note that the
   tests are the subject. Run the codemod first when the plan has one, then let the executor
   finish the slice. One commit per wave: `refactor(migrate): wave <n> - <slices>`.
2. Run `<TEST_CMD>`, and `<TYPECHECK_CMD>`, `<LINT_CMD>` and `<BUILD_CMD>` when configured. On
   failure, feed the output back to the executor (max 2 cycles).
3. Spawn `critic` with `context: "code"`, the wave's diff inline (`git diff <prev>..HEAD`; the
   critic cannot run git) and the standard's behaviour-preservation criteria in place of the
   design.md Test Scenarios check.
4. Snapshot and compare with the baseline:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py snapshot --label wave-<n> --out .review/evidence/<slug> --paths <slice paths> --metric-cmd '<usage query>'
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py compare .review/evidence/<slug>/baseline.json .review/evidence/<slug>/wave-<n>.json --lower-is-better old_usages
   ```
   The usage count must fall by the wave's share, and nothing else may regress (exit 1 is a
   failed wave, handled as in item 5).
5. A wave that still fails after its cycles is reverted (`git revert --no-edit <wave commit>`),
   and its slices go to "Not migrated" with the reason, or back to the pilot loop once. Never
   start the next wave on a red tree.

## Step 7: Contract

Once every wave is green, remove what only existed for the move: the old dependency, adapters,
flags, the abstraction layer when it is no longer wanted, dual writes. This is a `tidy` like the
waves. It must stay out of this run when it touches production state that cannot be restored
(a dropped column, a deleted queue, a decommissioned service): list it in the PR as a follow-up
for after the user confirms the deploy is healthy.

## Step 8: Evidence and publish

1. Snapshot `--label after` the same way and compare it with the baseline, adding
   `--md .review/evidence/<slug>/evidence.md`.
   `old_usages` must be 0, or every remaining use must be a listed exception. A regression goes
   back to Step 6's fix cycle; if it remains, stop and report instead of publishing.
2. Tidy the branch: drop reverted waves and their reverts so the PR shows only waves that
   landed (`git rebase --onto` or `git cherry-pick` from START). If no wave survived, check out
   the original branch, delete the migration branch, and report why.
3. Run `/sdd:create-pr` (pass title and body directly; never prompt under `--autonomous`).
   Title: `refactor: migrate <from> to <to>` with the area as scope when `--area` is set, or the
   repository's own convention for the change (a dependency upgrade may be `build:` or `chore:`).
   Body: summary; pattern and why; `## Evidence` with the comparison table and the usage count
   before and after; waves (slices, commit, result); not migrated, with reasons; rollback per
   wave; follow-ups (contract steps held back). When the diff is large, suggest
   `/sdd:triage-pr` to the reviewer.

See `${CLAUDE_PLUGIN_ROOT}/agents/executor.md` (`characterize`, `tidy`) and
`${CLAUDE_PLUGIN_ROOT}/agents/critic.md` (`code` context).
