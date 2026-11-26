# Flat skill prefix: namespace flat-installed skills — Tasks

**Source:** [requirements.md](requirements.md) | [design.md](design.md)
**Last Updated:** 2026-11-26

## Tasks

- [ ] 1. Fresh install uses flat names: stage rename with `name:` rewrite and `renames.json`, invocation and skill-path rewrite rules (with the plugin-note exception) over skills, agents, standards and `templates/agent-routing.md`, closing hints, `sdd-init` markers and message, `docs/installation.md` and `docs/plugins.md`, sdd 0.20.0 and render 0.3.0 in both manifests. Tests in `tests/install-paths.sh` for Stories 1, 2, 3, 7b, 9, 10.
- [ ] 2. Upgrade migration and legacy warning: the four migrate rules before the sync (manifest keys, edited `SKILL.md` name line, pending upstream copies, `Renamed` lines), and the stderr legacy warning after it. Tests in `tests/install-paths.sh` for Stories 4, 5, 5b, 6, 7, 8 and the matrix rows (interrupted upgrade, no name line, CRLF, symlink, render without the flag).
