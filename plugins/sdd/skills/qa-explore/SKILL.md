---
name: qa-explore
description: >
  Use when someone wants a running app played with like a human tester - poke at a feature or
  flow, find bugs and UX friction, and fix what is broken with a regression test per bug. Works
  on web apps through a browser and on CLI or TUI apps through the shell; --report-only explores
  without changing anything. Does not trigger for one task's QA Scenarios inside a pipeline run
  (that is /sdd:qa or /sdd:ship), for running the existing test suite (that is /sdd:test), or
  for implementing a planned task (that is /sdd:implement).
version: 1.0.0
owner: zenithml
updated: 2026-10-28
source: docs/specs/qa-explore/design.md
changelog: |
  1.0.0 — Initial release.
---

> **Configuration.** This skill uses project-specific commands and branch names. Resolve each placeholder from `.claude/sdd/config.json` at the repo root (keys: `commands.test`→`<TEST_CMD>`, `commands.testOne`→`<TEST_CMD> <test-file>`, `commands.lint`→`<LINT_CMD>`, `commands.build`→`<BUILD_CMD>`, `commands.dev`→`<DEV_CMD>`, `commands.devHost`→`<DEV_HOST_CMD>`, `commands.install`→`<INSTALL_CMD>`, `branching.devBranch`→`<DEV_BRANCH>`, `branching.mainBranch`→`<MAIN_BRANCH>`, `source.dir`→`<SOURCE_DIR>`, `devServer.url`→ the dev URL, `devServer.credentialEnv`→ credential variable names). If `.claude/sdd/config.json` is absent, auto-detect: read `package.json` scripts (npm/pnpm/yarn) or `pyproject.toml`/`Makefile` (python) for test/lint/build/dev commands; default the dev URL to `http://localhost:3000`; default branches to `main` (and `development` only if it exists on the remote); default `<SOURCE_DIR>` to `src`. Use the resolved values wherever a placeholder appears below.

Before delegating, Read `${CLAUDE_PLUGIN_ROOT}/agents/qa-engineer.md` in full. In Codex, pass
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

**Usage:** `/sdd:qa-explore <feature-or-flow> [--report-only]`

Go play with the running app like a human tester, find bugs and UX friction, and fix the bugs.
Spawn the `qa-engineer` agent for an ad hoc, adversarial session that leaves a regression test
and a fix behind for every bug it confirms.

## Not the same as `/sdd:qa`

| | `/sdd:qa` | `/sdd:qa-explore` |
|---|---|---|
| Scope | One spec task's QA Scenarios | Any feature, flow or command, spec or not |
| Agent | `tester` — sealed verifier: no source access, no writes | `qa-engineer` — reads source and fixes code |
| On a bug | Reports behavioural feedback; the pipeline hands it to `executor` | Failing regression test (red), minimal fix (green), proof the test bites, separate commits |
| Independence | Independent verdict: it cannot see the code it grades | Not independent; the red → green → revert proof stands in for it |
| Use when | Inside `/sdd:ship`, task-scoped | Ad hoc: "go poke at this and find problems" |

## Steps

1. **Parse the invocation.** Everything except `--report-only` is the feature or flow. If it
   is empty, ask what to explore and stop.
2. **Resolve the target.** Read `.claude/sdd/config.json` if present: the dev URL
   (`devServer.url`, default `http://localhost:3000`), `commands.devHost`, `commands.test`, and
   `devServer.credentialEnv`. Collect any credential variable *names* the user gave; never ask
   for or pass credential values.
3. **Optional context.** If the flow clearly maps to a spec domain under `docs/specs/<domain>/`,
   read the QA Scenarios section of its `design.md`. It is context, not a boundary; skip this
   step when no domain is inferable.
4. **Dispatch.** Spawn `qa-engineer` (per the delegation preamble above) in the foreground with
   only: the feature or flow, the resolved dev URL, `--report-only` when given, the credential
   variable names, and the QA Scenarios from step 3 if any. Do not pass this conversation's
   history, diffs or other agents' output.
5. **Relay the report.** Show the agent's final report — BUGS FOUND & FIXED, FRICTION NOTED,
   NOT FIXED (why), CLEAN — as returned, plus the commits it made (`git log --oneline` since
   the start of the session). Do not push or open a pull request; that is the user's call
   (`/sdd:create-pr`).

## What the agent will and will not do

- Reaches the app first. If nothing answers and `commands.devHost` is configured, it starts
  `<DEV_HOST_CMD>` in the background; if it is not configured, it stops and reports what is
  missing rather than standing up infrastructure.
- Probes beyond the happy path: empty, malformed and boundary input; rapid repeats;
  back, refresh and deep links; error states; console errors and failed network requests;
  phone-width layout. CLI and TUI apps are driven through the shell in a scratch directory.
- Treats an issue as a bug only after it reproduces twice.
- For each bug, unless `--report-only`: a failing regression test in the project's existing
  conventions, root cause from source, a minimal fix, the test reverted-against to prove it
  bites, `<TEST_CMD>`, then the test and the fix as two commits.
- Reports UX friction (confusing labels, missing feedback, dead ends) and flaky or out-of-scope
  findings without changing them.
- Reads credentials only from environment variables named by you or by
  `devServer.credentialEnv`; never hard-codes, prints or commits them.

See `${CLAUDE_PLUGIN_ROOT}/agents/qa-engineer.md` for the full contract.
