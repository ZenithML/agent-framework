# Doc Structure — Standard

This standard is the single source of truth for the `docs/` hierarchy a project using the SDD plugin maintains. It defines how documentation is organised to support spec-driven development. Agents and humans consult it when creating, locating, or auditing documentation.

For the broader harness architecture (three-layer model, AGENTS.md contract, cross-reference rules), see [`harness.md`](harness.md).

## Directory Layout

```
docs/
  INDEX.md                    — master index: standards, specs, reference guides, decisions

  standards/<domain>/         — project-specific process standards: rules and conventions by topic
    design.md                 — the standard definition

  specs/<domain>/             — one directory per feature domain
    requirements.md           — what and why (source of truth for intended behavior)
    design.md                 — how (architecture, decisions, test scenarios)
    tasks.md                  — implementation checklist

  decisions/                  — architectural decision records
    ADR-NNN-short-name.md     — numbered sequentially, kebab-case
```

> Canonical templates for `requirements.md`, `design.md`, `tasks.md`, and ADRs ship with the plugin at `${CLAUDE_PLUGIN_ROOT}/templates/docs/`. Agents read those when creating new docs.

## File Rules

### `docs/INDEX.md`
- Lists every standard in `docs/standards/`
- Lists every domain in `docs/specs/` with its current status
- Lists every file in `docs/decisions/`
- **Must be updated** whenever a standard, domain, ADR, or reference guide is added or its status changes

### `docs/specs/<domain>/`
Create a domain directory when a change introduces any of:
- A new screen, route, or user-facing surface
- A new module, hook, or service
- A new data model
- A new persistent-state key (e.g. localStorage, DB column, cache key)

Do **not** create a domain spec for bug fixes, config changes, or docs-only changes.

Each domain has up to three files: `requirements.md`, `design.md`, `tasks.md`. Not every domain needs all three — use what fits the scope of the change.

#### `requirements.md`
- **Status values:** `Draft` → `Review` → `Approved`
- **Required sections:** Problem Statement, Goals, Out of Scope, User Stories & Acceptance Criteria, Constraints, References
- Every goal must be independently testable
- Every user story must have Given/When/Then acceptance criteria
- Constraints must include accessibility requirements (e.g. WCAG 2.1 AA) for any UI changes

#### `design.md`
- **Status values:** `Draft` → `Review` → `Approved`
- **Required sections:** Architecture, Decisions, Test Scenarios (Unit Tests, BDD Scenarios, BDD Traceability, QA Scenarios), Edge Cases & Error Handling
- Decisions table must have no unresolved rows (no TBD)
- BDD scenarios must trace to acceptance criteria in requirements.md
- QA scenarios must be executable without reading source code

#### `tasks.md`
- **Required sections:** `## Tasks` with a Source header linking to requirements.md and design.md
- Tasks ordered by dependency: data model → utilities → services/modules → UI → integration
- Each task completable in a single commit
- When issue tracking is used, completed tasks (`[x]`) should reference an issue number `(#N)`. Projects that do not use per-task issues may omit this.

### `docs/decisions/`
- Named `ADR-NNN-short-name.md`, numbered sequentially from `001`
- **Required sections:** Context, Decision, Consequences
- **Status values:** `Proposed` → `Accepted` → `Superseded by ADR-NNN`
- Append-only — to reverse a decision, write a new ADR that supersedes it
- Use for cross-cutting concerns only; domain-specific decisions go in `design.md`

### `README.md`
- Lives at the project root (not in `docs/`)
- **Required sections:** project description/overview, tech stack, getting started (install + run)
- **Must be updated** when structural or behavioural changes are merged

## What Belongs Where

| Content | Location |
|---|---|
| Feature behavior and acceptance criteria | `docs/specs/<domain>/requirements.md` |
| Implementation design and decisions | `docs/specs/<domain>/design.md` |
| Implementation checklist | `docs/specs/<domain>/tasks.md` |
| Cross-cutting architectural decisions | `docs/decisions/ADR-NNN-short-name.md` |
| Domain-specific decisions | `docs/specs/<domain>/design.md` Decisions table |
| Project-specific process rules (release flow, incident response, etc.) | `docs/standards/<domain>/design.md` |
| Product/platform reference guides | `docs/` top level |
| Project overview and setup | `README.md` |
