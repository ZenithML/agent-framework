# Review triage: say which parts of a pull request need a human — Requirements

**Status:** Approved
**Last Updated:** 2026-10-20

Scope: `plugins/sdd` 0.11.0. Adds one skill, `/sdd:triage-pr`, and the script it runs.

## Problem Statement

A reviewer with more diff than time does not review less: they *appear* to review the same amount
and skip at random. The approval looks the same whether the reviewer read every line or none,
so the skipped part is invisible, and the risky hunk is as likely to be skipped as the lockfile.

The existing tooling does not touch this. `/sdd:review-pr` makes an agent leave inline comments;
`/sdd:fix-pr` acts on comments; the review standard is a checklist for this repository's own
harness. None of them tells a human, before they start, which part of a large change needs
their eyes, which part is safe to skip and why, and none of them gives the reviewer a way to
say "I read these, not those" other than approving everything.

## Goals

- **G1 Triage.** Given a unified diff, sort every changed hunk into one of three tiers:
  **focus** (a risk signal fired — read closely), **standard** (ordinary change, no signal —
  the triage makes no claim either way), **low** (mechanical — safe to skip, with the reason).
- **G2 Reasons.** Every focus item and every low item names the rule that put it there. No
  tier assignment is unexplained.
- **G3 Ordered path.** Output is a review path in reading order: focus hunks first (grouped by
  file), then standard files, then low files collapsed into one list, with an item count and a
  line count for each tier (hunks for focus, files for standard and low) so the reviewer sees
  the size of the job before starting.
- **G4 Declared coverage.** Focus items are a checklist. The output says plainly that an
  unticked item at approval time is an unreviewed item, so a partial review is declared rather
  than hidden.
- **G5 Deterministic floor.** The tiering is done by a stdlib-only Python script, so the same
  diff always gives the same tiers. The agent running the skill adds a one-line "what to check"
  per focus hunk and may promote a hunk to focus by re-running the script with `--promote`; the
  script has no way to demote, and the skill forbids editing tiers by hand.
- **G6 Repo rules.** A repository can add its own focus paths, low paths and focus content
  patterns in `.claude/sdd/review-triage.json`.
- **G7 Sources.** The skill triages a GitHub PR (`gh pr diff`), or the current branch against
  a base ref (`git diff`) when there is no PR.
- **G8 Optional comment.** With `--comment`, the skill posts the triage as one PR comment and
  updates that same comment on re-runs instead of adding another, keeping the reviewer's ticks
  on items that did not change. Without it, nothing is posted.
- **G9 Machine output.** `--format json` gives the same result as JSON for other tools.
- **G11 Visual page.** `--format html` writes one self-contained page: the ordered review path
  with each hunk's diff, a per-item read tick, and a live count of unread "Read closely" lines.
- **G10 Docs and release.** The skill is listed in `docs/plugins.md`, AGENTS.md routing, the
  review standard and the lint-harness skill-name list; it is held to the strict schema, ships
  baseline evals and a file manifest; the sdd version is 0.11.0 in both manifests.

## Out of Scope

- Triage of a whole PR backlog (many PRs at once). One PR at a time; a backlog view can be
  built on the JSON output later.
- Tracking what a reviewer actually opened or scrolled past. Not observable from git or the
  GitHub API without a browser extension.
- Blocking or gating an approval on the checklist. The tool makes skipping visible; it does not
  enforce reading.
- Reviewing the code. `/sdd:review-pr` reviews; this skill only says where to look.
- Semantic risk analysis (call graphs, coverage deltas). Heuristics only, and the output says so.

## User Stories & Acceptance Criteria

### Story 1: See the size of the job before starting

**Given** a diff of 20 files where a lockfile accounts for most changed lines
**When** the reviewer runs `/sdd:triage-pr`
**Then** the output opens with total files and changed lines, then the item and line counts for
focus (hunks), standard (files) and low (files), and the lockfile appears under low with the reason `lockfile`.

### Story 2: Risky hunks surface first, with reasons

**Given** a diff where one hunk in `src/auth/session.ts` adds an `eval(` call and another file
changes ordinary logic
**When** the triage runs
**Then** the `session.ts` hunk is listed under focus before any standard item, with both
reasons (`sensitive path: auth`, `adds eval(`), and the ordinary file is under standard.

### Story 3: Weakened tests are focus

**Given** a diff that removes assertion lines from a test file, adds a skip marker, or deletes
a test file
**When** the triage runs
**Then** each of those is a focus item with the reason `removes assertions`, `adds skip marker`
or `deletes test file`.

### Story 4: Mechanical change is low, with the reason

**Given** a diff containing a lockfile, a generated or vendored file, a whitespace-only hunk,
a pure rename with no content change, and a mode-only change
**When** the triage runs
**Then** each is low with the reason `lockfile`, `generated or vendored`, `whitespace only`,
`pure rename` or `mode change only`, and none of them is scanned for content signals.

### Story 5: Declared coverage

**Given** any triage with at least one focus item
**When** it is printed as markdown
**Then** every focus hunk is a `- [ ]` checklist line, and a closing Coverage section says that
tiers are heuristic, that standard is not "safe", and that focus items unticked at approval
were not reviewed and should be named in the review.

### Story 6: Repository rules

**Given** `.claude/sdd/review-triage.json` with `focus_paths: ["^ledger/"]`
**When** a diff changes `ledger/rates.py`
**Then** that file's hunks are focus with the single reason `repo rule: ^ledger/`; an invalid rules
file stops the run with a message naming the file and the problem.

### Story 7: Agent adds judgment but cannot downgrade

**Given** the script's tiering
**When** the skill presents it
**Then** each focus hunk carries a one-line "check:" the agent wrote after reading the hunk;
a hunk promoted with `--promote FILE:LINE=REASON` is a focus item with the reason
`promoted: REASON` in both markdown and JSON; no hunk the script put in focus appears in a
lower tier.

### Story 8: Post or update one comment

**Given** `/sdd:triage-pr 42 --comment`
**When** the PR has no triage comment
**Then** one comment is posted, starting with the marker `<!-- sdd:triage-pr -->`;
**and when** it is run again, that comment is edited in place, no second comment appears, and
every focus line that is unchanged since the last run keeps its tick.

### Story 9: No PR, branch diff

**Given** a branch with no open PR
**When** the user runs `/sdd:triage-pr --base main`
**Then** the triage covers `git diff main...HEAD`, and `--comment` is refused because there is
no PR to comment on.

### Story 10: Empty and malformed input

**Given** an empty diff
**When** the script runs
**Then** it prints that there is nothing to triage and exits 0;
**given** input that is not a unified diff, it exits 2 with a message saying so.

## Constraints

- Script: Python 3 standard library only, like `scripts/checks/`. Runs from the plugin root
  (`${CLAUDE_PLUGIN_ROOT}/skills/triage-pr/scripts/triage.py`) and from a flat install.
- Read-only toward the repository and the PR, except the one comment under `--comment`. Never
  approves, requests changes, or edits code.
- Deterministic: same diff and rules give byte-identical output.
- Tests run in CI with no network and no `gh`.

## References

- [`docs/standards/review/design.md`](../../standards/review/design.md)
- [`plugins/sdd/skills/review-pr/SKILL.md`](../../../plugins/sdd/skills/review-pr/SKILL.md)
- [`plugins/sdd/standards/harness.md`](../../../plugins/sdd/standards/harness.md)
- [design.md](design.md) · [tasks.md](tasks.md)
