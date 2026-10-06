# Release — Standard

**Status:** Accepted

This standard defines the release process for the `agent-framework` plugin. All versions follow [Semantic Versioning](https://semver.org/).

---

## How releases work

Every merge to `main` is a production release. CI (`.github/workflows/release.yml`) reads the version from `plugins/sdd/.claude-plugin/plugin.json` on each push to `main`. If the tag does not yet exist, it creates the git tag and a GitHub Release automatically. If the tag already exists (no version bump in the PR), CI skips — no duplicate releases.

The developer's only responsibility is to bump the version as part of the feature PR.

---

## Version Files

Each plugin's manifest and its own listing in `marketplace.json` must be kept in
sync — update the sdd plugin's pair in the same commit:

| File | Key |
|---|---|
| `plugins/sdd/.claude-plugin/plugin.json` | `"version"` |
| `.claude-plugin/marketplace.json` | top-level `"version"` and the `sdd` entry in `plugins[]` |

A second plugin (e.g. `plugins/render/`) versions independently: its own
`plugin.json` `"version"` must match only its own entry in `plugins[]`, never
sdd's. A PR that changes a plugin without bumping its version, or that lets a
`plugins[]` entry drift from its own manifest, is invalid and must not be
merged.

---

## Version Increment Rules

| Change | Version component |
|---|---|
| New skill, agent, or template added | `MINOR` |
| Existing skill or agent behaviour changed | `MINOR` |
| Bug fix in a skill, agent, or standard | `PATCH` |
| Breaking change to `.claude/sdd/config.json` schema | `MAJOR` |
| Docs-only or tooling-only change | No bump required |

---

## Release Steps

1. **Decide the new version** using the increment rules above.
2. **Bump both version files** listed above, run `./scripts/check-all.sh`, commit as `release: v<version>`, and open a PR to `main`.
3. **Merge the PR.** CI creates the git tag and publishes the GitHub Release with generated notes automatically.

---

## Consumer Impact

Consumers pinning a `"ref": "v<version>"` in their marketplace config are unaffected by new releases until they update the ref. Consumers without a `ref` track `main` and pick up changes automatically at next session start.

---

## Rules

- Never push tags manually — CI owns tagging.
- Never create a GitHub Release manually — CI owns releases.
- Both version files must be in sync before merging.
