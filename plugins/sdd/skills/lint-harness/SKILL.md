---
name: lint-harness
description: >
  Use when a skill, agent, or standards document changed and its instruction text should be
  checked for the anti-patterns that make agents misbehave — step-delegation references and rule
  drift. Judgment-level review only. Does not trigger for documentation structure (that is
  /sdd:audit), and does not replace the mechanical gates in agent-framework's scripts/checks, which run in
  its CI.
---

> **Configuration.** This skill uses project-specific commands and branch names. Resolve each placeholder from `.claude/sdd/config.json` at the repo root (keys: `commands.test`→`<TEST_CMD>`, `commands.testOne`→`<TEST_CMD> <test-file>`, `commands.lint`→`<LINT_CMD>`, `commands.build`→`<BUILD_CMD>`, `commands.dev`→`<DEV_CMD>`, `commands.devHost`→`<DEV_HOST_CMD>`, `commands.install`→`<INSTALL_CMD>`, `branching.devBranch`→`<DEV_BRANCH>`, `branching.mainBranch`→`<MAIN_BRANCH>`, `source.dir`→`<SOURCE_DIR>`, `branching.featurePrefix`→ the `feature/` prefix in `<feature-branch>`). If `.claude/sdd/config.json` is absent, auto-detect: read `package.json` scripts (npm/pnpm/yarn) or `pyproject.toml`/`Makefile` (python) for test/lint/build/dev commands; default branches to `main` (and `development` only if it exists on the remote); default `<SOURCE_DIR>` to `src`. Use the resolved values wherever a placeholder appears below.

**Usage:** `/sdd:lint-harness`

Inspect the agent instruction harness for known anti-patterns. Run this skill after any change to a file in `.claude/skills/`, `.github/copilot-instructions.md`, `AGENTS.md`, or `docs/standards/**/design.md`.

See `${CLAUDE_PLUGIN_ROOT}/standards/harness.md` for the full background and cross-reference design rules.

---

## Step 1: Collect files to inspect

**1a. Execution-layer files (always inspected).** Read each of these in full:

```
.github/copilot-instructions.md
.claude/skills/*/SKILL.md
.claude/agents/*.md
${CLAUDE_PLUGIN_ROOT}/skills/*/SKILL.md
${CLAUDE_PLUGIN_ROOT}/agents/*.md
```

**1b. Standards files (prefilter, then conditionally read).** Do **not** read every file under `docs/standards/` — compute the diff first and only read the files it returns:

```bash
BASE=$(git merge-base HEAD origin/<DEV_BRANCH> 2>/dev/null || git merge-base HEAD origin/<MAIN_BRANCH> 2>/dev/null || echo "HEAD")
CHANGED_STANDARDS=$(git diff --name-only "$BASE" -- 'docs/standards/**/design.md')
echo "$CHANGED_STANDARDS"
```

This returns committed and uncommitted changes since the branch diverged from its base.

- If `$CHANGED_STANDARDS` is empty → skip Step 5 entirely. Do not read any standards files.
- If `$CHANGED_STANDARDS` is non-empty → read only those files in full. Do not read unchanged standards.

## Step 2: Check for step-delegation cross-references

For every numbered step in every skill file and in `copilot-instructions.md`, check whether the step's **only** content is a pointer to another file (e.g. "see `<file>`" or "refer to `<file>`" with no other instruction).

Flag any such step as a **step-delegation cross-reference** — an anti-pattern where a mandatory step is silently outsourced to a document the agent may never read.

> A step that references another file *in addition to* providing its own instruction is acceptable. Only flag steps where the cross-reference is the entire instruction.

## Step 3: Check for prohibited screenshot mechanisms

Search all execution-layer files for:

1. `gh release create` — prohibited for hosting PR screenshots. Flag every occurrence with file name and line context.
2. Any instruction to use the Playwright MCP browser to navigate to `github.com` for the purpose of uploading screenshots. Flag every occurrence.

