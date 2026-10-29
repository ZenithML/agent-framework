# Exploratory QA — Design

**Status:** Approved
**Last Updated:** 2026-10-28

Source: [requirements.md](requirements.md).

## Decision

**Ship exploratory QA as one dispatcher skill and one new role.** `/sdd:qa-explore` resolves
inputs and dispatches; `qa-engineer` carries the whole contract, because that is where its
`tools:` are declared (the dispatch pattern in harness.md).

### Alternatives considered

- *Extend `tester`.* Rejected: the tester's value is that it is sealed. Giving it `Read` and
  `Edit` would void the verifier contract the pipeline depends on.
- *Reuse `executor`.* Rejected: the executor implements one planned task from tasks.md; it has
  no browser tools and no mandate to explore.

## Architecture

### Component Design

| Component | Path | Responsibility |
|---|---|---|
| Skill | `plugins/sdd/skills/qa-explore/SKILL.md` | Parse `<feature-or-flow> [--report-only]`, resolve config, optional QA Scenarios, delegation preamble, dispatch `qa-engineer` |
| Evals | `plugins/sdd/skills/qa-explore/evaluations/baseline-evals.json` | Happy path, the no-dev-server gate, and the signature failure (fixing friction or an unconfirmed glitch) |
| Role | `plugins/sdd/agents/qa-engineer.md` | `role: author`, `tier: workhorse`, `model: sonnet`; tools `Read, Write, Edit, Bash, Grep, Glob` plus Playwright MCP browser tools |
| Config | `plugins/sdd/config/config.schema.json` | Optional `devServer.credentialEnv`: an object mapping a credential field to the *name* of an environment variable |
| Gate config | `scripts/checks/harness-config.json` | Add `qa-explore` to `strict_skills` and `evals_required` |

### Role contract

`qa-engineer` declares `Read` and `Write`, so it satisfies the `author` contract in
`scripts/checks/agent_roles.json`. It is not a verifier and makes no independence claim: it
reads the code it fixes. Its proof of correctness is the red/green/stash-revert sequence, not
isolation. No new role contract is needed.

### Resolution

- Dev URL: `devServer.url`, default `http://localhost:3000` (same snippet as tester.md).
- Commands: `<TEST_CMD>`, `<DEV_HOST_CMD>` and the rest from `.claude/sdd/config.json`, with the
  same auto-detect fallback as tester.md.
- App kind: web when the flow is a URL or the project has a dev server; CLI/TUI otherwise, driven
  through Bash.
- Credentials: env var names from the invocation or `devServer.credentialEnv`; values read from
  the environment at use time, never echoed, never written to tests (tests read the same env
  vars).

### Agent steps

1. Resolve config and mode (`--report-only`).
2. Reach the app: probe the URL; if down and `commands.devHost` is set, start it with
   `run_in_background`, then wait; if down and unset, stop and report.
3. Explore adversarially (list in requirements Story 1).
4. Reproduce each suspect a second time; classify as bug, friction, or not-fixed.
5. Per bug (skipped in report-only): red test → root cause → minimal fix → green → stash-revert
   proof → `<TEST_CMD>` → two commits.
6. Final report with the four sections.

## Test Scenarios

Python `unittest` in `tests/`, no provider calls:

| # | Scenario | Asserts |
|---|---|---|
| T1 | `test_agent_tiers.py` role inventory | `qa-engineer` is `workhorse`, legacy `model` matches the catalog |
| T2 | `test_agent_tiers.py` dispatchers | `qa-explore` carries the full model-resolution preamble |
| T3 | `test_agent_tiers.py` qa-engineer contract | `role: author`; tools include Read/Grep/Glob/Edit/Write/Bash and `mcp__playwright__browser_navigate`; body names `devServer.url`, `<DEV_HOST_CMD>`, `run_in_background`, `--report-only`, the stash-revert proof and all four report sections; no hard-coded credential fallback |
| T4 | `test_agent_tiers.py` skill boundary | `qa-explore` description says Does not trigger and names `/sdd:qa`; `qa` description names `/sdd:qa-explore` |
| T5 | `test_shared_runtime.py` flat install | `.agents/skills/qa-explore/SKILL.md` references `.claude/agents/qa-engineer.md` and reads it in full |
| T6 | `./scripts/check-all.sh` | All gates pass with `qa-explore` in `strict_skills` and `evals_required` |

## QA Scenarios

The "running application" for this repository is its gates and its installer.

| # | Scenario | Pass when |
|---|---|---|
| Q1 | Install into a fresh temp git repo with `scripts/install-skills.sh --harness claude,codex` | `.claude/skills/qa-explore/SKILL.md` and `.claude/agents/qa-engineer.md` exist; `/sdd:` is rewritten to `/` in the installed skill; `.agents/skills/qa-explore` resolves |
| Q2 | `./tests/install-paths.sh` | Passes |
| Q3 | `./scripts/check-all.sh` and `./tests/run-fixtures.sh` | All gates pass; every fixture still fires |
| Q4 | Remove `Read` from a copy of `qa-engineer.md` in a temp root and run `agent_tool_seal` | The gate fails on the author contract |
| Q5 | Read the installed skill | Usage line, `--report-only`, and the `/qa` comparison are present |
