---
name: qa
description: >
  Use when one task's observable behaviour should be exercised against the QA Scenarios in
  design.md, through the running application rather than the source. Does not trigger during a
  /sdd:ship run, which spawns the tester per task, does not trigger for unit tests (that is
  /sdd:test), and never reads implementation code.
---

**Usage:** `/sdd:qa <domain> <task-id>`

Spawn the `tester` agent with the domain, task ID, and required context.

Before spawning, read and pass only:
- The QA Scenarios section of `docs/specs/<domain>/design.md`
- The Acceptance Criteria section of `docs/specs/<domain>/requirements.md`
- The specific QA scenario to test

The tester agent runs as an isolated subprocess (Bash + Playwright MCP — no Write/Edit) and:
1. Detects the environment (local vs GitHub cloud agent)
2. Starts the dev server and tests observable behavior
3. Tests edge cases from design.md
4. Outputs a PASS/FAIL report with actionable behavioral feedback

**The tester never reads source code.**

> Called automatically by `/ship` after each implement + critique cycle. Run manually to re-check a specific QA scenario.

See `${CLAUDE_PLUGIN_ROOT}/agents/tester.md` for the full QA spec.
