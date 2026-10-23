---
name: audit
description: >
  Use when project documentation should be checked for structural completeness and template
  conformance on demand, across all domains or one named domain, reporting gaps without
  repairing them. Does not trigger as part of a pull-request flow (that is /sdd:prepare-docs),
  and does not check skills or agents (that is /sdd:lint-harness).
---

Before delegating, Read `${CLAUDE_PLUGIN_ROOT}/agents/archivist.md` in full. In Codex, pass
that exact canonical role definition and only this stage's scoped inputs to a fresh native
subagent; do not assume a registered custom role. Read and apply the Cross-harness delegation
contract in `${CLAUDE_PLUGIN_ROOT}/standards/agent-pipeline.md`.

**Usage:** `/sdd:audit` or `/sdd:audit <domain>`

Spawn the `archivist` agent to check documentation health against `${CLAUDE_PLUGIN_ROOT}/standards/doc-structure.md`.

- No argument: audits all domains
- With `<domain>`: audits only that domain

## What it checks

| Check | Description |
|---|---|
| INDEX.md ↔ disk | Every domain in INDEX.md has a directory, and vice versa |
| Spec completeness | Each domain has requirements.md, design.md, and tasks.md |
| Template conformance | All required sections are present in each spec file |
| No unresolved decisions | design.md Decisions table has no TBD rows |
| Task / issue linkage | Completed tasks `[x]` reference a GitHub issue `(#N)` when the project uses per-task issues |
| Status consistency | INDEX.md status matches actual task completion in tasks.md |
| ADR index sync | Every file in the ADR directory (`docs.adrDir`, default `<docs.root>/decisions/`) appears in the INDEX.md ADR table |
| README structure | README.md exists and has required sections |

The archivist is **read-only** — it reports issues but does not fix them.

See `${CLAUDE_PLUGIN_ROOT}/agents/archivist.md` for the full audit spec.
