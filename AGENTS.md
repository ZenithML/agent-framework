# AGENTS.md

This repository is the **SDD plugin and its marketplace**. It ships a spec-driven
development pipeline as a reusable Claude Code plugin (`plugins/sdd/`).

This is the single source of truth for rules and routing in this repository.
There is no `CLAUDE.md` — Claude Code falls back to this file when it is absent.

## Always-on rules

- All changes arrive via PR — no direct pushes to `main`
- Run `./scripts/check-all.sh` before marking any PR ready for review — CI runs the same
  command. `/sdd:lint-harness` is the judgment half, for step-delegation and rule drift
- Version bumps are required whenever plugin behaviour changes — see [`docs/standards/release/design.md`](docs/standards/release/design.md)

## Design Docs

| Topic | Authoritative document |
|---|---|
| Branching strategy | [`docs/standards/branching/design.md`](docs/standards/branching/design.md) |
| Release process | [`docs/standards/release/design.md`](docs/standards/release/design.md) |
| PR review process | [`docs/standards/review/design.md`](docs/standards/review/design.md) |
| Doc structure | [`plugins/sdd/standards/doc-structure.md`](plugins/sdd/standards/doc-structure.md) |
| Harness architecture | [`plugins/sdd/standards/harness.md`](plugins/sdd/standards/harness.md) |
| SDD pipeline | [`plugins/sdd/standards/agent-pipeline.md`](plugins/sdd/standards/agent-pipeline.md) |
| Agent roles and tool contracts | [`plugins/sdd/standards/harness.md`](plugins/sdd/standards/harness.md) |

## Skill Routing

| Task | Skill |
|---|---|
| Create / update a plugin spec | `/sdd:spec` |
| Design a change | `/sdd:plan` |
| Open a pull request | `/sdd:create-pr` |
| Respond to PR review feedback | `/sdd:fix-pr` |
| Review a pull request | `/sdd:review-pr` |
| Lint skills / agents / standards (judgment half) | `/sdd:lint-harness` |
| Run every mechanical gate before marking an MR ready | `./scripts/check-all.sh` (and `./tests/run-fixtures.sh`, and `./tests/install-paths.sh` when installers or manifests change) |
| Hold one more skill to the strict authoring schema | Add its name to [`scripts/checks/harness-config.json`](scripts/checks/harness-config.json); removals are refused |
| Audit docs | `/sdd:audit` |
