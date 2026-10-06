# Branching Model — Standard

This standard defines the branch topology the SDD plugin's git/PR skills assume. It is **configurable**: the concrete branch names come from `.claude/sdd/config.json` (`branching.mainBranch`, `branching.devBranch`, `branching.featurePrefix`), so the same skills work for GitHub Flow, trunk-based and Gitflow-style repos. **GitHub Flow is the default.**

Throughout this document, `<MAIN_BRANCH>` and `<DEV_BRANCH>` refer to those configured values.

## Three supported topologies

| Topology | Config | Behaviour |
|---|---|---|
| **GitHub Flow** (default) | `mainBranch == devBranch` (e.g. both `main`) — the schema default | Feature branches cut from `main`, merged back via PR. `main` is always deployable; merging triggers deployment. PRs are the primary integration gate and may stay open for review/discussion. |
| **Trunk-based** | `mainBranch == devBranch` (e.g. both `main`) — convention only | Very short-lived feature branches (hours to a day or two). Incomplete work is hidden behind feature flags. Emphasis on continuous integration over PR review gates. |
| **Gitflow-style** | `devBranch` distinct from `mainBranch` (e.g. `development` + `main`) | Features branch from and PR into `<DEV_BRANCH>`; `<MAIN_BRANCH>` is the production/release branch. |

Trunk-based and GitHub Flow share the same config shape (`mainBranch == devBranch`). The distinction is a team convention captured in `docs/standards/branching/design.md`, not in `.claude/sdd/config.json`.

If `.claude/sdd/config.json` is absent, skills default to GitHub Flow with `main` (and only use a separate `development` branch if one exists on the remote). Because `devBranch` defaults to `main` in the schema, a config that omits it is also GitHub Flow on `main`; Gitflow repos must set `devBranch` explicitly.

## Starting a feature

```bash
git fetch origin
git checkout -b <feature-branch> origin/<DEV_BRANCH>
```

`<feature-branch>` is `branching.featurePrefix` + the domain name (default `feature/<domain>`). Feature branches are always cut from `<DEV_BRANCH>`.

## Before opening a PR

Merge the target (base) branch into your branch and resolve conflicts locally:

```bash
git fetch origin
git merge origin/<DEV_BRANCH>     # base is usually the dev branch
```

Push only after the merge is clean. The goal is a PR diff that reflects your change only, not a mix of your change and conflict resolutions.

## Base-branch selection

| Branch prefix | Base branch |
|---|---|
| `featurePrefix` (e.g. `feature/`) | `<DEV_BRANCH>` |
| `hotfix/` | `<MAIN_BRANCH>` |
| anything else | `<DEV_BRANCH>` |

## Commit messages

Use Conventional Commits prefixes (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`, `ci:`). Using them consistently keeps history readable and makes changelog generation possible if the project chooses to add it.

## Hard prohibitions

- **Do not push directly to `<MAIN_BRANCH>` or `<DEV_BRANCH>`.** Both are PR-only.
- **Do not merge with `--no-verify`.** If a hook fails, fix the underlying issue.

> Release/versioning automation (tagging, back-merge, changelog) is **out of scope** for this plugin — it is too project-specific. Each consuming repo owns its own release workflow.
