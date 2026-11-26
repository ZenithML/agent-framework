# Flat skill prefix: namespace flat-installed skills — Requirements

**Status:** Review
**Last Updated:** 2026-11-26

Scope: `scripts/install-skills.sh` (flat copy), `plugins/sdd` 0.20.0, `plugins/render` 0.3.0.

## Problem Statement

A flat install copies the harness skills into `.claude/skills/<name>/` without the plugin
namespace, so they are invoked as `/ship`, `/spec`, `/plan`, `/review-pr`. Claude Code now ships
a built-in `ship` skill, so in a flat-installed project the two share the name `/ship`. The plugin install is unaffected because its skills carry the `sdd:` namespace
(`/sdd:ship`). Other bare names can clash the same way (Claude Code also has a built-in `/plan`), so renaming
only `ship` would leave the next clash in place.

Skill names may only contain lowercase letters, digits and hyphens, so the plugin's
`sdd:` namespace cannot be copied as is. The harness already has one prefixed skill,
`sdd-init`, named that way to avoid Claude Code's built-in `/init`.

## Goals

Terms used below. The **skill set** is the names of the skill directories the install copies
(`plugins/sdd/skills/*`, plus `plugins/render/skills/*` with `--with-render`). A skill's **flat
name** is `<plugin>-<skill>`, or the source name when it already starts with `<plugin>-`. An
**invocation** is `/` or `$` directly followed by a name in the skill set (optionally written
`/sdd:<skill>` or `/render:<skill>`), where the character before the `/` or `$` is the start of
the line, whitespace, or one of `` ` ( [ ' " `` and the name is not followed by a letter, digit,
`_`, `-`, `/`, or by `.` and a letter. A **skill path** is `.claude/skills/<skill>/` or
`${CLAUDE_PLUGIN_ROOT}/skills/<skill>/` with `<skill>` in the skill set.

- **G1 Prefixed names.** A flat install puts each skill in `.claude/skills/<flat name>/` and sets
  its SKILL.md frontmatter `name:` to the flat name: `/sdd-ship`, `/sdd-spec`, `/sdd-plan`,
  `/render-frames`, and so on.
- **G2 No double prefix.** `sdd-init` stays `sdd-init`, `render-init` stays `render-init`.
- **G3 Consistent references.** In the installed skills, agents and standards markdown and the seeded `AGENTS.md` template, every
  invocation is rewritten to `/<flat name>` (or `$<flat name>`), and every skill path to
  `.claude/skills/<flat name>/`. The one exception is the existing plugin note: an invocation
  written `` `/sdd:<skill>` when installed as a plugin `` is left as is. Text that is not an
  invocation or a skill path (for example `docs/specs/<domain>/tasks.md`, `src/test/`, the word
  "plan") is unchanged.
- **G4 Plugin names unchanged.** The source directories under `plugins/*/skills/` and their
  `name:` fields do not change, so marketplace, vendored and `scripts/dev.sh` installs keep
  `/sdd:ship`.
- **G5 Clean upgrade.** On a re-run over a flat install with a `.harness-manifest`, each harness
  file the manifest lists under an old `skills/<skill>/` is moved to `skills/<flat name>/` before
  the usual sync, and its manifest entry moves with it, so the usual rules apply under the new
  path: unedited files are updated, an edited file keeps the user's edits and its upstream copy
  goes to `.claude/sdd/upstream/` only when upstream also changed it. A moved, edited SKILL.md
  gets its `name:` line set to the flat name. A pending upstream copy under
  `.claude/sdd/upstream/skills/<skill>/` moves the same way. When the destination file already
  exists, the old file is not moved and is handled as a file the release no longer ships
  (deleted if unedited, kept if edited). Each moved directory is reported on stdout as
  `Renamed skills/<skill>/ -> skills/<flat name>/`. Files the manifest does not list are never
  moved or deleted. The same applies to render skills.
- **G6 Legacy warning.** After the sync, every `.claude/skills/<skill>/` directory that still
  exists, with `<skill>` a skill-set name whose flat name differs, is reported on stderr as
  `Warning: legacy skill directory .claude/skills/<skill>/ left in place (<reason>)`, where
  `<reason>` is `holds files the installer did not move` or `no .harness-manifest`. The install still succeeds (exit 0) and
  still writes the prefixed directory.
- **G7 Seeded routing and docs.** The seeded `AGENTS.md` template, the installer's closing hint
  (`run /sdd-init`, Codex `$sdd-init`), `docs/installation.md`, `docs/plugins.md` and the
  `sdd-init` skill use the flat names, and `sdd-init` detects a flat install by
  `.claude/skills/sdd-ship/SKILL.md` (or the pre-0.20 `.claude/skills/ship/SKILL.md`).
- **G8 Codex and agy.** `.agents/skills` still links to `.claude/skills`, so Codex and agy list
  the same flat names.
- **G9 Release.** `plugin.json` and `marketplace.json` say sdd 0.20.0 and render 0.3.0, and
  `tests/install-paths.sh` covers the stories below.

## Out of Scope

- A switch to keep the old bare names. Consumers update their own docs to the flat names.
- This repository's own source checkout, where `.claude/skills` links to the unprefixed
  sources; `scripts/dev.sh` already gives namespaced `/sdd:ship` there.
- The vendored install's copied `.claude/skills/sdd:<name>/` directories (`scripts/vendor.sh`).
- Upgrading consumers (zenith-agent-platform pin, agent-anywhere, zenith): one follow-up PR per
  layer after this release.
- Any UI: this is a CLI, docs and skill-text change, so WCAG does not apply.

## User Stories & Acceptance Criteria

### Story 1: Fresh flat install uses flat names

**Given** an empty project
**When** `scripts/install-skills.sh <project>` runs
**Then** `.claude/skills/sdd-ship/SKILL.md` exists with `name: sdd-ship`, `.claude/skills/ship/`
does not exist, `.claude/skills/sdd-init/SKILL.md` has `name: sdd-init`, every directory under
`.claude/skills/` starts with `sdd-`, none starts with `sdd-sdd-`, and the closing output says
`/sdd-init`.

### Story 2: Installed text invokes the flat names

**Given** a fresh flat install
**When** the installed `.claude/skills`, `.claude/agents` and `.claude/standards` markdown is
searched
**Then** no invocation (G3) of any skill-set name remains in its source form, with or without
`/sdd:`, except the plugin note of G3; in particular no line contains `` `/ship` ``,
`` `/spec ``, `` `/create-pr` `` or `$ship`; `.claude/skills/sdd-triage-pr/SKILL.md` runs
`.claude/skills/sdd-triage-pr/scripts/triage.py`; `.claude/standards/ship-runbook.md` names
`.claude/skills/sdd-ship/SKILL.md` and `/sdd-review-diff`; and the text
`docs/specs/<domain>/tasks.md` still occurs in the installed planner role unchanged.

### Story 3: Render skills are prefixed too

**Given** an empty project
**When** the installer runs with `--with-render`
**Then** `.claude/skills/render-frames/SKILL.md` has `name: render-frames`,
`.claude/skills/render-dcg/` exists, `.claude/skills/render-init/` exists, and no
`render-render-init` or bare `frames` directory exists.

### Story 4: Upgrade moves an unedited old install

**Given** a project flat-installed by the previous release (unprefixed names, with a manifest)
**When** the new installer runs over it
**Then** no unprefixed harness skill directory remains, the prefixed directories match a fresh
install, the manifest lists no `skills/ship/` path, stdout contains
`Renamed skills/ship/ -> skills/sdd-ship/`, and stderr has no `legacy skill directory` warning.

### Story 5: Upgrade keeps a local edit

**Given** the old install's `.claude/skills/ship/SKILL.md` was edited locally, and the old
release's copy of that file differs from the new release's (it always does: the new one says
`name: sdd-ship`)
**When** the new installer runs
**Then** `.claude/skills/sdd-ship/SKILL.md` holds the local edit with `name: sdd-ship`,
`.claude/skills/ship/` is gone, `.claude/sdd/upstream/skills/sdd-ship/SKILL.md` exists, and
stderr lists `skills/sdd-ship/SKILL.md` under the existing "Kept local edits, but upstream changed
these too" block.

### Story 5b: Pending upstream copies, existing destinations, render

**Given** an old install with a manifest where `.claude/sdd/upstream/skills/ship/SKILL.md` is a
pending conflict copy, `.claude/skills/sdd-ship/SKILL.md` already exists unedited beside an
unedited `.claude/skills/ship/SKILL.md`, and render skills were installed unprefixed
**When** the new installer runs with `--with-render`
**Then** no `.claude/sdd/upstream/skills/ship/` remains, `.claude/skills/ship/` is gone (the
unedited old file is deleted as no longer shipped), and `.claude/skills/frames/` is gone with
`render-frames/` in its place.

### Story 6: A user's own file survives and is named

**Given** an old install with a manifest where the user added `.claude/skills/ship/notes.md`
**When** the new installer runs
**Then** `notes.md` is still there, the harness files moved to `sdd-ship/`, and stderr warns
`legacy skill directory .claude/skills/ship/ left in place (holds files the installer did not move)`.

### Story 7: An old install without a manifest is warned about

**Given** an old flat install whose `.harness-manifest` was deleted
**When** the new installer runs
**Then** it exits 0, the prefixed directories are installed, `.claude/skills/ship/` is left in
place, and stderr warns
`legacy skill directory .claude/skills/ship/ left in place (no .harness-manifest)`.

### Story 7b: Seeded routing and sdd-init detection

**Given** an empty project with no `AGENTS.md`
**When** the installer runs
**Then** the seeded `AGENTS.md` contains `/sdd-ship` and `$sdd-ship` and no `` `/ship` `` or
`$ship`, and the installed `sdd-init` skill names `.claude/skills/sdd-ship/SKILL.md` as the flat
install marker and `.claude/skills/ship/SKILL.md` as the pre-0.20 marker; `docs/installation.md`
and `docs/plugins.md` give the flat commands as `/sdd-<skill>`.

### Story 8: Re-running is quiet

**Given** a project already installed by this release
**When** the installer runs again
**Then** no file changes, and the output has no `Renamed` line and no legacy warning.

### Story 9: Codex and agy see the flat names

**Given** an install with `--harness claude,codex`
**When** `.agents/skills` is listed
**Then** it resolves to `.claude/skills` and contains `sdd-ship/SKILL.md`.

### Story 10: Plugin sources keep the namespace

**Given** the repository after the change
**When** `plugins/sdd/skills/ship/SKILL.md` and both manifests are read
**Then** the directory is still `ship` with `name: ship`, and the manifests say sdd 0.20.0 and
render 0.3.0.

## Constraints

- The installer stays bash 3.2 compatible and does its rewriting in stdlib python3 (macOS).
- The rewrite is deterministic: the same release installs byte-identical files, so the manifest
  logic keeps telling local edits from upstream changes.
- No generated copies are committed to this repository.

## References

- `scripts/install-skills.sh`, `tests/install-paths.sh`, `docs/installation.md`
- [ship-orchestration](../ship-orchestration/requirements.md) (the `ship` skill)
