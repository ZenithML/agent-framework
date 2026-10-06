---
name: branching-model
description: >
  Use when the branch, commit or merge convention for this repository needs stating or resolving
  — GitHub Flow (the default), trunk-based or Gitflow, read from config.json. Reference material for other
  skills. Does not trigger to perform git operations, open a PR, or cut a release.
---

> **Configuration.** This skill uses project-specific commands and branch names. Resolve each placeholder from `.claude/sdd/config.json` at the repo root (keys: `commands.test`→`<TEST_CMD>`, `commands.testOne`→`<TEST_CMD> <test-file>`, `commands.lint`→`<LINT_CMD>`, `commands.build`→`<BUILD_CMD>`, `commands.dev`→`<DEV_CMD>`, `commands.devHost`→`<DEV_HOST_CMD>`, `commands.install`→`<INSTALL_CMD>`, `branching.devBranch`→`<DEV_BRANCH>`, `branching.mainBranch`→`<MAIN_BRANCH>`, `source.dir`→`<SOURCE_DIR>`, `branching.featurePrefix`→ the `feature/` prefix in `<feature-branch>`). If `.claude/sdd/config.json` is absent, auto-detect: read `package.json` scripts (npm/pnpm/yarn) or `pyproject.toml`/`Makefile` (python) for test/lint/build/dev commands; default branches to `main` (and `development` only if it exists on the remote); default `<SOURCE_DIR>` to `src`. Use the resolved values wherever a placeholder appears below.

This skill is the agent-facing procedural for branching. The conventions and rationale live in [${CLAUDE_PLUGIN_ROOT}/standards/branching-model.md](${CLAUDE_PLUGIN_ROOT}/standards/branching-model.md) — read that for branch roles, the comparison to classical Gitflow / GitHub Flow, and commit-message rules.

## When this applies

You are about to:
- Create a feature branch
- Open a pull request
- Investigate or recover a merge

## What to do

### Starting a feature

```bash
git fetch origin
git checkout -b <feature-branch> origin/<DEV_BRANCH>
```

Feature branches are always cut from `<DEV_BRANCH>`, never from `<MAIN_BRANCH>`.

### Before opening a PR

Merge the target (base) branch into your branch and resolve conflicts locally:

```bash
git fetch origin
git merge origin/<base-branch>     # base is usually `<DEV_BRANCH>`
```

Push only after the merge is clean. If you opened the PR before merging the base in, do it now — the goal is a PR diff that reflects your change only, not a mix of your change and conflict resolutions.

### Commit messages

Use Conventional Commits prefixes (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`). Using them consistently keeps the history readable and groupable by change type.

### Hard prohibitions

- **Do not push directly to `<MAIN_BRANCH>` or `<DEV_BRANCH>`.** Both branches are PR-only.
- **Do not merge with `--no-verify`.** If a hook fails, fix the underlying issue.
