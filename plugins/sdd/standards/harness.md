# Harness — Standard

This standard defines the documentation and automation architecture the SDD plugin assumes. It is stack-agnostic: it describes *how docs, standards, and skills relate*, not what language or framework a project uses.

---

## Three-Layer Model

A project using this harness organises conventions and automation in three layers:

| Layer | Location | Audience | Contains |
|-------|----------|----------|----------|
| **CONTRIBUTING.md** | Repo root | Human (new contributors) | Entry point — project overview, navigation to standards |
| **Standards** | `docs/standards/` (project) + the plugin's `standards/` (shared) | Human + agent | Rules, conventions, naming patterns, structures |
| **Skills** | The `sdd` plugin (`/sdd:<skill>`) + any project `.claude/skills/` | Agent (+ developers who configure them) | Workflow steps, agent orchestration, tool invocations |

Standards define **what to do**. Skills define **how agents do it**. A non-agent reader can understand all project conventions by reading standards alone, without knowing skills exist.

A skill **references** a standard for the rules it follows, rather than embedding them. If a convention changes, update the standard — the skill picks it up automatically. Project-specific commands and branch names are resolved from `.claude/sdd/config.json` (see the plugin README), not hardcoded into skills.

### Standards vs Specs

| | Standard | Spec |
|---|---|---|
| **Lives at** | `docs/standards/<domain>/design.md` (project) or the plugin `standards/` (shared) | `docs/specs/<domain>/` |
| **Purpose** | Process conventions the team adopts | Specifications for systems the team builds |
| **Files** | `design.md` only (+ optional `assets/`) | Up to `requirements.md`, `design.md`, `tasks.md`, `assets/` |
| **Examples** | branching, testing, PR workflow, SDD authoring | auth, backend, frontend-design, infrastructure |
| **Lifecycle** | Stable reference — evolves slowly | Active work-in-progress — tracks implementation |

---

## File Roles

| File | Role | Audience |
|------|------|----------|
| `CONTRIBUTING.md` | Entry point — how this project works | Human |
| `AGENTS.md` | Rules and routing map — points to standards, specs, and skills. The single source of truth; no `CLAUDE.md` needed on a Claude Code version that falls back to it. | Agent |
| `docs/INDEX.md` | Doc index — links to all standards and specs | Agent + human |
| `docs/standards/<domain>/` | Project standards — process rules and conventions | Human + agent |
| `docs/specs/<domain>/` | Specs — requirements, design, implementation tracking | Human + agent |
| `docs/decisions/` | ADRs — rationale for architectural choices | Human + agent |
| `.claude/sdd/config.json` | Per-repo toolchain + branch config consumed by the plugin | Agent |

---

## AGENTS.md Contract

`AGENTS.md` is the single source of truth for this repository's rules and routing. It contains:
1. An **Always-on rules** section — the small set of rules that apply to every change (PR-only,
   the mechanical gate command, version-bump policy)
2. A **Design Docs table** — maps topics to their authoritative standard or spec design doc
3. A **Skill Routing table** — maps task types to their required skill (e.g. code changes → `/sdd:ship`)

A `CLAUDE.md` is never a second hand-maintained copy of this content. On a Claude Code version
that falls back to `AGENTS.md` when no `CLAUDE.md` is present, omit `CLAUDE.md` entirely — this
repo does. Where a `CLAUDE.md` is required (an older client, or another tool that only reads
that filename), it must be a one-line `@AGENTS.md` pointer, never a duplicate.

---

## Spec Domain Structure

Each spec domain lives at `docs/specs/<domain>/` with up to three files:

| File | Purpose | Audience |
|------|---------|----------|
| `requirements.md` | What and why — user stories, acceptance criteria, BDD scenarios | Product / dev |
| `design.md` | How — technical architecture, data models, API contracts, conventions | Dev |
| `tasks.md` | Implementation checklists — update as work completes | Dev |
| `assets/` | Reference images, diagrams, machine-readable specs | Dev / AI agents |

Not every domain needs all three files. Use what fits.

### Domain Naming

Domain names describe the **concern**, not the ticket or tool: `frontend-design`, not `dds-2830`.

### Cross-Domain References

Specs and standards link to each other via relative paths. Cross-cutting decisions go in `docs/decisions/` as ADRs, not in individual specs or standards.

---

## Cross-Reference Rules for Execution-Layer Docs

Agents read execution-layer documents linearly and do not reliably follow arbitrary cross-references. Several regressions have been caused by placing required steps behind a "see the other document" pointer; the agent completed the numbered steps and never followed the pointer. Skills and `.github/copilot-instructions.md` must therefore be **self-contained for the agent that reads them**.

