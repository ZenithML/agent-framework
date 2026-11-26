# Flat skill prefix: namespace flat-installed skills — Design

**Status:** Review
**Last Updated:** 2026-11-26

## Architecture

### Component / Hook Design

All behaviour lives in `scripts/install-skills.sh`, in the stages it already has.

1. **Stage (step 1).** After copying the plugin trees into the temp stage, build the rename map:
   for each copied skill directory `skills/<skill>` from plugin `<p>` (`sdd`, or `render` with
   `--with-render`), the flat name is `<skill>` when it starts with `<p>-`, else `<p>-<skill>`.
   Rename the staged directory and set the SKILL.md frontmatter `name:` to the flat name. The map
   (`{"<skill>": "<flat>"}`, only entries that differ) is written to `$STAGE/renames.json`; it is
   never installed.
2. **Rewrite (step 1c).** The existing Python rewrite gains two rules, applied to every staged
   `.md` under `skills/`, `agents/`, `standards/`, and to `templates/agent-routing.md`:
   - **Skill path:** `.claude/skills/<skill>/` (which `${CLAUDE_PLUGIN_ROOT}/skills/<skill>/`
     has already become) -> `.claude/skills/<flat>/`, for `<skill>` in the map.
   - **Invocation:** regex
     `(?<![^\s`(\['"])([/$])(?:(?:sdd|render):)?(<names>)(?![\w/-]|\.\w)` where `<names>` is the
     skill set (longest first), replaced by `\1<flat>`. A name already in flat form (`sdd-init`)
     maps to itself. Plugin-note exception: a match written with `sdd:` or `render:` and
     followed directly by `` ` when installed as a plugin`` (the lookahead the current rule
     already uses) is left as is. The old `/sdd:` -> `/` rule is replaced by this. Non-markdown
     staged files (`.py`, `.sh`, `.json`) carry no invocations or skill paths today (checked by
     grep) and are not rewritten.
3. **Migrate (step 2, new block before the sync loop).** With a manifest (`old`) and a non-empty
   map: for each manifest key `skills/<skill>/<rest>` with `<skill>` in the map, compute
   `skills/<flat>/<rest>`, and apply the first rule that fits:
   - **old file exists, new file missing:** move it (creating parents), rename the manifest key
     (keeping the old hash), and if it is an edited `SKILL.md` (hash differs from the manifest)
     replace the first `name:` line inside its frontmatter (between the first two `---` lines)
     with `name: <flat>`, keeping the line ending. A file with no such line is moved unchanged.
   - **old file missing, new file exists** (a run that stopped after moving, since the manifest
     is written only at the end of the sync): rename the manifest key only, keeping the old hash,
     so an edit made before the move is still seen as an edit. Skipped when the old manifest
     already has the new key.
   - **both exist:** leave the old key alone, so the existing "no longer shipped" pass deletes the
     old file when unedited or keeps it when edited (then the legacy warning names the dir).
   - **neither exists:** nothing.

   Only skills in the map (the staged ones) migrate. Render skills from an earlier
   `--with-render` install, re-run without the flag, keep today's behaviour: their files are no
   longer shipped and are retired by the existing rules. Moves use the manifest's file list, so
   subdirectories move file by file; a legacy skill directory that is a symlink is never moved
   or followed, only warned about. Move `sdd/upstream/skills/<skill>/<rest>` to the
   flat path the same way. Remove old directories left empty. Print
   `  Renamed skills/<skill>/ -> skills/<flat>/` once per directory that had a move.
4. **Legacy warning (step 2, after the sync).** For each `<skill>` in the map, if
   `.claude/skills/<skill>/` still exists, print to stderr
   `Warning: legacy skill directory .claude/skills/<skill>/ left in place (<reason>)`, reason
   `no .harness-manifest` when there was no manifest, else `holds files the installer did not move`.
5. **Text.** Source edits for the bare names that are not invocations of the form above:
   `templates/agent-routing.md` is rewritten by the installer (rule 2), `sdd-init` detection
   names both markers, closing hints print `/sdd-init` and `$sdd-init`, docs list the flat names.

### Data Model

- `renames.json` (stage only): `{"ship": "sdd-ship", ..., "frames": "render-frames"}`.
- `.harness-manifest` keys change from `skills/ship/...` to `skills/sdd-ship/...`. Format unchanged.

### Data Flow

copy plugins -> stage rename + `name:` -> markdown rewrite -> (manifest) migrate old paths ->
existing sync (update / keep / conflict copy / retire) -> legacy warning -> hook, links, stamp.

## Decisions

| # | Question | Options Considered | Decision | Rationale |
|---|----------|--------------------|----------|-----------|
| 1 | Which skills get a prefix | only `ship`; every skill | every skill | `/plan` already clashes; later built-ins will too |
| 2 | Prefix form | `sdd:` (not a valid name), `sdd-`, `sdd_` | `<plugin>-` | only separator skill names allow; matches `sdd-init` and `render-init` |
| 3 | Where the prefix is applied | rename source dirs; installer only | installer only | plugin installs keep `/sdd:ship`, no `sdd:sdd-ship` |
| 4 | Edited SKILL.md during migration | leave `name:` alone; rewrite it | rewrite only the `name:` line | an old name would keep shadowing a built-in; the rest of the edit is the user's |
| 5 | Old dir with user files or no manifest | delete; warn | warn, exit 0 | never delete what the installer did not record |

## Failure Modes & Degradation Matrix

| Category | Failure Condition | Expected System Behavior | Test Scenario |
|---|---|---|---|
| Transport/Network | No network is used; the nearest analogue is a run that aborts after moving files but before the manifest is written | The next run renames the stale manifest keys and treats an edited moved file as edited | re-run after an interrupted upgrade completes the migration |
| Concurrency/State | Re-running on a migrated project | Nothing moves, nothing is warned about | re-run is quiet |
| Concurrency/State | Both `ship/` and `sdd-ship/` present | Unedited old file deleted; an edited one kept and its dir warned about | existing destination retires the old file |
| Concurrency/State | Pending upstream copy under the old path | It moves to the flat path | pending upstream copy moves |
| Boundary & Payloads | Skill already prefixed (`sdd-init`, `render-init`) | Name unchanged, no `sdd-sdd-` | no double prefix |
| Boundary & Payloads | Text that resembles a name (`docs/specs/x/tasks.md`, `src/test/`, `/tasks.md`) | Unchanged | non-invocations are untouched |
| Boundary & Payloads | No manifest, user files, or a symlink at an old dir | Old dir kept, warning on stderr, exit 0 | legacy warning names the directory |
| Boundary & Payloads | Edited SKILL.md with no frontmatter `name:` line, or CRLF endings | Moved unchanged, or name line replaced keeping CRLF | edited skill file without a name line moves unchanged |
| Boundary & Payloads | Render skills installed earlier, re-run without `--with-render` | Retired as no longer shipped, as today | render upgrade without the flag retires render files |

## Test Scenarios

### Unit Tests

All in `tests/install-paths.sh` (shell assertions over a temp project).

- fresh install: `sdd-ship/SKILL.md` with `name: sdd-ship`, no `ship/`, every dir starts `sdd-`
- no double prefix: `sdd-init` has `name: sdd-init`, no `sdd-sdd-*`
- installed markdown has no source-form invocation of any skill-set name (scan with the same
  boundary rule), triage-pr script path and runbook paths are prefixed
- non-invocations are untouched: `docs/specs/<domain>/tasks.md` still in planner.md
- render install: `render-frames`, `render-dcg`, `render-init`, no `render-render-init`
- seeded AGENTS.md has `/sdd-ship` and `$sdd-ship`, no `` `/ship` ``
- upgrade from unprefixed (simulated by renaming dirs and manifest keys back), unedited: no old
  dirs, manifest has no `skills/ship/`, `Renamed skills/ship/ -> skills/sdd-ship/` printed
  and no legacy warning on stderr; closing output says `/sdd-init`
- upgrade with edited `ship/SKILL.md`: edit kept under `sdd-ship/` with `name: sdd-ship`,
  upstream copy saved, stderr conflict block lists `skills/sdd-ship/SKILL.md`
- pending upstream copy moves to `upstream/skills/sdd-ship/`
- existing destination: unedited old file deleted; edited old file kept and warned
- render upgrade with `--with-render`: `frames/` gone, `render-frames/` present
- render upgrade without the flag: unedited render files retired, as before
- edited skill file without a `name:` line moves unchanged; CRLF `name:` line keeps CRLF
- legacy warning names the directory for a user file, a missing manifest and a symlinked dir
- re-run is quiet: no `Renamed`, no warning, no file changes
- re-run after an interrupted upgrade (file moved by hand to `sdd-ship/` and edited, manifest
  still old) keeps the edit and does not overwrite it
- plugin note `` `/sdd:x` when installed as a plugin`` survives in the installed text
- installed `sdd-init` skill names both markers; `docs/installation.md` and `docs/plugins.md`
  give `/sdd-ship` for flat installs (grep assertions in the same test)
- codex: `.agents/skills/sdd-ship/SKILL.md` resolves

### BDD Scenarios

- **Scenario:** fresh install uses flat names — Given an empty project When installed Then `sdd-ship` exists and `ship` does not
- **Scenario:** no double prefix — Given `sdd-init` and `render-init` When installed Then their names are unchanged
- **Scenario:** non-invocations are untouched — Given installed markdown When searched Then invocations are prefixed and paths like `docs/specs/<domain>/tasks.md` are unchanged
- **Scenario:** render skills are prefixed — Given `--with-render` When installed Then `render-frames` exists
- **Scenario:** upgrade moves an unedited old install — Given an unprefixed install with manifest When re-installed Then old dirs are gone and renames are printed
- **Scenario:** upgrade keeps a local edit — Given an edited old SKILL.md When re-installed Then the edit is under the flat dir with the flat name
- **Scenario:** pending upstream copy moves — Given an old upstream copy When re-installed Then it is under the flat path
- **Scenario:** legacy warning names the directory — Given user files or no manifest When re-installed Then stderr names the old dir and exit is 0
- **Scenario:** existing destination retires the old file — Given both `ship/` and `sdd-ship/` When re-installed Then the unedited old file is deleted and an edited one is kept and warned
- **Scenario:** edited skill file without a name line moves unchanged — Given an edited old SKILL.md with no `name:` When re-installed Then it moves byte-identical
- **Scenario:** render upgrade without the flag retires render files — Given an old render install When re-installed without `--with-render` Then unedited render files are removed
- **Scenario:** re-run is quiet — Given a current install When re-run Then nothing changes and nothing is renamed or warned
- **Scenario:** re-run after an interrupted upgrade completes the migration — Given a half-moved tree with the old manifest When re-run Then the migration finishes
- **Scenario:** seeded routing uses flat names — Given no AGENTS.md When installed Then it names `/sdd-ship`
- **Scenario:** codex sees flat names — Given `--harness claude,codex` When `.agents/skills` is listed Then `sdd-ship` is there
- **Scenario:** plugin sources keep the namespace — Given the repo When `plugins/sdd/skills/ship` is read Then it is `name: ship` and manifests say 0.20.0 / 0.3.0

### BDD Traceability

| BDD Scenario | Component(s) / Module(s) | Notes |
|---|---|---|
| fresh install uses flat names | stage rename | Story 1 |
| no double prefix | stage rename | Story 1, 3 |
| non-invocations are untouched | rewrite | Story 2 |
| render skills are prefixed | stage rename | Story 3 |
| upgrade moves an unedited old install | migrate | Story 4 |
| upgrade keeps a local edit | migrate + sync | Story 5 |
| pending upstream copy moves | migrate | Story 5b |
| legacy warning names the directory | legacy warning | Story 6, 7 |
| existing destination retires the old file | migrate + sync | Story 5b |
| edited skill file without a name line moves unchanged | migrate | matrix row |
| render upgrade without the flag retires render files | sync | matrix row |
| re-run is quiet | migrate + sync | Story 8 |
| re-run after an interrupted upgrade completes the migration | migrate | matrix row |
| seeded routing uses flat names | rewrite, template | Story 7b |
| codex sees flat names | link step | Story 9 |
| plugin sources keep the namespace | manifests | Story 10 |

### QA Scenarios

Setup for upgrade scenarios: `git worktree add <old> v0.19.0` and run `<old>/scripts/install-skills.sh`
into a fresh temp git repo `<p>` to get an unprefixed install with a manifest.

- Story 1: install into an empty temp repo; `ls .claude/skills` shows only `sdd-*`; output ends
  with `run /sdd-init`.
- Story 2: in that repo, `grep -rn '`/ship`' .claude` and `grep -rn '\$ship' .claude` find
  nothing; `.claude/skills/sdd-triage-pr/SKILL.md` names `.claude/skills/sdd-triage-pr/scripts/`.
- Story 3: install with `--with-render`; `render-frames`, `render-dcg`, `render-init` listed.
- Story 4: run this branch's installer over `<p>`; no `ship/` dir; `Renamed` lines printed; no
  legacy warning.
- Story 5: in a fresh `<p>`, append a line to `.claude/skills/ship/SKILL.md`, upgrade; the line is
  in `sdd-ship/SKILL.md`, which says `name: sdd-ship`; `.claude/sdd/upstream/skills/sdd-ship/`
  exists.
- Story 5b: in a fresh `<p>` with `--with-render`, upgrade with `--with-render`; `frames/` gone.
- Story 6: in a fresh `<p>`, add `.claude/skills/ship/notes.md`, upgrade; file survives; warning.
- Story 7: in a fresh `<p>`, delete `.claude/sdd/.harness-manifest`, upgrade; exit 0; warning.
- Story 7b: install into an empty repo; `AGENTS.md` names `/sdd-ship`;
  `.claude/skills/sdd-init/SKILL.md` names both markers.
- Story 8: run the installer twice; second run prints no `Renamed` or warning; `git status` clean
  after committing the first.
- Story 9: install with `--harness claude,codex`; `ls .agents/skills/` shows `sdd-ship`.
- Story 10: `head -3 plugins/sdd/skills/ship/SKILL.md` shows `name: ship`; both manifests say
  0.20.0 for sdd and 0.3.0 for render.

## Edge Cases & Error Handling

- A skill name that is a prefix of another (`qa`, `qa-explore`; `review-pr`, `review-diff`):
  the regex alternation lists longer names first and requires a non-`[\w/-]` boundary.
- A `$` before a name inside a shell snippet (`$test`) is rare in the harness text; the boundary
  rule treats it as an invocation, which matches Codex usage.
