# Contributing to agent-framework

## Repository layout

This repo is both the plugin and its marketplace. Quick orientation:

```
.claude-plugin/marketplace.json     — marketplace manifest (this repo = the marketplace)
plugins/sdd/
  .claude-plugin/plugin.json        — plugin manifest (name, version, author)
  skills/<name>/SKILL.md            — slash commands, invoked as /sdd:<name>
  agents/<name>.md                  — specialist agents called by skills
  hooks/                            — SessionStart hook (remote/web setup)
  standards/                        — shared harness conventions
  config/                           — config schema + examples
  templates/docs/                   — canonical doc templates
scripts/
  vendor.sh                         — copy the plugin into a consuming project (see README)
```

## Setting up locally

No build step. Clone, then load the plugin into any test repo:

```bash
git clone git@github.com:zenithml/agent-framework.git
```

In a Claude Code session inside the test repo:

```
# Local development (use a local checkout)
/plugin marketplace add /path/to/agent-framework
/plugin install sdd@sdd-harness --scope project
```

Recommended for consumers (fetches plugin from GitHub):

```
/plugin marketplace add zenithml/agent-framework
/plugin install sdd@sdd-harness --scope project
```

Vendoring into a consumer repository (commit a local, pinned copy):

```
# Run from a checkout of this repo:
scripts/vendor.sh /path/to/your-project
```

The vendor script uses the consuming repository's directory name as the local marketplace key by default (e.g. `.claude/vendors/my-repo` and plugin id `sdd@my-repo`). Use `--name <key>` to choose a custom marketplace key, or `--dry-run` to preview actions without changing files.

Edits to a local checkout are picked up immediately — no reinstall needed.

## Making changes

### Editing a skill

Skills live at `plugins/sdd/skills/<name>/SKILL.md`. Each file:

- Starts with YAML frontmatter (`name`, `description`)
- Contains a **Configuration preamble** (copy verbatim from any existing skill) so the agent resolves `.claude/sdd/config.json` placeholders
- Uses numbered steps — see `plugins/sdd/standards/harness.md` for the cross-reference design rules that govern execution-layer docs

After editing any skill, run `/sdd:lint-harness` before opening a PR.

### Adding a skill

1. Create `plugins/sdd/skills/<name>/SKILL.md`
2. The directory name becomes the slash command: `skills/my-skill/` → `/sdd:my-skill`
3. Run `claude plugin validate ./plugins/sdd --strict` and `/sdd:lint-harness`

No manifest edit is needed. Claude Code always scans a plugin's `skills/` directory, so a new directory is picked up automatically. `plugin.json` deliberately carries **no** `skills` field — its schema expects directory paths, not per-skill entries, and a hand-maintained list would only be a second place to forget.

### Editing an agent

Agents live at `plugins/sdd/agents/<name>.md`. Skills spawn them by name. Before renaming an agent, search the skills directory for its current name to find all callsites.

### Config schema

`plugins/sdd/config/config.schema.json` is the source of truth for `.claude/sdd/config.json` shape. After a schema change, update both example files (`config.example.npm.json`, `config.example.python.json`) and the placeholder table in `README.md`.

### Standards

`plugins/sdd/standards/` defines *what* the conventions are. Skills define *how* agents execute them. Keep the two layers separate — standards should not name specific skills as enforcement mechanisms. See `plugins/sdd/standards/harness.md` for the full design rules and known anti-patterns.

## Linting

Two checks, with different jobs.

**Manifest and frontmatter — mechanical.** Run after any change to a manifest, skill, or agent:

```bash
claude plugin validate . --strict            # marketplace.json + every listed plugin
claude plugin validate ./plugins/sdd --strict  # plugin.json, skill/agent frontmatter, hooks.json
```

`--strict` treats warnings as errors, which is what makes the marketplace/plugin version-agreement warning a failure rather than a note.

**Harness anti-patterns — judgment.** Run after editing any skill, agent, or standard:

```
/sdd:lint-harness
```

It checks for step-delegation cross-references, prohibited screenshot mechanisms, rule drift between execution-layer files, and skill-name references in changed standards.

Neither runs in CI yet. Closing that gap is the P0 workstream in [`docs/specs/harness-quality/`](docs/specs/harness-quality/requirements.md).

## Versioning

Versions follow semver. For any change intended as a release:

1. Bump `"version"` in `plugins/sdd/.claude-plugin/plugin.json`
2. Bump the matching entry in `.claude-plugin/marketplace.json`
3. Commit: `git commit -am "release: v<version>"`
4. Tag the commit: `git tag v<version> && git push origin v<version>`

Consumer repos pinning `"ref": "v0.1.0"` are unaffected until they update their ref. Repos without a `ref` track `main` and pick up changes on the next session start.

## License

This project is licensed under the [Apache License 2.0](LICENSE). By submitting a pull request you agree that your contribution is licensed under the same terms (Apache-2.0 §5).

## Support

Issues and pull requests are welcome and handled on a best-effort basis — there is no support SLA. Security reports go through [`SECURITY.md`](SECURITY.md), not public issues.
