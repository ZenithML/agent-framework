# AGENTS.md

This repository is the **SDD plugin and its marketplace**. It ships a spec-driven
development pipeline as a reusable Claude Code plugin (`plugins/sdd/`).

This is the single source of truth for rules and routing in this repository.
There is no `CLAUDE.md` — Claude Code falls back to this file when it is absent.

## Always-on rules

- All changes arrive via PR — no direct pushes to `main`
- Run `./scripts/check-all.sh` before marking any PR ready for review — CI runs the same
  command. `/lint-harness` is the judgment half, for step-delegation and rule drift
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
| Create / update a plugin spec | `/spec` |
| Design a change | `/plan` |
| Open a pull request | `/create-pr` |
| Respond to PR review feedback | `/fix-pr` |
| Review a pull request | `/review-pr` |
| Review the local change before it goes public (findings to `.review/findings.json`) | `/review-diff` |
| Triage a large PR — which parts need a human, which can be skipped | `/triage-pr` |
| Lint skills / agents / standards (judgment half) | `/lint-harness` |
| Run every mechanical gate before marking an MR ready | `./scripts/check-all.sh` (and `./tests/run-fixtures.sh`, and `./tests/install-paths.sh` when installers or manifests change, and `./tests/ci-runner.sh` when `plugins/ci-runner/` changes, and `./tests/triage-pr.sh` when `plugins/sdd/skills/triage-pr/` changes) |
| Hold one more skill to the strict authoring schema | Add its name to [`scripts/checks/harness-config.json`](scripts/checks/harness-config.json); removals are refused |
| Audit docs | `/audit` |
| Install or update consumers, including Codex discovery and shared roles | [Installation](docs/installation.md) |

## Coding-agent discovery

In this source checkout, `.claude/skills` and `.agents/skills` both link to
`plugins/sdd/skills`; `.claude/agents` links to `plugins/sdd/agents`. Launch either client
from this root. Claude discovers `/ship`, `/spec`, etc. as project skills and registers the
canonical roles; Codex uses `$ship` or `/skills` and native role delegation. No SDD plugin
installation is required to work on this repository.

In standalone source skills, `${CLAUDE_PLUGIN_ROOT}` denotes the repository's `plugins/sdd`
directory. Resolve it as a path before running shell commands; it is not an exported shell
variable. Plugin examples using `/sdd:<skill>` mean `/<skill>` in this checkout. Consumer
flat installs instead link `.agents/skills` to `.claude/skills`. See
[the delegation contract](plugins/sdd/standards/agent-pipeline.md#cross-harness-delegation)
for full-role native delegation, isolated stage inputs and session-model inheritance.
The source checkout disables `sdd@sdd-harness` at project scope to prevent an older cached
plugin from shadowing or duplicating the local canonical skills. Marketplace and vendored
plugin installations remain supported for consumer repositories. Installation and
authentication are documented in [the installation guide](docs/installation.md).
