# Agent Pipeline — Reference

This document describes the agent-driven development workflow the SDD plugin provides. It is the reference for anyone (human or AI) working on or extending the pipeline.

## Cross-harness delegation

Canonical role instructions live only in `agents/<agent-name>.md` under the plugin root
(or `.claude/agents/` in a flat consumer install). Discovery through `.agents/skills` is
a symlink to the canonical skills; there are no Codex role copies or generated agents.

Before every role invocation, including nested reviews and direct architect resumption:

1. Read the canonical role Markdown in full, including its frontmatter, tool contract,
   constraints and handoff schema. Read the scoped inputs required for the current stage.
2. In Claude Code, invoke the existing registered role using the Agent/Task mechanism;
   resolve the target role model as specified below, preserving its declared capabilities.
3. In Codex, start a native generic subagent. Pass the exact full role instructions as its
   task instructions, followed by only the scoped stage context and invocation arguments.
   Do not use a role summary, infer a custom agent registration, duplicate the role in
   another file, or inherit the caller's full conversation. The native subagent must have
   a fresh context containing just the role definition and permitted stage inputs.
4. Map Claude tool names to native equivalents (file reads/patches, shell commands, searches,
   browser tools and subagent spawning). Resolve the target role model as specified below;
   never send Claude model labels to Codex. Preserve role prohibitions and handoff
   formats while using those native tools. If native delegation is unavailable, report the
   limitation; do not substitute a self-review for an independent critic or tester.

### Provider model resolution

Each canonical role declares a semantic `tier` (`frontier`, `workhorse` or `fast`).
The shared model tier catalog at `${CLAUDE_PLUGIN_ROOT}/config/model-tiers.json` is the source of default model
IDs for all providers. In a flat install it lives at `.claude/sdd/model-tiers.json`.

| Tier | Roles |
|---|---|
| frontier | (none shipped; available for a consumer to move a role up) |
| workhorse | architect, planner, critic, archivist, publisher, qa-engineer |
| fast | executor, tester |

Before every invocation, the caller reads the catalog and identifies the active host
provider from the session (`openai` in Codex, `anthropic` in Claude Code). Resolution is:

1. Require a readable JSON catalog containing the target role's valid tier. A missing or
   malformed catalog, missing/invalid tier, or unknown provider selects `inherit`.
2. If the target role declares `provider_defaults.<provider>`, use that explicit override.
   An absent provider key falls through to the catalog's `<tier>.<provider>` entry.
3. Require a non-empty string model ID that the host confirms as supported, accessible and
   active. Missing mappings, malformed overrides, unsupported/deprecated models or
   unverifiable support select `inherit` (the parent session model). An explicit invalid
   or unsupported override does not silently fall through to a different default.

Roles normally contain no `provider_defaults`; consumers may add a partial mapping when
one role needs a provider-specific exception, for example:

```yaml
tier: workhorse
provider_defaults:
  openai: <host-supported-model-id>
```

The legacy `model` field remains a static Claude compatibility value. It equals the
resolved Anthropic default (the role override when present, otherwise the tier catalog
entry). Callers implementing this contract resolve from the catalog and optional override;
`model` is not a fallback source. Changing an Anthropic default also requires updating
any affected legacy `model` fields; tests enforce that alignment for shipped roles.
There is no cross-provider name translation or substitution with another tier.

For Codex native spawning, the resolved supported ID is the `model` argument, with
fresh context (for example `fork_turns="none"` where exposed). For inheritance, omit
`model` rather than passing the literal `inherit` to a host that does not accept it.
If a spawn rejects an override as unavailable, unsupported or deprecated, retry once
with the same role and scoped inputs and no override; other errors retain their normal
failure handling. This applies to direct skill dispatch and every nested invocation.
Callers log the role, tier, provider, selected model and any fallback reason.

### Antigravity model selectors

The catalog's Google defaults (or a role's `provider_defaults.google` override) contain
concrete agy CLI IDs, checked against `agy models`.
The agy CLI's `--model` does not accept `pro`.

