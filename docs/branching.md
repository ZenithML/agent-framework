# Branching

The git and PR skills support three topologies. **GitHub Flow is the default.**

| Topology | `devBranch` config | When to use |
|---|---|---|
| **GitHub Flow** (default) | equals `mainBranch` (the schema default) | PRs as the integration gate; `main` always deployable and deploying on merge. Most web / SaaS projects. |
| **Trunk-based** | equals `mainBranch` | Very short-lived branches (hours to a day or two); feature flags for incomplete work; emphasis on CI over PR review. High-cadence teams. |
| **Gitflow** | distinct from `mainBranch` (e.g. `development`) | Explicit integration branch; `main` is production-only. Useful when release cadence is slower or the team wants a staging gate. |

GitHub Flow and trunk-based share the same config shape: both set `devBranch == mainBranch`. The
difference is a team convention, recorded in your `docs/standards/branching/design.md` (written
by `sdd-init`) rather than in `.claude/sdd/config.json`.

`sdd-init` picks the topology from your remote branches:
- If a `development`, `develop` or `dev` branch exists, it sets up Gitflow.
- Otherwise it proposes GitHub Flow and offers trunk-based as the alternative.

How the skills implement each topology (base-branch selection, merging before a PR, hard
prohibitions) is in
[`plugins/sdd/standards/branching-model.md`](../plugins/sdd/standards/branching-model.md).
