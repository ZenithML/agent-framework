---
name: triage-pr
description: >
  Use when a pull request or branch diff is too large to review carefully, or a reviewer asks
  where to look or what can be skipped. Produces an ordered review path: read closely, review
  normally, safe to skip with a reason. Does not trigger to review or comment on code (that is
  /sdd:review-pr), to fix code (that is /sdd:fix-pr), or to approve a pull request.
version: 1.0.0
owner: zenithml
updated: 2026-10-20
source: docs/specs/review-triage/design.md
changelog: |
  1.0.0 — Initial release.
---

> **Configuration.** This skill uses project-specific commands and branch names. Resolve each placeholder from `.claude/sdd/config.json` at the repo root (keys: `commands.test`→`<TEST_CMD>`, `commands.testOne`→`<TEST_CMD> <test-file>`, `commands.lint`→`<LINT_CMD>`, `commands.build`→`<BUILD_CMD>`, `commands.dev`→`<DEV_CMD>`, `commands.devHost`→`<DEV_HOST_CMD>`, `commands.install`→`<INSTALL_CMD>`, `branching.devBranch`→`<DEV_BRANCH>`, `branching.mainBranch`→`<MAIN_BRANCH>`, `source.dir`→`<SOURCE_DIR>`, `branching.featurePrefix`→ the `feature/` prefix in `<feature-branch>`). If `.claude/sdd/config.json` is absent, auto-detect: read `package.json` scripts (npm/pnpm/yarn) or `pyproject.toml`/`Makefile` (python) for test/lint/build/dev commands; default branches to `main` (and `development` only if it exists on the remote); default `<SOURCE_DIR>` to `src`. Use the resolved values wherever a placeholder appears below.

**Usage:** `/sdd:triage-pr [PR-number] [--base REF] [--comment]`

Triage a large diff into an ordered review path for a human reviewer.

## Why

When a diff is too large to read, reviewers skip parts at random and approve anyway, and a
partial review looks the same as a full one. Triage makes the skip visible: every hunk is placed
in a tier, every skip has a stated reason, and the focus items form a checklist whose unticked
entries show what was not reviewed.

## Tiers

- **Read closely** (section 1): hunks that touch sensitive paths, migrations, CI or deploy config, env files, risky constructs (eval, shell execution, disabled verification, suppressed checks), weakened tests, or repo rules. Each is a `- [ ]` checklist item.
- **Review normally** (section 2): nothing fired. This is not a claim that the code is safe.
- **Safe to skip** (section 3): lockfiles, generated or vendored files, pure renames, mode-only changes, empty files, whitespace-only hunks. Each carries its reason.

Optional repo rules live in `.claude/sdd/review-triage.json`. Every key is optional and holds a list of regex strings:

- `focus_paths`: paths whose hunks are always read closely.
- `low_paths`: paths that are safe to skip (a built-in path focus still wins).
- `focus_patterns`: patterns that, when matched on an added line, make the hunk read closely.

## Steps

1. **Get the diff.**
   - Given a PR number N, run `gh pr diff N > "$TMP/pr.diff"`.
   - Given neither a number nor `--base`, find the current branch's PR with `gh pr view --json number --jq .number`. If one exists, run `gh pr diff <number> > "$TMP/pr.diff"`.
   - With no PR (or when `--base` is given), run `git diff <base>...HEAD > "$TMP/pr.diff"`, where `<base>` is `--base` or `<MAIN_BRANCH>`.
   - If `--comment` is set and there is no PR, refuse and say why: a comment needs a PR to live on. Do not continue to post; you may still print the triage if the user wants it.
2. **Rules.** If `.claude/sdd/review-triage.json` exists, pass `--rules .claude/sdd/review-triage.json` to the script.
3. **Find the previous comment (only with `--comment`).**
   - Get the current user: `gh api user --jq .login`.
   - List the PR's comments: `gh api repos/{owner}/{repo}/issues/N/comments --paginate`.
   - Pick the most recent comment whose author login is that user and whose body starts with `<!-- sdd:triage-pr -->`. Remember its `id`.
   - If found, write its body to a temp file and pass it with `--previous FILE`, so ticks carry over.
4. **Run the script.**
   `python3 ${CLAUDE_PLUGIN_ROOT}/skills/triage-pr/scripts/triage.py --diff "$TMP/pr.diff" [--rules ...] [--previous FILE]`
   If it exits 2, show its message and stop.
5. **Read the focus hunks.**
   - Read every focus hunk in the diff. Under each `- [ ]` item write a line `  check: <one concrete question the human should answer>`. The question must come from actually reading that hunk, not from the reason text.
   - While reading the review-normally files, a hunk may carry a risk the rules do not cover, for example a changed authorisation check in a file with a neutral name. For each such hunk, re-run the script adding `--promote FILE:LINE=<reason>` (repeatable; LINE is the hunk's new start line), then redo the check lines for the new output.
   - Never edit tiers, counts or reasons by hand. There is no demote option, and you must not move a line out of section 1.
6. **Output.**
   - With `--comment`, write the final markdown (with check lines) to a file and post it. If a comment was found in step 3, update it: `gh api -X PATCH repos/{owner}/{repo}/issues/comments/{id} -F body=@FILE`. Otherwise create one: `gh api -X POST repos/{owner}/{repo}/issues/N/comments -F body=@FILE`. Then print the comment URL (`html_url` from the response).
   - Without `--comment`, print the triage markdown.
   - Do not approve, request changes, or edit code.

## Rules

- Never demote or hand-edit tiers. Promote only, through `--promote`. If asked to mark focus hunks safe, refuse and explain that an unticked item means unreviewed.
- Never approve, request changes, or edit code. For review comments use `/sdd:review-pr`; for fixes use `/sdd:fix-pr`.
- `--comment` is refused when there is no PR.
- Every `check:` line is a concrete question from actually reading the hunk.

## Files in this skill

- `SKILL.md` (this file)
- `scripts/triage.py` — deterministic diff tiering (standard library only)
- `evaluations/baseline-evals.json` — baseline scenarios
