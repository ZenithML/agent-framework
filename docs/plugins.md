# Plugins

This repository ships three Claude Code plugins. `.claude-plugin/marketplace.json` at the repo
root lists them all, so **the repository is itself the marketplace** (`sdd-harness`).

## sdd: the spec-driven pipeline

**spec → plan → implement → QA → publish**, with critic gates built into each stage and a TDD
loop for implementation.

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

| Pipeline | Git / PR | Maintenance |
|---|---|---|
| `ship` (entry point) | `create-pr` | `sdd-init` (onboarding) |
| `spec` · `plan` · `tasks` | `fix-pr` | `audit` |
| `implement` · `critique` · `qa` | `review-pr` | `lint-harness` |
| `publish` · `prepare-docs` | `branching-model` | `test` |
| `architect` (internal) | | |

> Repository-specific release skills and release/CI-automation layers (tag-release,
> prepare-release, back-merge, version bumping) are **intentionally excluded**. They are too
> tied to each repository's GitHub Actions workflows, so each consuming repo owns its release
> workflow.

How the stages hand off to each other is in
[`plugins/sdd/standards/agent-pipeline.md`](../plugins/sdd/standards/agent-pipeline.md). The
rules for writing skills and agents are in
[`plugins/sdd/standards/harness.md`](../plugins/sdd/standards/harness.md).

## render: verification for perceptual work

For domains where a failure is something you *see* rather than something that throws.

```
plugins/render/
  .claude-plugin/plugin.json   — plugin manifest
  skills/<name>/SKILL.md        — 4 slash commands (invoked as /render:<name>)
  standards/                    — agent-graphics, verification
```

An agent working on a visual domain with no way to see its output is guessing, and the human
becomes the only sensor in the system. This plugin is the method for fixing that. It gives the
agent a **capture endpoint**, a **named observation set**, **numeric proxies** cheap enough to
gate CI, and a **symptom-keyed traps table**.

| Skill | Does |
|---|---|
| `/render:render-init` | Build the apparatus: determinism, capture, the named set, budgets. Run once, **before** any perceptual work |
| `/render:frames` | Re-shoot the set, read every image, report against the look contract |
| `/render:tune` | Change one theme value against the set: baseline, vary, compare, keep the winner with the frames as evidence |
| `/render:trap` | Record a bug that threw nothing, keyed by its symptom, in the same change that fixes it |

It also carries the **harness / engine / theme** layering rule and its three falsifiable
boundary tests: swap, transplant, and a grep for colour literals in the engine. See
[`plugins/render/standards/agent-graphics.md`](../plugins/render/standards/agent-graphics.md).

> The plugin ships no rendering code. It is prose: the method, not the engine. An engine is a
> per-project or per-org package, because it has a different consumer and a different release
> cadence. A plugin that pulled in a 3D library would be a plugin nobody can install.

## ci-runner: GitHub Actions on your own machine

A shell command first and a plugin second, so it works without Claude Code: `ci-runner`
registers a self-hosted runner for a repository (or an organization) as a systemd service on
Linux or a launchd agent on macOS, writes a `select-runner.yml` reusable workflow, and flips
repository variables to send jobs to the runner, back to GitHub-hosted, or to the runner only
while it is online. Generalised from ZenithML/zenith's `self-hosted-runner/` scripts.

```
plugins/ci-runner/
  .claude-plugin/plugin.json   — plugin manifest
  bin/ci-runner                 — the command (bash 3.2 safe)
  install.sh                    — links bin/ci-runner into ~/.local/bin
  templates/select-runner.yml   — the reusable workflow `ci-runner workflow` writes
  skills/setup/SKILL.md         — /ci-runner:setup, the order to run it in
```

| Skill | Does |
|---|---|
| `/ci-runner:setup` | Install the runner under a dedicated account, wire the workflows, then switch |

Self-hosted runners are for private repositories only, and should run under a dedicated
account. The plugin's [README](../plugins/ci-runner/README.md) covers both, the commands and
how to make jobs safe to run there.