Changes to execution-layer files should be linted with `/sdd:lint-harness` before being merged. Run it manually — it is intentionally **not** part of the automated `/sdd:ship` pipeline, to keep agent costs down.

### Document Roles (execution context)

| Document | When read |
|---|---|
| `.github/copilot-instructions.md` | Always-on system context — covers reactive sessions (PR comments, issue responses) |
| A skill (`/sdd:<name>`) | Read when an agent explicitly runs that skill |

`AGENTS.md` and `CONTRIBUTING.md` are the **design/standards layer** — navigational only, pointing agents and humans to the execution layer.

### Cross-Reference Taxonomy

**✅ Works: navigational pointer (design layer → execution layer).** `AGENTS.md` saying "for PR creation, use `/sdd:create-pr`" works because the *user* triggers the skill — the agent doesn't have to decide to go read it.

**✅ Works: sub-detail reference within an active step.** A skill that is already executing can reference another document for a concrete artifact (a script, a template, a code block). The agent is mid-step and follows the pointer to retrieve a specific thing.

**✅ Works: dispatch.** A skill whose whole job is to parse arguments and hand off to an agent
that carries the full contract is doing *routing*, not delegating a step. The contract belongs
with the agent because that is where its `tools:` restrictions are declared, and the two must
not drift apart. The stage skills (`/sdd:implement`, `/sdd:qa`, `/sdd:critique`, `/sdd:publish`)
are this pattern deliberately: they are the interactive entry points, and `/sdd:ship` is the
streamlined one. Both surfaces are wanted; they simply have to be distinguishable, which is why
every skill description carries a "Does not trigger" clause naming the pipeline path.

**❌ Fails: delegating a whole step via cross-reference.** A skill saying "for screenshots, see `copilot-instructions.md`" causes the agent to note the reference and continue without following it.

**Scope note.** This rule is about *steps*, but it also applies at *file* scale, and
`/sdd:lint-harness` step 2 originally checked only the former: it iterates numbered steps
looking for one whose sole content is a pointer. A file with no numbered steps — where the
entire document is the reference — was invisible to it. The distinction that resolves this is
dispatch versus delegation above: a file that routes is fine, a step that abdicates is not.

**❌ Not possible: `copilot-instructions.md` as orchestrator of skills.** Claude Code has an explicit Skill tool that can invoke a skill. Copilot has no equivalent — `copilot-instructions.md` is a passive system prompt, not a program. It can point to skills navigationally, but cannot cause them to execute.

### Cross-Reference Design Rules

1. **Design/standards layer** (`CONTRIBUTING.md`, `AGENTS.md`, `docs/standards/`): cross-references are fine and encouraged. This layer is navigational.
2. **Execution layer** (skills, `.github/copilot-instructions.md`): each document must be self-contained for the agent that reads it. Rules that apply to both reactive and skill-driven contexts must appear in both files — this duplication is intentional, not a smell.
3. **Cross-reference within an active step** (skill → sub-detail in another file): acceptable for concrete artifacts. Not acceptable for delegating responsibility for a whole step.
4. **Never use a cross-reference to make a step optional by implication.** If a step must happen, it must appear as a numbered step in the document the agent is actively following.
5. **`copilot-instructions.md` and skills are peers, not a hierarchy.** Neither reliably orchestrates the other. Shared rules must be duplicated.

## Agent roles and tool contracts

Context isolation is this pipeline's main safety property, and prose cannot enforce it. "Pass
only the Test Scenarios section" is an instruction a model can exceed. What binds is the
agent's `tools:` declaration: **a tool that is not declared cannot be called.**

Every agent therefore declares a `role:`, and each role carries a tool contract:

| Role | Agents | Contract |
|---|---|---|
| `orchestrator` | `architect`, `publisher` | Runs a pipeline; must declare `Agent`. Broad access by nature. |
| `author` | `planner`, `executor` | Writes specs, plans, or code. Needs `Read` and `Write`. |
| `reviewer` | `critic` | Must declare no write tool — it cannot be able to change what it judges. |
| `verifier` | `tester` | Must declare no `Read`, `Grep`, or `Glob`. |
| `auditor` | `archivist` | Read-only inspection and reporting. |

### Why the verifier is sealed