Antigravity's in-process `invoke_subagent` has a different interface: its `Model` enum
accepts `pro`, `flash`, `flash_lite` and `inherit`; `pro` routes to Argon on the backend.
For that tool only, adapt the supported Google catalog choice to its native selector:
Argon high/medium → `pro`, Flash high → `flash`. Use `inherit` when the current schema
cannot represent the selected model or support cannot be confirmed. The high/medium
variant is not expressible through this enum; the native tool controls that choice.
Do not pass CLI IDs to this enum or enum selectors to `agy --model`.
This is host-interface adaptation within Google, never cross-provider model translation.

Anthropic defaults retain Claude Code's supported `opus`, `sonnet` and `haiku` aliases,
matching the legacy `model` fields without pinning retired versioned IDs.
Host capability checks remain authoritative as provider catalogs change.

Codex role restrictions are advisory instructions, including read-only review and the
verifier's prohibition on source inspection. No per-role sandbox or tool allowlist is
installed by this harness. The Claude enforcement claims below apply to Claude Code only.

---

## Philosophy

- **`/sdd:ship` is the single entry point** for all code changes — feature, fix, or refactor.
- **Spec-driven development (SDD) is middleware**, not an entry point. Every stage reads existing specs and keeps them up to date.
- **Critics are embedded in planning.** The planner self-verifies requirements and design before handing off.
- **Test-driven development (TDD) is embedded** in the implement stage — red → green → refactor in one agent invocation.
- **Code critique runs after every implement task**, before QA. The orchestrator manages this loop.
- **One runbook, two orchestrators.** [ship-runbook.md](ship-runbook.md) is the procedure. By default the session that ran `/sdd:ship` follows it (`inline`); with `--architect` or `pipeline.orchestrator: "architect"`, an `architect` subagent follows it in its own git worktree, so several missions can be started from one session.
- **Context isolation** between stages: no stage receives another stage's internals.

---

## Pipeline stages

```
/sdd:ship <feature-description>
    │
    ▼
Stage 1 — Spec        planner (--spec-only)        → requirements.md  [critic embedded]
    │                                                 Gate: human approval (interactive mode)
    ▼
Stage 2 — Plan        planner (--design-and-tasks) → design.md + tasks.md  [critic embedded]
    │  (per task in tasks.md)
    ▼
Stage 3 — Implement   executor (TDD)               → passing tests + implementation, commit
    │
    ▼
Code Critique         critic (code)                → PASS / REVISE (routes back to executor)
    │
    ▼
Stage 4 — QA          tester (adversarial)         → PASS / FAIL (no source read; up to 3 cycles)
    │
    ▼
Stage 4b — Explore    qa-engineer (once, opt-in)   → fixes + friction report  [--explore only]
    │
    ▼
Stage 5 — Publish     publisher                    → docs verified, PR opened, CI monitored
```

### Stage 1: Spec
Planner writes `requirements.md`; critic reviews inline (completeness, Given/When/Then, no ambiguity) and loops until PASS. In interactive mode, surfaces the approved spec for human sign-off; `--autonomous` skips the gate.

### Stage 2: Plan
Reads approved `requirements.md`; planner writes `design.md` (decisions, architecture, test + QA scenarios); critic reviews inline (no TBDs, scenario coverage, consistency) and loops until PASS; planner then writes `tasks.md` (and GitHub issues with `--issues`).

**Acceptance criteria are frozen at design approval.** The QA Scenarios in `design.md` are what
the sealed verifier later checks, and the planner is the agent that wrote them. A `DESIGN_GAP`
route-back may revise them only as an explicit, recorded decision — never as a side effect of a
retry. If a scenario changes, say so in the design's Decisions table and re-approve; a test that
moves to accommodate the code it is grading has stopped being a test.

### Stage 3: Implement
The executor is the only agent that writes code. Full TDD per task: red (failing tests from design.md Test Scenarios) → green (minimum code) → refactor → one commit. On a design gap it reports `DESIGN_GAP` and the orchestrator routes back to the planner.

