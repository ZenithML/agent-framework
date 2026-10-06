# agent-framework

An open-source framework of reusable [Claude Code plugins](https://code.claude.com/docs/en/plugins) for driving work with an agent. Two of them:

| Plugin | For |
|---|---|
| **`sdd`** | The pipeline — **spec → plan → implement → QA → publish**, with embedded critic gates and a TDD implement loop |
| **`render`** | Perceptual work — domains where a failure is something you *see* rather than something that throws |

Both are stack-agnostic: project-specific commands and paths are read from a small `.claude/sdd/config.json` in each consuming repo instead of being hardcoded.

**Framework, not a hosted service.** Everything here runs inside your own Claude Code sessions and your own repository — no account, server, or external infrastructure is required. Released under the [Apache License 2.0](LICENSE).

## What's in the sdd plugin

```
plugins/sdd/
  .claude-plugin/plugin.json   — plugin manifest
  skills/<name>/SKILL.md        — 18 slash commands (invoked as /sdd:<name>)
  agents/<name>.md              — 7 pipeline agents (architect, planner, critic,
                                  executor, tester, publisher, archivist)
  hooks/                        — SessionStart hook (remote/web setup, config-driven)
  templates/docs/               — canonical requirements/design/tasks/ADR templates
  standards/                    — harness, doc-structure, branching-model, agent-pipeline
  config/                       — config.schema.json + example configs (npm, python)
```

## What's in the render plugin

```
plugins/render/
  .claude-plugin/plugin.json   — plugin manifest
  skills/<name>/SKILL.md        — 4 slash commands (invoked as /render:<name>)
  standards/                    — agent-graphics, verification
```

An agent working on a visual domain with no way to see its output is guessing, and the human becomes the only sensor in the system. This plugin is the method for fixing that: give the agent a **capture endpoint**, a **named observation set**, **numeric proxies** cheap enough to gate CI, and a **symptom-keyed traps table**.

| Skill | Does |
|---|---|
| `/render:render-init` | Build the apparatus — determinism, capture, the named set, budgets. Run once, **before** any perceptual work |
| `/render:frames` | Re-shoot the set, read every image, report against the look contract |
| `/render:tune` | Change one theme value against the set — baseline, vary, compare, keep the winner with the frames as evidence |
| `/render:trap` | Record a bug that threw nothing, keyed by its symptom, in the same change that fixes it |

It also carries the **harness / engine / theme** layering rule and its three falsifiable boundary tests (swap, transplant, and a grep for colour literals in the engine). See `plugins/render/standards/agent-graphics.md`.

> The plugin ships no rendering code. It is prose: the method, not the engine. An engine is a per-project or per-org package, because it has a different consumer and a different release cadence — and a plugin that pulled in a 3D library is a plugin nobody can install.

Marketplace manifest lives at `.claude-plugin/marketplace.json` at the repo root, so **this repo is itself the marketplace**.

### Skills (`/sdd:<name>`)

| Pipeline | Git / PR | Maintenance |
|---|---|---|
| `ship` (entry point) | `create-pr` | `sdd-init` (onboarding) |
| `spec` · `plan` · `tasks` | `fix-pr` | `audit` |
| `implement` · `critique` · `qa` | `review-pr` | `lint-harness` |
| `publish` · `prepare-docs` | `branching-model` | `test` |
| `architect` (internal) | | |

> Repository-specific release skills and release/CI-automation layers (tag-release, prepare-release, back-merge, version bumping) are **intentionally excluded** — they are too tied to each repository's GitHub Actions workflows. Each consuming repo owns its release workflow.

## Installing in a project

Pick the method that matches your situation:

| Your situation | Method |
|---|---|
| **You just want it to work** — locally, on claude.ai/code, and in CI — with no install step that can silently skip on a fresh VM | **[Flat copy](#flat-copy-recommended)** — recommended |
| You want every session to auto-pull the latest harness from GitHub | **[GitHub marketplace](#github-marketplace)** |
| You want a frozen copy committed to your repo, pinned to a version, with no GitHub access needed at runtime | **[Vendored copy](#vendored-copy)** |

All three end the same way: you run the onboarding skill once, then the **ship** skill to start the pipeline. They differ only in *how the skills get into your repo*.

> **Heads up — command names differ by method.** Flat copy installs the skills **without** the `sdd:` namespace, so you invoke them as `/ship`, `/spec`, `/sdd-init`. The marketplace and vendored methods install them as a **plugin**, which keeps the namespace: `/sdd:ship`, `/sdd:spec`, `/sdd:sdd-init`. (The `sdd-init` name avoids clashing with Claude Code's built-in `/init`.)

---

### Flat copy (recommended)

Copies the harness (skills, agents, standards, templates, config schema, and the SessionStart hook) straight into your project's `.claude/` directory. They become ordinary committed files, so **every session type loads them unconditionally** — no marketplace, no install step to go wrong on a cloud VM.

**Step 1 — get a checkout of this harness** (anywhere on your machine):

```bash
git clone https://github.com/zenithml/agent-framework.git
cd agent-framework
```

**Step 2 — install it into your project.** Point the script at your project's root (add `--dry-run` first if you want to preview):

```bash
./scripts/install-skills.sh /path/to/your-project
```

This copies `plugins/sdd/{skills,agents,standards,templates,config,hooks}` into `<your-project>/.claude/`, rewrites the plugin's `${CLAUDE_PLUGIN_ROOT}` paths to repo-relative `.claude/` paths, declares the SessionStart hook in `.claude/settings.json`, symlinks `.agents/skills` to `.claude/skills` so Antigravity (`agy`) discovers the skills too (skipped with a warning if `.agents/skills` already exists), and writes a `.claude/sdd/.harness-version` stamp.

**Step 3 — commit the files in your project:**

```bash
cd /path/to/your-project
git add .claude/
git commit -m "chore: install sdd harness"
```

**Step 4 — open Claude Code in your project and run `/sdd-init`.** Then `/ship <feature>` to start the pipeline.

**To update later:** `git pull` in your harness checkout, re-run `./scripts/install-skills.sh /path/to/your-project`, and commit. The re-run overwrites harness files in place but does **not** delete skills/agents/standards that were removed in a newer harness version — delete any stale ones manually. Compare `.claude/sdd/.harness-version` against this repo's plugin version to see whether you are behind.

---

### GitHub marketplace

Each session fetches the plugin from GitHub, so you always track the latest harness — but that fetch is an install step that can silently skip on a fresh claude.ai/code or CI VM. Prefer [flat copy](#flat-copy-recommended) if reliability there matters. No checkout of this repo is needed; you only edit one file.

**Prerequisites:** Claude Code with plugin support. The repository is public, so no GitHub token is needed to fetch it.

**Step 1 — add two keys to your project's `.claude/settings.json`** (create the file if it does not exist), then commit it so every teammate and CI session inherits the plugin:

```json
{
  "extraKnownMarketplaces": {
    "sdd-harness": {
      "source": { "source": "github", "repo": "zenithml/agent-framework" }
    }
  },
  "enabledPlugins": {
    "sdd@sdd-harness": true,
    "render@sdd-harness": true
  }
}
```

Omit the `render` line for projects with no visual output.

To pin an exact version, add a `ref` to the source — otherwise the repo tracks the default branch and picks up updates automatically:

```json
"source": { "source": "github", "repo": "zenithml/agent-framework", "ref": "v0.2.0" }
```

**Step 2 — open Claude Code in your project and run `/sdd:sdd-init`.** Then `/sdd:ship <feature>` to start the pipeline.

---

### Vendored copy

Commits a frozen copy of the plugin into your repo (under `.claude/vendors/`) and enables it through a *local* marketplace — so it works offline and pins an exact version with no GitHub access at runtime. Like the marketplace method (and unlike flat copy), the skills stay namespaced: `/sdd:ship`, `/sdd:sdd-init`.

**Step 1 — get a checkout of this harness** (anywhere on your machine):

```bash
git clone https://github.com/zenithml/agent-framework.git
cd agent-framework
```

**Step 2 — vendor it into your project** (add `--dry-run` first to preview):

```bash
./scripts/vendor.sh /path/to/your-project
```

The vendor key defaults to your project's directory name. For a project at `/home/alice/my-repo`, the script copies the plugin into `<your-project>/.claude/vendors/my-repo/` and updates `<your-project>/.claude/settings.json` to register that local marketplace and enable `sdd@my-repo`.

**Step 3 — commit the files in your project:**

```bash
cd /path/to/your-project
git add .claude/
git commit -m "chore: vendor sdd plugin"
```

**Step 4 — open Claude Code in your project and run `/sdd:sdd-init`.** Then `/sdd:ship <feature>` to start the pipeline.

**To update later:** `git pull` in your harness checkout and re-run `./scripts/vendor.sh /path/to/your-project` — it is idempotent and overwrites the previous copy.

---

### What `sdd-init` sets up

The `sdd-init` skill detects your tech stack from `package.json`, `pyproject.toml`, and `setup.py` (including monorepo layouts), shows you the resulting config for confirmation, writes `.claude/sdd/config.json`, and commits the following docs scaffold:

```
AGENTS.md                              — routing map: standards + skill routing table
docs/
  INDEX.md                             — master index (Standards section pre-populated)
  standards/
    branching/design.md                — branch topology, naming rules, commit conventions
    code-style/design.md               — linting tools and coding conventions
  specs/<domain>/                      — created by /sdd:ship as features are developed
  decisions/                           — architectural decision records (empty, ready to use)
```

**Standards are stubs to grow into.** `sdd-init` fills in what it can detect — topology (GitHub Flow by default, Gitflow when a development branch exists), branch names, and linting tools (ruff, ESLint, Prettier). The team then adds project-specific rules: type annotation policy, component conventions, performance budgets, and so on.

Standards contain rules in plain language for both humans and agents. They do not contain implementation commands — those live in skills, which read `.claude/sdd/config.json` for the real toolchain specifics.

Templates for requirements, design, tasks, and ADRs ship with the harness (at `.claude/templates/docs/` for a flat install, or `${CLAUDE_PLUGIN_ROOT}/templates/docs/` for the plugin methods) and are used automatically by the pipeline.

### Manual config (reference)

`sdd-init` covers the common case. If you need to write `.claude/sdd/config.json` by hand — for CI-only setup or an unusual toolchain — the full schema is at `plugins/sdd/config/config.schema.json`. Example configs:

- `plugins/sdd/config/config.example.npm.json` — React / Node
- `plugins/sdd/config/config.example.python.json` — Python / FastAPI

Every field is optional. Skills auto-detect commands from manifests and default branches to `main` when the file is absent.

#### How placeholders resolve

Skills use placeholders that map to config keys:

| Placeholder | Config key |
|---|---|
| `<INSTALL_CMD>` | `commands.install` |
| `<TEST_CMD>` / `<TEST_CMD> <test-file>` | `commands.test` / `commands.testOne` |
| `<LINT_CMD>` · `<BUILD_CMD>` | `commands.lint` · `commands.build` |
| `<DEV_CMD>` · `<DEV_HOST_CMD>` | `commands.dev` · `commands.devHost` |
| `<SHOOT_CMD>` | `commands.shoot` |
| `<SOURCE_DIR>` | `source.dir` |
| `<MAIN_BRANCH>` · `<DEV_BRANCH>` | `branching.mainBranch` · `branching.devBranch` |
| `<feature-branch>` | `branching.featurePrefix` + `<domain>` |

### (Optional) SessionStart hook for web/CI

The plugin ships a `SessionStart` hook (`hooks/hooks.json`) that runs automatically in **remote sessions** (claude.ai/code and CI). It installs dependencies and runs the test suite, driven by `.claude/sdd/config.json`. It also wires up the `gh` CLI if a `GITHUB_PERSONAL_ACCESS_TOKEN` environment variable is present (set this in your claude.ai project secrets or CI environment). It is a no-op in local Claude Code sessions, so it is safe to leave enabled always.

Plugin hooks load automatically once the plugin is enabled — no additional wiring required.

## Branching topologies

Three topologies are supported:

| Topology | `devBranch` config | When to use |
|---|---|---|
| **GitHub Flow** (default) | equals `mainBranch` (the schema default) | PRs as the integration gate; `main` always deployable and deploying on merge. Most web / SaaS projects. |
| **Trunk-based** | equals `mainBranch` | Very short-lived branches (hours to a day or two); feature flags for incomplete work; emphasis on CI over PR review. High-cadence teams. |
| **Gitflow** | distinct from `mainBranch` (e.g. `development`) | Explicit integration branch; `main` is production-only. Useful when release cadence is slower or the team wants a staging gate. |

GitHub Flow and trunk-based share the same config shape — both set `devBranch == mainBranch`. The distinction is a team convention captured in `docs/standards/branching/design.md` (written by `sdd-init`) rather than in `.claude/sdd/config.json`. When no separate development branch is detected, `sdd-init` proposes GitHub Flow and offers trunk-based as the alternative.

See `plugins/sdd/standards/branching-model.md` for how skills implement each topology.

## Development

This repo is both the plugin and its marketplace. To test local changes, point a consuming repo's `.claude/settings.json` at your local checkout instead of GitHub:

```json
{
  "extraKnownMarketplaces": {
    "sdd-harness": {
      "source": { "source": "directory", "path": "/path/to/agent-framework" }
    }
  },
  "enabledPlugins": {
    "sdd@sdd-harness": true
  }
}
```

Changes to a local checkout are picked up on the next session start — no reinstall needed.

## License and security

Licensed under the [Apache License 2.0](LICENSE). Contributions are accepted under the same license — see [`CONTRIBUTING.md`](CONTRIBUTING.md). To report a vulnerability, follow [`SECURITY.md`](SECURITY.md) rather than opening a public issue.

> **Warning:** Do not add a directory marketplace to your global `~/.claude/settings.json` unless you intend all local repositories to resolve `sdd-harness` to that path. Prefer the GitHub marketplace source for everyday use.

Run `/sdd:lint-harness` after editing any skill to catch the known agent-instruction anti-patterns documented in `plugins/sdd/standards/harness.md`.
