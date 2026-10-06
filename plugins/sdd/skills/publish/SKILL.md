---
name: publish
description: >
  Use when a domain's tasks are complete and it should be taken to an open pull request — docs
  verified, description drafted from the specs, PR opened, CI watched. Does not trigger during a
  /sdd:ship run, which spawns the publisher, does not trigger with tasks still outstanding, and
  does not merge anything.
---

**Usage:** `/sdd:publish <domain>`

Spawns the `publisher` agent with the domain name and domain path (`docs/specs/<domain>/`).

The publisher owns the full shipping sequence:
1. Runs `/prepare-docs <domain>` — verifies tasks, updates INDEX.md, audits and commits docs checkpoint
2. Reads specs and drafts the PR description (summary, changes, `Closes #N`, test plan)
3. Runs `/create-pr` with the drafted description
4. Monitors CI — routes code failures back to executor, retries infra flakes once

> Called automatically by `/ship` as the final stage. Run manually when working outside the pipeline or resuming after a failure.

See `${CLAUDE_PLUGIN_ROOT}/agents/publisher.md` for the full publishing spec.
