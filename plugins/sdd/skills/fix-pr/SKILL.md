---
name: fix-pr
description: >
  Use when an existing pull request needs to become mergeable — resolve conflicts, address open
  review comments, and bring the description back in line with what changed. Does not trigger to
  give a first review (that is /sdd:review-pr), to open a PR (that is /sdd:create-pr), or to
  merge.
---

**Usage:** `/sdd:fix-pr` or `/sdd:fix-pr <PR-number>`

**Also triggered by** PR readiness questions: "is this PR ready to merge?", "can we merge this?", "is the PR good to go?", "what's left before merging?", or any similar question about whether a PR is ready. Run the full skill — don't just answer the question.

Bring the current (or specified) pull request to a mergeable state. This covers two independent concerns:

1. **Merge conflicts** — detected by GitHub's merge status or visible conflict markers; resolved by merging the target branch
2. **Open comments** — issue comments, inline review comments, and formal reviews from any author (human, Copilot, or bots)

Run both checks every time. Either or both may need work.

**Scope:** This skill acts on existing issues on any PR — it resolves conflicts, makes fixes, and replies to feedback. It is distinct from `/review-pr`, which reviews code changes and leaves feedback but never commits code.

---

## Step 1: Check merge status

```bash
gh pr view <number> --json mergeable,mergeStateStatus,headRefName,baseRefName
```

| `mergeable` value | Action |
|---|---|
| `MERGEABLE` | No conflict work needed — proceed to Step 2 |
| `CONFLICTING` | Resolve conflicts (see below) |
| `UNKNOWN` | Wait a moment, re-check; treat as `CONFLICTING` if it persists |

### Resolving conflicts

1. **Fetch and merge the target branch** into the PR branch:
   ```bash
   git fetch origin
   git merge origin/<base-branch>
   ```
2. **Identify conflicted files**: `git diff --name-only --diff-filter=U`
3. **Resolve each conflict** — read both sides, understand the intent, keep what's correct. Do not blindly accept either side.
4. Stage resolved files and commit:
   ```bash
   git add <resolved-files>
   git commit -m "chore: resolve merge conflicts with <base-branch>"
   ```
5. Push: `git push origin <head-branch>`

If the conflict is complex (interleaved logic changes on both sides), read the relevant files in full before deciding.

---

## Step 2: Fetch all comment types

Retrieve all three comment surfaces — missing any one means leaving feedback unaddressed:

- **Issue comments** — general PR-level discussion (`gh api repos/:owner/:repo/issues/:number/comments`)
- **Review comments** — inline comments on specific lines (`gh api repos/:owner/:repo/pulls/:number/comments`)
- **Reviews** — formal review submissions with summary body (`gh api repos/:owner/:repo/pulls/:number/reviews`)

---

## Step 2: Understand context

Before taking any action, proactively read the relevant code to understand the context of the comments. You can read the code locally and use tools like `read_file` or `grep_search` to verify surrounding logic, ensuring your response or fix aligns with the codebase. Keep the scope manageable.

---

## Step 3: Triage each comment

For every comment, determine:

| Type | Signal | Action |
|---|---|---|
| Question / explanation request | "why", "can you explain", "help me understand" | Reply only — no code changes |
| Suggestion / code change | "consider", "you could", diff block | Evaluate critically (see Step 4), then reply |
| Bug report / correctness issue | "this is wrong", "will break", "doesn't match" | Investigate, fix if valid, reply with outcome |
| Outdated comment | Thread marked outdated, file deleted/moved | Reply acknowledging the change, no action needed |

**Skip** a comment only if it already has a substantive reply that fully addresses the point — regardless of which session posted it.

---

## Step 4: Evaluate suggestions critically

Do not apply suggestions blindly. For each suggestion, ask:

1. **Is it correct?** Does it fix a real problem, or is it based on a misunderstanding?
2. **Is it consistent with the design?** Does it align with decisions already made in this PR or the project specs?
3. **Does it improve things?** Is the change an objective improvement, or a style preference?

**Apply** the suggestion if it fixes a genuine issue. Reference the fix in the reply.

