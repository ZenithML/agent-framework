# Exploratory QA: play with the running app, find bugs, fix them — Requirements

**Status:** Approved
**Last Updated:** 2026-10-28

Scope: `plugins/sdd` 0.14.0. Adds one skill, `/sdd:qa-explore`, and one agent role,
`qa-engineer`. Generalised from a consumer repository's project-local copy.

## Problem Statement

`/sdd:qa` runs the sealed `tester` against one task's QA Scenarios. It is deliberately blind:
it cannot read source, cannot write, and only reports. That is right inside `/sdd:ship`, where an
independent verdict is the point, but it leaves a gap. Nobody in the harness is asked to *go play
with the app like a human tester*: wander any flow, spec or not, push on it adversarially, and
when something breaks, leave the repository with a regression test and a fix instead of a note
that evaporates.

Consumers fill that gap with project-local copies that hard-code their own routes, credentials,
backends and test file names, so the workflow cannot be shared.

## Goals

- **G1 Explore.** Drive the running application the way a human tester would — a browser
  through Playwright MCP for web apps, the shell for CLI and TUI apps — beyond the happy path.
- **G2 Confirm.** Treat an issue as a bug only after it reproduces twice.
- **G3 Fix with proof.** For each confirmed bug: a failing regression test in the project's
  existing conventions (red, for the right reason), root cause from source, a minimal fix
  (green), proof the test bites (revert the fix, rerun, see it fail), the broader suite, and
  test and fix as separate commits.
- **G4 Report friction honestly.** UX friction that is not a clear bug, and flaky or
  out-of-scope findings, are reported as noted-not-fixed and never changed.
- **G5 Portable.** No project-specific paths, routes, credentials, backends or test files.
  URLs and commands come from `.claude/sdd/config.json`; credentials only from environment
  variables named by the caller or config.
- **G6 Cross-harness.** The skill dispatches with the same delegation preamble as the other
  dispatchers, so it works in Claude Code and Codex.

## Out of Scope

- Replacing `/sdd:qa` or the sealed `tester`. The pipeline's QA stage is unchanged.
- Running inside `/sdd:ship`. `qa-explore` is ad hoc and user-invoked.
- Starting infrastructure the config does not name (databases, containers, backends).
- Product decisions: wording, layout and flow changes are reported, not made.

## User Stories & Acceptance Criteria

### Story 1: Explore any flow

**Given** a configured project and a running web app
**When** the user runs `/sdd:qa-explore "checkout with a discount code"`
**Then** the `qa-engineer` role is dispatched with the flow description, the resolved dev URL
and (when a domain is inferable) that domain's QA Scenarios as optional context, and it probes
empty, malformed and boundary input, rapid repeats, back/refresh/deep links, error states,
console errors, failed network requests and a phone-width layout.

### Story 2: Never stand up infrastructure silently

**Given** the dev URL does not answer
**When** `commands.devHost` is configured
**Then** the agent starts `<DEV_HOST_CMD>` with the Bash tool's `run_in_background` parameter
(not a trailing `&`) and waits for the URL to answer.
**Given** the dev URL does not answer and no `commands.devHost` is configured
**Then** the agent stops and reports what is missing, and changes nothing.

### Story 3: A confirmed bug gets a test, a fix, and proof

**Given** an issue that reproduces twice
**Then** the agent writes a failing regression test using the project's existing test
conventions, confirms it fails for the right reason, reads source to find the root cause,
applies a minimal fix, reruns the test green, stash-reverts the fix and sees the test fail
again, restores the fix, runs `<TEST_CMD>`, and commits the test and the fix separately.

### Story 4: Friction and flakes are noted, not changed

**Given** a confusing label, a missing feedback message or a dead end that is not clearly a bug,
or an issue that does not reproduce
**Then** it is listed under FRICTION NOTED or NOT FIXED (with the reason), and no file changes.

### Story 5: Report only

**Given** `/sdd:qa-explore <flow> --report-only`
**Then** the agent explores and reports, and writes, edits and commits nothing.

### Story 6: Credentials

**Given** the flow needs a signed-in user
**Then** credentials are read only from environment variables named by the caller or by
`devServer.credentialEnv` in config; when none are named or set, the protected area is reported
as not tested. No credential is hard-coded or printed.

### Story 7: Final report

**Then** the session ends with four sections: BUGS FOUND & FIXED, FRICTION NOTED,
NOT FIXED (why), CLEAN.

### Story 8: Distinguishable from `/qa`

**Then** the skill states that `/sdd:qa` is the task-scoped sealed verifier (`tester`, no source
access, report-only), while `/sdd:qa-explore` is ad hoc, covers any flow, reads source and fixes
code; and each description names the other as a non-trigger.

## Constraints

- The `qa-engineer` role needs file reads and writes, so it is an `author`, not a `verifier`;
  the verifier seal on `tester` is unchanged.
- Tier `workhorse`.
- Adding the role and skill is a new capability: sdd MINOR version bump in both manifests.

## References

- [design.md](design.md), [tasks.md](tasks.md)
- [harness.md — agent roles and tool contracts](../../../plugins/sdd/standards/harness.md#agent-roles-and-tool-contracts)
- [agent-pipeline.md — cross-harness delegation](../../../plugins/sdd/standards/agent-pipeline.md#cross-harness-delegation)
