# Branching — Standard

**Status:** Accepted

This standard defines the branching model and commit conventions for the `agent-framework` repository.

For the general SDD plugin branching rules (topology options, base-branch selection, merge workflow), see [`plugins/sdd/standards/branching-model.md`](../../../plugins/sdd/standards/branching-model.md). This document records the choices made for *this* repo specifically.

---

## Topology

GitHub Flow. `main` is the single long-lived branch — always deployable, merging a PR triggers a release. There is no separate `development` branch. Feature branches are cut from `main` and can live for days until the PR is merged.

`.claude/sdd/config.json` reflects this: `mainBranch` and `devBranch` are both `main`.

---

## Branch Naming

| Prefix | Used by | Purpose |
|---|---|---|
| `claude/<task-slug>` | Claude Code agents | Agent-authored feature work. Slug format: `<short-description>-<random-id>` (e.g. `claude/sdd-branching-standard-SPrdx`). |
| `feature/<name>` | Human contributors | Human-authored feature work. |
| `hotfix/<name>` | Anyone | Critical fixes that must bypass the normal feature cycle. PRs into `main` directly. |
| `release/v<version>` | Anyone | Version bump only — no feature work. PRs into `main` directly. |

All branches are cut from `origin/main` and target `main` as the base branch (except `hotfix/` which also targets `main`).

---

## Commit Messages

Use [Conventional Commits](https://www.conventionalcommits.org/) prefixes:

| Prefix | When to use |
|---|---|
| `feat:` | New skill, agent, standard, or template |
| `fix:` | Correcting a bug in an existing skill, agent, or standard |
| `docs:` | README, CONTRIBUTING, or AGENTS.md changes |
| `chore:` | Config, tooling, or non-functional maintenance |
| `refactor:` | Restructuring without behaviour change |
| `release:` | Version bump commits (see [release standard](../release/design.md)) |

---

## Hard Prohibitions

- **No direct pushes to `main`.** All changes arrive via PR.
- **No `--no-verify` merges.** Fix hooks; don't bypass them.
- **No force-pushing to `main`.**