### Code Critique
After each task, the critic checks design adherence (no unspecced keys/modules/components), test quality (behaviour-focused, covers design scenarios), and code quality. On REVISE the orchestrator routes back to the executor (max 2 cycles).

### Stage 4: QA
Tests observable behaviour against `design.md` QA Scenarios. **Never reads source code** — and
this is enforced by the `tester` agent declaring no `Read`, `Grep`, or `Glob` tool, not merely
by instruction. See the verifier seal in [harness.md](harness.md) for why, and for the one
residual hole. On FAIL, gives behavioural feedback to the executor (max 3 cycles).

### Stage 4b — Explore (optional, off by default)
Runs only with `/sdd:ship --explore`, or when `.claude/sdd/config.json` sets
`"pipeline": {"explore": true}` (`--no-explore` turns it off for one run). After every task has
passed QA, the `qa-engineer` plays with the whole feature once in the running app, fixes each
bug it confirms test-first, and reports UX friction without changing it. Its fix commits go
through the code critic (max 2 cycles, else they are reverted) and the full test suite; its
report goes into the PR description. It does not replace Stage 4: the tester stays the
independent verdict, because the explorer reads and edits the code. Choose it for a careful,
slower ship; leave it off for a quick one.

### Stage 5: Publish
`/sdd:prepare-docs` (verify tasks, update INDEX, audit, commit checkpoint) → draft PR description from specs → `/sdd:create-pr` → monitor CI; route code failures back to the executor, retry infra flakes once.

---

## Manual stage invocation

| Skill | Stage |
|---|---|
| `/sdd:spec <domain>` | Stage 1 — requirements.md (critic embedded) |
| `/sdd:plan <domain>` | Stage 2 — design.md + tasks.md (critic embedded) |
| `/sdd:tasks <domain>` | Stage 2b — regenerate tasks.md only |
| `/sdd:implement <domain> <task-id>` | Stage 3 — implement one task (TDD) |
| `/sdd:critique code <domain>` | Code critique — review executor output |
| `/sdd:qa <domain> <task-id>` | Stage 4 — QA one task |
| `/sdd:publish <domain>` | Stage 5 — verify docs, open PR, monitor CI |
| `/sdd:prepare-docs <domain>` | Stage 5 (sub-step) — doc checkpoint commit |
| `/sdd:audit [domain]` | On-demand — doc conformance check |
| `/sdd:bug-hunt <area \| --all> [--report-only] [--autonomous]` | Outside the pipeline — static audit (critic, `bugs`) + runtime pass (qa-engineer, report-only), prioritised report, gate, fixes, one PR |
| `/sdd:qa-explore <feature-or-flow> [--report-only]` | Stage 4b on its own, or ad hoc — exploratory QA that fixes confirmed bugs with a regression test each |

---

## Agents

| Agent | Role |
|---|---|
| `architect` | Pipeline orchestrator in architect mode: one mission, its own worktree |
| `planner` | Spec and task authoring (with embedded critic loops) |
| `critic` | Adversarial reviewer — requirements, design, and code; read-only static bug audit (`bugs`) for `/sdd:bug-hunt` |
| `executor` | TDD implementation |
| `tester` | Adversarial QA — behaviour testing, no source read |
| `publisher` | Docs verification, PR authoring, CI monitoring |
| `archivist` | Documentation audit (read-only, on-demand) |
| `qa-engineer` | Exploratory QA — Stage 4b when `--explore` is on, `/sdd:bug-hunt` (report-only pass, `--fix-list` fixes), or ad hoc — plays with the running app, fixes confirmed bugs test-first, reports friction (`/sdd:qa-explore`) |

Every agent declares a `role:` whose tool contract is defined in
[harness.md](harness.md#agent-roles-and-tool-contracts). The contract is what actually binds:
context isolation stated in prose is an instruction a model can exceed, whereas a tool that is
not declared cannot be called.

**`/sdd:ship`** runs the full multi-agent pipeline with context isolation, using Claude Code's Agent/Task tool (or Codex native subagents) to spawn each agent above. Inline, the calling session spawns them; in architect mode, the architect does.
