# Plugins

This repository ships two Claude Code plugins. `.claude-plugin/marketplace.json` at the repo
root lists both, so **the repository is itself the marketplace** (`sdd-harness`).

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