Report each finding with a quoted excerpt.

## Step 4: Check for rule drift between `copilot-instructions.md` and skills

The following rules must appear in **both** `copilot-instructions.md` **and** the `create-pr` skill (`.claude/skills/create-pr/SKILL.md`), because they apply to both reactive sessions and skill-driven sessions:

| Rule | Expected in both |
|---|---|
| Before/after screenshots required for UI-changing PRs | ✅ |
| Never commit screenshot files to any git branch | ✅ |
| Never use `gh release create` for screenshots | ✅ |
| Never use Playwright MCP browser to navigate to github.com for upload | ✅ |
| Placeholder text required when upload fails | ✅ |
| Never create a GitHub Release to host screenshots | ✅ |

For each rule, verify it is explicitly stated in both files. If a rule is present in one but not the other, flag it as **rule drift**.

> Exact wording does not need to match — the substance must be present. A cross-reference ("see `copilot-instructions.md`") does **not** satisfy the self-containment requirement.

## Step 5: Check changed standards for skill-name references

Scope: only the files in `$CHANGED_STANDARDS` from Step 1b. Do not scan other standards.

For each such file, search for occurrences of `/<skill-name>` where `<skill-name>` is any skill in the harness. Get the list of skill names from the skill directories under `.claude/skills/` and, if present, the plugin's `skills/` directory:

```bash
ls -1 .claude/skills/
```

Use a regex that matches a skill invocation but excludes filename paths like `specs/<domain>/tasks.md` or `docs/standards/branching-model/design.md`. Ripgrep (used by Grep) does not support lookaround, so use character classes to bound the match:

```
(^|[^/\w-])/<skill-names-joined-by-|>([^\w.-]|$)
```

Build the pattern concretely by joining the skill names with `|`, then run it via Grep with the standards file path. Example:

```
(^|[^/\w-])/(architect|audit|branching-model|create-pr|critique|fix-pr|implement|lint-harness|plan|prepare-docs|publish|qa|review-pr|sdd-init|ship|spec|tasks|test)([^\w.-]|$)
```

This allows `` `/lint-harness` `` (backtick before, backtick after), ` /create-pr ` (spaces), but rejects `tasks.md`, `design.md`, and `specs/<domain>/tasks.md`.

Flag every match — both inside and outside backticks — because prescriptive leaks (e.g. "Run `/lint-harness` after…") and illustrative examples (e.g. "AGENTS.md saying 'use `/create-pr`'") both show up in backticks and can't be distinguished mechanically.

Report each finding with file, line number, and the surrounding sentence. For each, the author should confirm which category it falls into:

- **Illustrative** — the standard is demonstrating what a correct navigational pointer looks like (acceptable; keep as-is)
- **Prescriptive** — the standard is telling the reader to run the skill (violates the "standards define *what*, skills define *how*" contract; rephrase to describe the obligation neutrally and leave the skill binding to AGENTS.md routing)

> Rationale: a standard that names a specific skill as the enforcement mechanism couples the rule to a workflow implementation and inverts the "skill references standard, not reverse" direction.

If Step 1 returned no changed standards files, skip this step.

## Step 6: Report findings

Output a structured report:

```
## Lint Harness Report

### Step-delegation cross-references
<list each finding: file, step number, quoted content>
— or —
None found.

### Prohibited screenshot mechanisms
<list each finding: file, line excerpt>
— or —
None found.

### Rule drift
<list each rule that is missing from one of the two files>
— or —
None found.

### Skill-name references in changed standards
<list each finding: file:line, quoted sentence, category (illustrative or prescriptive)>
— or —
None found.
— or —
Skipped — no changed standards files.

### Summary
PASS — no anti-patterns found.
— or —
FAIL — N issue(s) found. See details above.
```

If the report is FAIL, describe what changes are needed to resolve each finding, following the rules in `${CLAUDE_PLUGIN_ROOT}/standards/harness.md`.
