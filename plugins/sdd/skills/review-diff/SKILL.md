---
name: review-diff
description: >
  Use when the local change on a branch (commits, uncommitted edits and new files against the
  default branch) needs a code review before anyone else sees it, with findings anchored to
  file and line and written to .review/findings.json for a person or tool to read. Does not
  trigger to review a pull request on the code host (that is /sdd:review-pr), to judge SDD
  artifacts (that is /sdd:critique), or to fix what it finds.
---

**Usage:** `/sdd:review-diff [--base <ref>]`

A read-only review of the change in the current worktree, written for the owner of the change to
read before the change goes public. It works the same for any agent that can run `git` and write
one file: nothing in it depends on a particular provider or code host.

**Read-only by contract.** Never edit, stage, commit, push or post anything. The only file this
skill writes is `.review/findings.json` (and `.review/.gitignore`).

## Step 1: Find the change

1. Base ref: `--base` if given; otherwise `origin/<default>` where `<default>` comes from
   `git symbolic-ref --short refs/remotes/origin/HEAD`, then `origin/main`, `origin/master`,
   `main`, `master`, the first that exists. Do not fetch.
2. `base=$(git merge-base HEAD <base ref>)`, `head=$(git rev-parse HEAD)`.
3. The change is `git diff <base>` (committed and uncommitted edits to tracked files) plus every
   file from `git ls-files --others --exclude-standard` (new files). Read new files whole.
4. Read the intent if it is there: the task or spec the change implements (an SDD
   `requirements.md` / `design.md` the commits touch, the PR description, or the brief you were
   given). A finding may be that the change does not do what was asked.

## Step 2: Review

Read every changed hunk with enough surrounding code to judge it (the whole function, its
callers when a signature or contract changed). Look for, in this order:

1. **Correctness**: wrong results, unhandled cases the code can actually reach, broken callers,
   races, resource leaks.
2. **Security and data**: secrets or tokens logged or committed, injection, missing auth checks,
   destructive operations without a guard, data loss.
3. **Scope**: the change does something it was not asked to, or misses part of what it was asked.
4. **Tests**: behavior changed with no test that would fail without the change.
5. **Maintainability**, only when it will cause a bug: duplicated logic that must stay in sync,
   misleading names on public interfaces.

Do not report style, formatting, naming taste, or anything a linter in the repository enforces.

## Step 3: Verify each finding

Before writing a finding, trace a concrete path from a real caller or input to the failure, in
the code as it is. If you cannot, drop it. Write at most 15 findings, most severe first.

| Severity | Meaning |
|---|---|
| `high` | Would cause a wrong result, data loss, a crash on a reachable path, or a security hole |
| `medium` | A real defect on a less likely path, or a missing test for changed behavior |
| `low` | Worth fixing, harmless if not |

## Step 4: Write the findings

Create `.review/` with a `.gitignore` containing `*`, then write `.review/findings.json`:

```json
{
  "version": 1,
  "head": "<full sha of HEAD>",
  "base": "<full sha of the merge base>",
  "reviewer": { "agent": "<your agent, e.g. claude, agy, codex>", "model": "<your model if known>" },
  "verdict": "pass",
  "summary": "<one or two sentences on the change as a whole>",
  "findings": [
    {
      "file": "src/upload.js",
      "line": 41,
      "side": "new",
      "severity": "high",
      "category": "correctness",
      "summary": "Retries a non-idempotent POST.",
      "failure_scenario": "A timeout after the server stored the upload sends it again: the file is stored twice."
    }
  ]
}
```

- `line` is the line number in the new version of the file (`side: "new"`), or in the old
  version for a removed line (`side: "old"`). For a finding about a whole file, use the first
  changed line.
- `category` is one of `correctness`, `security`, `scope`, `tests`, `maintainability`.
- `verdict` is `revise` when any finding is `high`, otherwise `pass`.
- Overwrite the file on each run; it describes one head.

## Step 5: Report

Reply with the verdict, the count by severity and the path of the file. If you were started by a
tool that asked you to hand the file back (for example with a report command), do so.

## Rules

- Never modify the code under review, stage, commit, push, or comment on the code host
- Every finding names a file, a line and a concrete failure, verified against the code
- No style findings; at most 15 findings
- The only files written are `.review/findings.json` and `.review/.gitignore`
