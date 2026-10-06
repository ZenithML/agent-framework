---
name: critique
description: >
  Use when one already-written artifact needs an adversarial second opinion on demand —
  requirements, design, or the code from a finished task — returning PASS or REVISE. Does not
  trigger during /sdd:spec or /sdd:plan, where critic review is already embedded, and does not
  trigger to fix what it finds.
---

**Usage:** `/sdd:critique <context> <domain>`

- `context`: `requirements` · `design` · `code`
- `domain`: the domain being reviewed

Spawn the `critic` agent with the appropriate artifacts and criteria:

| Context | Artifacts passed |
|---|---|
| `requirements` | `requirements.md` |
| `design` | `requirements.md` + `design.md` |
| `code` | Changed source files + Architecture + Test Scenarios sections of `design.md` |

The critic is **read-only** and returns a structured PASS/REVISE handoff. It never modifies files.

> In the pipeline, critic review is embedded within `/spec` (requirements) and `/plan` (design). Code critique after each executor task is managed by the architect. Run `/critique` manually to re-check a specific artifact.

See `${CLAUDE_PLUGIN_ROOT}/agents/critic.md` for the full review spec.