**Push back** if the suggestion is based on a misunderstanding, conflicts with an intentional design decision, or would introduce a worse trade-off. Explain the rationale clearly:

> "The `Read` tool was intentionally included so the agent can read design.md — removing it would require the architect to inline all spec content into every prompt. The concern about source inspection is addressed by the instruction constraint instead."

Pushing back is not rejection — it's a response. The author can follow up.

---

## Step 5: Make fixes

For comments that require code changes:

1. Make the fix
2. Commit with a clear message referencing what was fixed
3. Push to the branch

Batch all fixes into as few commits as is sensible. Complete all fixes before replying, so replies can reference commit SHAs.

---

## Step 6: Reply individually

Reply to each comment at the **comment level**, not as a single PR-level summary. Use the correct endpoint for each comment type:

**Inline review comments** (from Step 2 "Review comments") — reply in-thread under the original:
```bash
gh api repos/:owner/:repo/pulls/:pull_number/comments/:comment_id/replies \
  --method POST --field body="..."
```

**Issue comments** (from Step 2 "Issue comments") — reply by posting a new comment:
```bash
gh api repos/:owner/:repo/issues/:pull_number/comments \
  --method POST --field body="..."
```

Do not post a single PR-level summary in place of individual replies.

Each reply should:
- State whether you applied a fix, pushed back, or just answered
- Reference the commit SHA if a fix was made (e.g. "Fixed in `abc1234`")
- Be concise — one to three short paragraphs at most
- Not repeat the original comment back verbatim

---

## Step 7: Sync the PR description

The PR description is the **permanent release record**. After all work is done and commits are pushed, audit the description against the full commit list and update it to reflect what is actually in the PR — not just the original intent.

### Audit before finishing

Read every commit in the PR (not just the latest) and ask:

1. Is every material change represented in the description?
2. Does any section say `_None_`, `TBD`, or stay empty even though commits address that category?
3. Did fixes applied during review introduce content that belongs in a "Fixed" section?

The original author wrote the description before review began. Bugs found and fixed during review, harness corrections, doc fixes — these are real changes that belong in the description even if they were not planned upfront.

### When to update

**Update** if any commit in the PR introduced something the description does not reflect:
- A real bug was found and fixed during review → add to "Fixed"
- A section has `_None_` or a placeholder but the PR actually contains that type of change → fill it in
- A file, component, or approach that was added, removed, or changed is not mentioned → add it
- A checklist item in the test plan was completed → tick it off

**Do not update** if:
- A section is genuinely empty (e.g. "Fixed: None" and no bugs were actually fixed)
- A commit is a trivially cosmetic edit (whitespace, typo in a comment) with no user-visible effect
- The description is accurate and complete as-is

### How to update

- **Minimum diff** — edit only the lines that are wrong or missing; do not reformat or restructure
- **Preserve the existing format** — headings, bullet style, table layout stay as-is
- **Exception**: if the description was poorly written (no structure, inaccurate title) or the user explicitly requests a different structure, a fuller rewrite is appropriate

### Title

Update the PR title only if the current title no longer reflects the primary purpose of the PR. Apply the same minimum-change principle.

> Note: The general rule in `copilot-instructions.md` — "never modify PR title or description unless explicitly asked" — applies to reactive behavior when triggered by a comment. This step is an *explicit* part of the skill's contract and is not in conflict with that rule.

---

## Rules

- Always check merge status first — a conflicted PR needs that fixed before comments can be meaningfully addressed
- Resolve conflicts by understanding both sides, not by blindly accepting one
- Address every open comment — no silent skips
- Reply individually, never with a single catch-all summary
- Evaluate suggestions; push back when warranted
- Fixes go in their own commit before the reply is posted
- Outdated comments still get a reply acknowledging the change
- PR description is the release record: audit against the full commit list at the end — fill `_None_` placeholders, surface fixes made during review, remove anything no longer true
- Distinct from `/review-pr`: that skill reviews code and leaves feedback but never commits; this skill acts on existing comments and may commit fixes
