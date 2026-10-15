---
name: create-pr
description: >
  Use when the current branch is ready to push and a pull request should be opened from it, with
  a description supplied or drafted. Does not trigger to review a PR (that is /sdd:review-pr),
  to act on review feedback (that is /sdd:fix-pr), or to merge one.
---

> **Configuration.** This skill uses project-specific commands and branch names. Resolve each placeholder from `.claude/sdd/config.json` at the repo root (keys: `commands.test`→`<TEST_CMD>`, `commands.testOne`→`<TEST_CMD> <test-file>`, `commands.lint`→`<LINT_CMD>`, `commands.build`→`<BUILD_CMD>`, `commands.dev`→`<DEV_CMD>`, `commands.devHost`→`<DEV_HOST_CMD>`, `commands.install`→`<INSTALL_CMD>`, `branching.devBranch`→`<DEV_BRANCH>`, `branching.mainBranch`→`<MAIN_BRANCH>`, `source.dir`→`<SOURCE_DIR>`, `branching.featurePrefix`→ the `feature/` prefix in `<feature-branch>`). If `.claude/sdd/config.json` is absent, auto-detect: read `package.json` scripts (npm/pnpm/yarn) or `pyproject.toml`/`Makefile` (python) for test/lint/build/dev commands; default branches to `main` (and `development` only if it exists on the remote); default `<SOURCE_DIR>` to `src`. Use the resolved values wherever a placeholder appears below.

**Usage:** `/sdd:create-pr [title]` — title is optional and inferred from the branch name if omitted.

Create a pull request for the current branch.

## Step 1: Verify state

1. Run `git status` — abort if there are uncommitted changes
2. Identify current branch name
3. Determine the **base branch** from branch prefix:
   | Branch prefix    | Base branch     |
   |------------------|-----------------|
   | `feature/`       | `<DEV_BRANCH>`  |
   | `hotfix/`        | `<MAIN_BRANCH>` |
   | `release/`       | `<MAIN_BRANCH>` |
   | anything else    | `<DEV_BRANCH>`  |

## Step 2: Push

```bash
git push -u origin <current-branch>
```

## Step 3: Infer title (if not provided)

Convert the branch name to a human-readable title:
- Strip the prefix (`feature/`, `hotfix/`)
- Replace hyphens with spaces
- Capitalise the first word

Example: `feature/add-cart-total` → `Add cart total`

## Step 4: Build PR body

If a description was supplied, use it as the content and fit it to the structure below.

**Choose the structure.** Look for a pull request template in the repository, first match wins:

1. `.github/pull_request_template.md`
2. `.github/PULL_REQUEST_TEMPLATE.md`
3. `docs/pull_request_template.md`
4. `pull_request_template.md` at the repo root

If one exists, its headings are the PR body's headings, in its order, and its comments say what goes in each. If none exists, use this default:

```markdown
## Summary

<One or two sentences a reviewer can read on their own: what changes and why.>

**Before:** <what a user or developer sees today>

**After:** <what they see once this merges; screenshots go here for UI changes>

## Changes

### <Area> (<task ids, e.g. T1–T3, when there is a spec>)

- <change>

## Not in this PR

- <deferred work and where it goes next>

## Testing

- [x] Unit tests: <command> — <result>
- [x] Lint / typecheck: <command> — <result>
- [ ] Build: <not run — reason>
- [ ] Manual / QA: <scenarios run, or why not>

## Review notes

<Where to start reading, the risky parts, anything you are unsure about.>

## Deploy notes

<Migrations, env or config changes, breaking changes, rollout order.>

## Related

- Closes #N
- Spec: `docs/specs/<domain>/`
- <PRs this builds on or overlaps with, and how to resolve the overlap>
```

Rules for filling it, whichever source the sections came from:

- Keep the sections in the template's order. Delete the guidance comments (`<!-- … -->`) once a section is filled.
- Leave out an optional section that has nothing to say (in the default: Changes on a small PR, Not in this PR, Deploy notes) instead of writing "None".
- Each Testing line names what was run and the result. A box stays unchecked only with a reason.
- Put `Closes #N` for every linked issue in Related, never in a section of its own.
- The PR body may start with lines the platform or tool adds (an attribution line, for example). Keep them where they are and put the sections below them.

## Step 5: Create or update PR

Check which GitHub tool is available and use the first that works:

1. **GitHub MCP** — use the `create_pull_request` MCP tool if available
2. **gh CLI** — fall back to:
   ```bash
   gh pr create \
     --base <base-branch> \
     --title "<title>" \
     --body "<body>"
   ```
   > **Local Claude Code only**: if `gh` fails with auth errors, prepend `unset GH_TOKEN GITHUB_TOKEN;` — this clears a stale env var that may override keyring credentials. Do **not** do this in GitHub Actions or Copilot cloud agents where `GITHUB_TOKEN` is the valid runtime token.

## Step 6: Screenshots (UI-changing PRs only)

**If the PR includes UI changes, you must complete this step before marking the PR ready. Do not skip it.**

Attempt to capture before and after screenshots of the running app and embed them in the PR body.

### Claude Code — local

1. Start the app (`<DEV_CMD>`) if the dev server (`devServer.url` in `.claude/sdd/config.json`, default `http://localhost:3000`) is not already reachable.
2. Use Playwright MCP browser tools to capture before and after screenshots from the running app.
3. Upload images manually through the GitHub web UI in a normal human/browser session to get `https://github.com/user-attachments/assets/...` URLs and embed them in the PR body.
   Do **not** use Playwright MCP or any other automation to navigate to `github.com` for the upload step.

### Claude Code — cloud agent

Screenshot upload is not automatable (no browser session cookies for the GitHub upload endpoint). Add the placeholder below and request manual reviewer attachment:

> ⚠️ Some required screenshots are still missing. Please attach the missing before and/or after screenshot(s) via the GitHub web UI before merging.

If neither screenshots nor a placeholder are present, add the placeholder now, then mark ready.

## Step 7: Finalize the PR before stopping

Do not end the session with a WIP or draft PR.

Before you stop:

1. Ensure the PR body is complete and real — every section of the structure chosen in Step 4 filled or deliberately left out, and `Closes #N` in Related when applicable
2. If the PR was created or left as draft, mark it ready for review after the screenshot requirement above is satisfied
3. Remove any generic firewall/environment warning dump from the PR body and replace it with the project-specific screenshot state
4. Confirm the branch is pushed and the PR reflects the final description, not a placeholder TODO body

## Rules

- Never push to `<MAIN_BRANCH>` or `<DEV_BRANCH>` directly.
- If neither MCP nor `gh` is available, instruct the user to install `gh` or enable the GitHub MCP server.
- **Never commit screenshot files to any git branch** (feature, hotfix, or otherwise).
- **Never create a GitHub Release (draft, pre-release, or otherwise) to host PR screenshots.** Releases are reserved for versioned software artifacts.
- Do not leave a PR in draft or WIP state at session end.
