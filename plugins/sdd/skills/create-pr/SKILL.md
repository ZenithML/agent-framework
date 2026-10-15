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

**Read the full commit history first**: `git log <base-branch>..<current-branch> --oneline`. The title describes what the branch as a whole does, not just the branch-name slug and not just the first or latest commit. If the branch's scope has drifted from its name (common on a long-running branch), the title follows the real scope.

Write the title in **Conventional Commits** form, `type(scope): description`, with the scope optional. Pick the type from the change, using the branch prefix as a hint:

| Branch prefix | Type |
|---|---|
| `feature/`, `feat/` | `feat` |
| `fix/`, `bugfix/`, `hotfix/` | `fix` |
| `docs/` | `docs` |
| `chore/` | `chore` |
| `refactor/` | `refactor` |
| `test/` | `test` |
| anything else | whichever of the above fits the change |

Write the description in lowercase, for a reader of the release notes rather than as a restated branch name.

Examples:
- `feature/add-cart-total` → `feat: add cart total`
- `fix/login-redirect-loop` → `fix(auth): stop the login redirect loop`

## Step 4: Build PR body

Read every commit on the branch (`git log <base-branch>..<current-branch>`), not just the latest one: the body covers everything the PR contains. If a description was supplied, use it as the content and fit it to the structure below.

**Choose the structure.** The repo's description template is one file, found in this order (first match wins):

1. The path in `pullRequest.template` in `.claude/sdd/config.json`, relative to the repo root. This works on any code host.
2. If that key is absent, the first of these that exists: `.github/pull_request_template.md`, `.github/PULL_REQUEST_TEMPLATE.md` (GitHub), `.gitlab/merge_request_templates/Default.md` (GitLab), `docs/pull_request_template.md`, `pull_request_template.md`.

If a template is found, its headings are the description's headings, in its order, and its comments say what goes in each. If none is found, use this default:

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

- [ ] Unit tests: <command> — <result>
- [ ] Lint / typecheck: <command> — <result>
- [ ] Build: <not run — reason>
- [ ] Manual / QA: <scenarios run, or why not>

## Review notes

<Where to start reading, the risky parts, anything you are unsure about.>

## Deploy notes

<Migrations, env or config changes, breaking changes, rollout order.>

## Related

- Closes #N
- Spec: <spec path, if there is one>
- <PRs this builds on or overlaps with, and how to resolve the overlap>
```

Rules for filling it, whichever source the sections came from:

- Keep the sections in the template's order. Delete the guidance comments (`<!-- … -->`) once a section is filled.
- Leave out an optional section that has nothing to say (in the default: Changes on a small PR, Not in this PR, Deploy notes) instead of writing "None".
- Each Testing line names what was run and the result. Tick a box only once that check has actually passed; a box stays unchecked only with a reason.
- Put `Closes #N` for every linked issue in Related, never in a section of its own.
- The description may start with lines the platform or tool adds (an attribution line, for example). Keep them where they are and put the sections below them.

## Step 5: Create or update PR

**First, check whether a PR already exists for this branch**: `gh pr view <branch> --json number,title,body`, the MCP `list_pull_requests` tool filtered by `head`, or `glab mr view <branch>` on GitLab. Someone may have opened one from the "Create PR" link that a push prints. If one exists, don't leave the title and body the host auto-filled (usually the first commit's subject): treat this run as an **update** and apply the title and body from Steps 3–4 to the existing PR.

Check which tool for the repo's code host is available and use the first that works:

1. **GitHub MCP** — `create_pull_request` (new) or `update_pull_request` (existing)
2. **gh CLI**:
   ```bash
   # New PR:
   gh pr create --base <base-branch> --title "<title>" --body "<body>"
   # Existing PR:
   gh pr edit <number> --title "<title>" --body "<body>"
   ```
   > **Local Claude Code only**: if `gh` fails with auth errors, prepend `unset GH_TOKEN GITHUB_TOKEN;` — this clears a stale env var that may override keyring credentials. Do **not** do this in GitHub Actions or Copilot cloud agents where `GITHUB_TOKEN` is the valid runtime token.
3. **glab CLI** — when `origin` is a GitLab remote, use a merge request:
   ```bash
   # New MR:
   glab mr create --target-branch <base-branch> --title "<title>" --description "<body>"
   # Existing MR:
   glab mr update <number> --title "<title>" --description "<body>"
   ```

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

## Step 8: Watch CI and review feedback

Skip this step when the publisher called this skill: the publisher watches CI itself. Skip it too when the user asked not to wait (for example `--no-wait`); then report the initial check status and stop.

Otherwise, stay with the PR until its checks are green and its feedback is answered:

1. **Watch the checks** until every one completes: `gh pr checks <number> --watch` on GitHub, `glab ci status --live` on GitLab. Don't stop while checks are pending.
2. **Allow time for review bots.** Automated reviewers (Copilot, Gemini, linters, deploy previews) usually post within a couple of minutes of the PR opening or checks finishing. Read the PR's review comments and reviews once more after that window (`gh api repos/:owner/:repo/pulls/<number>/comments`, `.../reviews`; `glab mr view <number> --comments` on GitLab).
3. **Act on failures and comments.** If a check failed or a review or comment is unanswered, run `/sdd:fix-pr <number>`: it resolves conflicts, fixes code or tests, replies in each thread and pushes. Then watch the checks again.
4. **Finish** when every check is green, every review thread and comment has its own reply, and the description matches what the PR now contains.

## Rules

- Never push to `<MAIN_BRANCH>` or `<DEV_BRANCH>` directly.
- If no tool for the repo's code host is available, instruct the user to install `gh` (GitHub) or `glab` (GitLab), or enable the GitHub MCP server.
- **Never commit screenshot files to any git branch** (feature, hotfix, or otherwise).
- **Never create a GitHub Release (draft, pre-release, or otherwise) to host PR screenshots.** Releases are reserved for versioned software artifacts.
- Do not leave a PR in draft or WIP state at session end.
- Unless Step 8 says to skip it, do not stop while checks are pending or review bots have not had time to post.
