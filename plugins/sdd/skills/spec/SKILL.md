---
name: spec
description: >
  Use when a named domain needs its requirements.md written or revised — user stories,
  acceptance criteria and Given/When/Then scenarios, with critic review looped in until it
  passes. Does not trigger during a /sdd:ship run, which invokes the planner directly, and does
  not trigger for design or task breakdown (that is /sdd:plan).
---

**Usage:** `/sdd:spec <domain> [--autonomous]`

Spawn the `planner` agent with `--spec-only` and the domain name.

The planner will:
1. Read existing state in `docs/specs/<domain>/` and `docs/INDEX.md`
2. Create or update `requirements.md`
3. Spawn the `critic` agent to review requirements (completeness, Given/When/Then, no ambiguity)
4. On REVISE: apply feedback and re-run critic (max 2 cycles)
5. On PASS: in interactive mode, surface to user for final approval before exiting

Exits with a critic-verified `requirements.md`. Run `/plan <domain>` next to produce design.md and tasks.md.

> Called automatically by `/ship` as Stage 1. Run manually when you only need to define or update requirements.

See `${CLAUDE_PLUGIN_ROOT}/agents/planner.md` for the full planning spec.
