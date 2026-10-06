---
name: test
description: >
  Use when the project's existing test suite should simply be run and its results reported, with
  no implementation or QA reasoning attached. Does not trigger for behavioural QA against design
  scenarios (that is /sdd:qa), and does not trigger to write new tests (that is /sdd:implement).
---

> **Configuration.** This skill uses project-specific commands and branch names. Resolve each placeholder from `.claude/sdd/config.json` at the repo root (keys: `commands.test`→`<TEST_CMD>`, `commands.testOne`→`<TEST_CMD> <test-file>`, `commands.lint`→`<LINT_CMD>`, `commands.build`→`<BUILD_CMD>`, `commands.dev`→`<DEV_CMD>`, `commands.devHost`→`<DEV_HOST_CMD>`, `commands.install`→`<INSTALL_CMD>`, `branching.devBranch`→`<DEV_BRANCH>`, `branching.mainBranch`→`<MAIN_BRANCH>`, `source.dir`→`<SOURCE_DIR>`, `branching.featurePrefix`→ the `feature/` prefix in `<feature-branch>`). If `.claude/sdd/config.json` is absent, auto-detect: read `package.json` scripts (npm/pnpm/yarn) or `pyproject.toml`/`Makefile` (python) for test/lint/build/dev commands; default branches to `main` (and `development` only if it exists on the remote); default `<SOURCE_DIR>` to `src`. Use the resolved values wherever a placeholder appears below.

**Usage:** `/sdd:test`

Run the test suite:

1. Check if test infrastructure exists (the project's test config file, and a configured test command)
   - If missing: report that tests are not configured, list the expected files/scripts (the project's test config file, and a runnable test command), and stop — do not proceed to run tests
2. Run `<TEST_CMD>`
3. Report results:
   - Number of tests passed/failed
   - Show any failures with details
   - Suggest fixes if tests are failing

If all tests pass, confirm with a summary.