A verifier that can read the implementation it grades is the configuration that reports success
while real behaviour degrades — artifact and test co-evolve until the test measures the wrong
thing. Published work on self-improving agents that authored both their policy and their own
tests found every run in a 35-case sweep self-scoring at or above 0.70, while 15 of those
policies performed *below random* and six sat at the benchmark floor. The seal is the
mitigation, and it has two halves: the judge cannot see what it judges, and it does not author
its own acceptance criteria (see the freeze rule in
[agent-pipeline.md](agent-pipeline.md#stage-2-plan)).

**Declared residual risk.** The `verifier` role permits `Bash`, because the tester needs it to
start a dev server, and `Bash` can read source. The seal is therefore strong but not absolute.
Ranked by strength: a prompt rule is weakest; a `tools:` declaration is real, because an
undeclared tool cannot be called; the environment is actual enforcement, because source that is
not on disk cannot be reached by anything. The tester sits at the middle rung with one hole,
recorded here rather than hidden behind a prose rule that reads as absolute. Closing it means
running QA against a built artifact in a directory without sources — a pipeline change, not a
declaration change. Until then, `Bash` in a verifier is for process control, not inspection.

## Every rule names its gate

**Each rule stated in a standards document carries a `Gate` column.** The value is either the
name of a script in [`scripts/checks/`](../../../scripts/checks/), or the literal word
`judgment`.

An empty cell is a bug. This repository's own harness-quality spec put it best: *"A rule
enforced by asking an agent to remember it is a preference."* Preferences drift silently, and
the point of the column is to make the difference **visible** rather than implicit. Marking a
rule `judgment` is a good answer — some rules genuinely cannot be mechanised, and saying so is
honest. Leaving the column blank is what is not allowed.

Adoption is a **ratchet**, not a flag day. `strict_skills` and `evals_required` in
[`harness-config.json`](../../../scripts/checks/harness-config.json) list the skills held to the
fuller authoring schema; raise the bar for one skill, add its name, move on. `coverage_ratchet`
refuses removals, because the failure mode of a staged rollout is that a red pipeline gets fixed
by quietly deleting a name.

```bash
./scripts/check-all.sh      # every gate, no install step
./tests/run-fixtures.sh     # proves each gate still fires
```

`/sdd:lint-harness` remains the judgment half — step-delegation and rule drift need a reading of
intent. The mechanical half now runs in CI on every pull request, so the two are complementary
rather than the same check done less reliably.

### Rules in this document

| # | Rule | Gate |
|---|---|---|
| H1 | An execution-layer doc is self-contained for its reader | `judgment` |
| H2 | No numbered step whose only content is a pointer | `judgment` |
| H3 | Dispatch is legitimate; step delegation is not | `judgment` |
| H4 | Every agent declares `tools:` and a known `role:` | `agent_tools_declared` |
| H5 | An agent's tools satisfy its role contract | `agent_tool_seal` |
| H6 | A verifier declares no file-read tool | `agent_tool_seal` |
| H7 | A reviewer declares no write tool | `agent_tool_seal` |
| H8 | No two descriptions are interchangeable | `description_collision` |
| H9 | Every skill description states what does not trigger it | `skill_frontmatter` |
| H10 | Relative links and anchors resolve | `markdown_links` |
| H11 | Acceptance criteria change only explicitly | `judgment` |
| H12 | A plugin change bumps the version in both manifests | `version_bump` |
| H13 | Adoption coverage grows, never shrinks | `coverage_ratchet` |
| H14 | Every stated rule names a gate or `judgment` | `judgment` |

H1–H3 are `judgment` deliberately: mechanising them would reject the stage-dispatch skills,
which are the interactive entry points this harness wants. H11 needs a reading of whether a
change was recorded as a decision. H14 is the one rule that cannot check itself.

### Known Anti-Patterns

| Anti-pattern | Description |
|---|---|
| Step-delegation cross-reference | An execution-layer step whose *only* content is a pointer to another file |
| Rule drift | A rule present in `copilot-instructions.md` but absent from the relevant skill, or vice versa, for content that must be consistent across both contexts |
| `gh release create` for screenshots | Using GitHub Releases to host PR screenshot images |
| Playwright MCP browser for GitHub uploads | Navigating to github.com via Playwright MCP to upload screenshots |
| Interchangeable description | A skill and the agent it dispatches carrying the same description text. The description is the only text a model reads before deciding what to load; identical strings leave nothing to discriminate on |
| Undeclared tools | An agent with no `tools:` key, which inherits everything its caller has and silently voids the isolation the pipeline claims |
| Unsealing the verifier | Adding a file-read tool to the `verifier` role's agent. No test fails when this happens, which is exactly why it needs a gate |
