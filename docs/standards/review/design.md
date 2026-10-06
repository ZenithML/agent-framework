# PR Review — Standard

**Status:** Accepted

This standard defines the review requirements for pull requests in the `agent-framework` repository.

---

## Before Marking a PR Ready for Review

The author (human or agent) must complete all of the following:

- [ ] `/sdd:lint-harness` passes with no errors
- [ ] Both version files updated if the change introduces new or changed plugin behaviour (see [release standard](../release/design.md))
- [ ] `docs/INDEX.md` updated if a new standard or ADR was added
- [ ] Config schema examples updated if `.claude/sdd/config.json` schema changed
- [ ] PR body includes a Summary (what changed and why) and a Test Plan

---

## Reviewer Checklist

### Execution-layer integrity (skills and agents)

- No step-delegation cross-references — every step an agent must perform is written out explicitly in the document the agent reads (see [harness standard](../../../plugins/sdd/standards/harness.md#cross-reference-rules-for-execution-layer-docs))
- Configuration preamble is present and verbatim in every modified plugin skill

### Standards layer

- Standards documents describe *what* to do, not *how* the agent does it — skill names should not appear as enforcement mechanisms within the standards body itself
- Cross-references use relative paths and point to existing files

### Config and schema

- If `config.schema.json` changed: both example files (`config.example.npm.json`, `config.example.python.json`) are updated and the placeholder table in `README.md` reflects the change

### Release

- If plugin behaviour changed: version is bumped in both files per the [release standard](../release/design.md)

---

## Review Skill

Use `/sdd:review-pr` to post inline feedback. Do not push code changes directly during a review — use `/sdd:fix-pr` to act on feedback after the review.
