# Review triage — Tasks

**Source:** [requirements.md](requirements.md) | [design.md](design.md)
**Last Updated:** 2026-10-20

Per-task issues are not used for this domain; the PR links the spec.

## Tasks

- [x] 1. Triage script: `plugins/sdd/skills/triage-pr/scripts/triage.py` — diff parser, rules loader, low/focus rules, tiering and ordering, markdown and JSON renderers, CLI and exit codes; tests `tests/triage-pr/test_triage.py` with fixtures and the runner `tests/triage-pr.sh` (T1–T15)
- [x] 2. Skill and release: `plugins/sdd/skills/triage-pr/SKILL.md` (strict frontmatter, configuration preamble, skill flow, promote-only rule, `--comment` upsert, file manifest), `evaluations/baseline-evals.json`; `harness-config.json` (`strict_skills`, `evals_required`, `manifest_skills`); one-line pointer in `review-pr`; `docs/plugins.md`, AGENTS.md routing, review standard, lint-harness skill list, `docs/INDEX.md`; `tests/triage-pr.sh` in the `gates` CI job; sdd version 0.10.0 in both manifests
