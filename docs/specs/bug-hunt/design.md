# Bug Hunt — Design

**Status:** Approved
**Last Updated:** 2026-10-28

Source: [requirements.md](requirements.md).

## Decision

**One orchestrating skill over two existing roles.** The static audit is a new `bugs` context
on the read-only `critic`; the runtime pass and the fixes reuse `qa-engineer` (`--report-only`
and a new `--fix-list` mode that skips exploring). No new role, so no new tool contract.

### Alternatives considered

- *A new `bug-hunter` role.* Rejected: it would duplicate the critic's read-only audit and the
  qa-engineer's red → green → revert proof, and drift from both.
- *Fix through the `executor`.* Rejected: the executor implements a planned task from tasks.md;
  bug fixes here have no task and need the qa-engineer's reproduction step.

## Architecture

| Component | Path | Responsibility |
|---|---|---|
| Skill | `plugins/sdd/skills/bug-hunt/SKILL.md` | Resolve the area, run both passes, triage, gate, fix, critic check, PR |
| Evals | `plugins/sdd/skills/bug-hunt/evaluations/baseline-evals.json` | Full run, report-only gate, fixing without approval or a test |
| Critic | `plugins/sdd/agents/critic.md` | New `bugs` context: findings as `<file>:<lines> \| <category> \| <P0-P3> \| <root cause>` |
| QA engineer | `plugins/sdd/agents/qa-engineer.md` | New `--fix-list` mode: run step 6 for listed bugs only |
| Gate config | `scripts/checks/harness-config.json` | `bug-hunt` in `strict_skills` and `evals_required` |

## Test Scenarios

- `tests/test_bug_hunt.py`: usage line, reuse of critic and qa-engineer (no new role file), the
  critic's `bugs` context with its read-only tools, `--fix-list` in qa-engineer, gate/report/PR
  wording, no consumer-specific strings, strict frontmatter and three evals.

## QA Scenarios

- A fresh flat install places `.claude/skills/bug-hunt` and `.agents/skills/bug-hunt`, with
  `/sdd:` rewritten (`tests/install-paths.sh`).
