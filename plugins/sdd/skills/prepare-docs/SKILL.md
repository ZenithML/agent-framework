---
name: prepare-docs
description: >
  Use when a domain's documentation needs sealing before a pull request — verify tasks.md,
  refresh INDEX status, audit conformance, and land a checkpoint commit. Does not trigger as a
  standalone doc audit with no PR pending (that is /sdd:audit), and does not open the PR itself.
---

> **Configuration.** This skill uses project-specific commands and branch names. Resolve each placeholder from `.claude/sdd/config.json` at the repo root (keys: `commands.test`→`<TEST_CMD>`, `commands.testOne`→`<TEST_CMD> <test-file>`, `commands.lint`→`<LINT_CMD>`, `commands.build`→`<BUILD_CMD>`, `commands.dev`→`<DEV_CMD>`, `commands.devHost`→`<DEV_HOST_CMD>`, `commands.install`→`<INSTALL_CMD>`, `branching.devBranch`→`<DEV_BRANCH>`, `branching.mainBranch`→`<MAIN_BRANCH>`, `source.dir`→`<SOURCE_DIR>`, `branching.featurePrefix`→ the `feature/` prefix in `<feature-branch>`). If `.claude/sdd/config.json` is absent, auto-detect: read `package.json` scripts (npm/pnpm/yarn) or `pyproject.toml`/`Makefile` (python) for test/lint/build/dev commands; default branches to `main` (and `development` only if it exists on the remote); default `<SOURCE_DIR>` to `src`. Use the resolved values wherever a placeholder appears below.

**Usage:** `/sdd:prepare-docs <domain>`

Brings documentation to a verified, committed state on the feature branch so the PR captures the final docs snapshot. Run this after all implementation tasks are done, before `/create-pr`.

> Called automatically by `/publish` as its first step. Run manually when working outside the pipeline.

> **Note on status semantics:** Marking tasks `[x]` and INDEX status `Implemented` here represents the anticipated state once the PR is merged. These are forward-looking markers on the feature branch — they do not mean the feature is live.

---

## Steps

### 1. Check tasks.md

Open `docs/specs/<domain>/tasks.md` and verify task completion:
- All implementation tasks should be checked `[x]`
- If any are still `[ ]`, stop and surface them to the user — do not auto-check tasks that were not actually completed

### 2. Update INDEX.md status

In `docs/INDEX.md`, find the row for `<domain>` and set Status to `Implemented`.

### 3. Run `/audit <domain>` and fix issues

- Template sections missing → add them
- Unresolved TBD rows in design.md → flag to user (do not silently resolve)
- Do not proceed to commit if blocking issues remain

### 4. Commit as docs checkpoint

Commit all changed docs files to the current feature branch:

```
chore(docs): prepare <domain> docs
```

Only commit docs files (`tasks.md`, `INDEX.md`, and any spec fixes from the audit). Do not touch source code.

### 5. Verify issue links (if applicable)

If tasks.md contains issue references (`#N`), confirm every completed `[x]` task with a linked issue will be auto-closed by the PR. Flag any gaps for the user to add `Closes #N` in the PR description (handled by `/publish`).

If no issues are linked — e.g., triggered as a periodic doc audit or the domain was implemented without GitHub issues — skip this step silently.

---

## Rules

- Run on the feature branch, not on `<DEV_BRANCH>` directly
- If tasks are already all `[x]`, step 1 is a no-op (idempotent)
- If INDEX.md already shows `Implemented`, step 2 is a no-op (idempotent)
- Do not close issues manually — `Closes #N` in the PR description handles this on merge
