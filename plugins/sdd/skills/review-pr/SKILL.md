---
name: review-pr
description: >
  Use when a pull request needs assessment and inline feedback left as comments, including when
  an agent is tagged on the PR to review it. Does not trigger to make code changes, push to the
  branch, edit the PR title or description, or open a new PR — if asked to implement, hand off
  to /sdd:fix-pr.
---

**Usage:** `/sdd:review-pr` — review the current pull request

Review and provide feedback on a pull request. To *act on* existing feedback (fix issues, reply to comments, resolve merge conflicts, sync the PR description), use `/fix-pr` instead.

For a PR too large to read fully, run `/sdd:triage-pr` first to get an ordered review path (read closely, review normally, safe to skip).

## Default Behavior

When tagged in a pull request (e.g. @claude[agent], @copilot) to review or provide feedback:

- **Default to leaving inline code suggestions and comments only.** Do not make changes to the PR.
- **Do NOT open new pull requests** when tagged for review - only provide feedback as comments.
- Post code suggestions as review comments (using GitHub suggestion blocks where appropriate) so the author can accept or reject them individually.
- Do **not** push code, update the branch, or modify the PR title/description.

## Proof of bug and severity budget

- A comment that flags a bug or a blocking issue must include a minimal failing reproduction:
  a test snippet, or an executable `curl` / CLI command, with the observed wrong result. No
  theoretical what-if conjectures; if you cannot reproduce it, it is not a blocker.
- Only reproducible High/P0 defects block approval. Request changes only for those.
- Everything else (unreproducible concerns, style, design taste, extra tests) is a suggestion,
  marked `Optional follow-up:` and never blocking.
- Converge in two passes. On a re-review after fixes, check only whether the earlier
  reproductions now pass and whether the fix caused a proven regression; do not raise new
  speculative blockers. Approve when the reproducible highs are fixed.

## When Explicitly Asked to Implement

If explicitly asked to implement fixes or apply suggestions during a review, **refuse** to make code changes directly using this skill. Instead, instruct the user to run `/fix-pr` to safely manage the resolution process.

## Rules

- Never push code or open PRs when tagged for review
- Only provide feedback as comments
- Blocking comments need a failing reproduction; only reproducible High/P0 defects block
- Mark non-blocking suggestions `Optional follow-up:`
- Use GitHub suggestion blocks for code suggestions
- Let the author accept or reject suggestions individually
- If asked to implement, refer the user to `/fix-pr`
