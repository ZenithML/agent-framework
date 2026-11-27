# Refactoring with evidence

**Status:** Accepted

How the harness changes code that already works: hardening a proof of concept for production
(`/sdd:productionize`) and moving code from one thing to another (`/sdd:migrate`). Both follow
the rules below. The research and sources behind them are in
`docs/research/refactoring-evidence.md` in the agent-framework repository.

A refactor is only as good as the evidence that it kept what mattered. "Cleaner", "safer" and
"faster" are claims; a before/after table is evidence. A PR from these skills carries the table.

## The seven rules

1. **Safety net first.** Before any change, pin what the code does today with
   **characterization tests** (Feathers): tests that pass on the current code and assert its
   observed behaviour, odd parts included. Where the output is large (a rendered page, a
   report, an API response), use a **golden master**: record the output for a fixed set of
   inputs to a file and compare against it, with time, random values and ids scrubbed at the
   seam. A characterization test that never failed proves nothing: show each one bites, by a
   deliberate temporary break of the code it covers or by `<MUTATE_CMD>` on that code.
2. **Measure before you touch.** Take a baseline snapshot with
   `${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py snapshot --label baseline` on the code as it is.
   The baseline must be green: a red suite is fixed or explicitly reported first, never
   refactored over.
3. **Two hats, never at once** (Fowler; Beck, *Tidy First?*). A commit either changes
   structure (`refactor:`, tests untouched and green before and after) or changes behaviour
   (`feat:`/`fix:`, test first). Never both. When a structural step needs a test to change, it
   was a behaviour change: stop and plan it as one.
4. **Small, reversible steps.** Every commit leaves the suite green. Every wave of a migration
   is one revertable commit. Interfaces and data change by **expand and contract** (add the
   new, move callers, then remove the old), never in one step. Rollout risk goes behind a flag.
5. **Tests are not proof of equivalence.** A passing suite only covers what it asserts, and
   studies of LLM refactorings find suites overstate equivalence. Stack oracles in proportion to
   risk: characterization and golden-master tests, types and build, the mutation score of the
   area, a **differential run** (old and new on the same recorded or generated inputs, outputs
   compared), and a structural audit (for example, zero remaining uses of the old API).
6. **Mechanical before generative.** A repeatable transform is a codemod (an AST rewrite or an
   official upgrade tool), run and verified like any other change. Agents handle the long tail
   the codemod cannot, and every agent edit passes the same checks, with failures fed back and
   retried (the shape of Google's and Airbnb's LLM migrations).
7. **Stop when the plan is wrong.** A step that cascades into unplanned edits is reverted, not
   pushed through (the Mikado method): note the prerequisite it revealed, do that first, and
   try again. A migration wave that regresses is reverted and its slice goes back to the pilot.

## Task labels

Plans written by these skills label every task in `tasks.md`. The label decides the executor
mode and what the critic checks.

| Label | Purpose | Executor mode | Commit prefix | Critic checks |
|---|---|---|---|---|
| `[characterize]` | Pin current behaviour | `characterize` | `test:` | Tests pass on unchanged code, assert outputs (not internals), and each bites |
| `[tidy]` | Change structure only | `tidy` | `refactor:` | [Behaviour-preservation criteria](#behaviour-preservation-criteria) |
| `[change]` | Change behaviour on purpose | `full` (or the `strict` Prosecutor/Defender pair) | `feat:` / `fix:` | The usual `code` criteria, plus the gap or rubric item it closes |

`[characterize]` tasks come first, then `[tidy]` tasks that make the change easy, then
`[change]` tasks that make the easy change.

### Behaviour-preservation criteria

Passed to the critic in `code` context in place of the design.md Test Scenarios check, for
`[tidy]` tasks and migration waves. Each REVISE item names the file and line.

- No test file changed, except where the task names the tests themselves as the subject (a test
  framework migration), and then no expected value or assertion was weakened, removed or skipped.
- No exported name, public signature, route, CLI flag, config key, schema or persisted format
  changed unless the task names it.
- No new behaviour: no new branch on input, default value, error message, log line a user or
  operator relies on, or side effect.
- The commit is `refactor:` only and stays inside the files the task or wave names.
- For a migration wave: no use of the old dependency or API is left in the wave's slices.

## Evidence

`${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py` records and compares. It runs only the commands in
`.claude/sdd/config.json` and installs nothing.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py snapshot --label baseline --out .review/evidence/<slug> --paths <area paths>
# ... the work ...
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py snapshot --label after --out .review/evidence/<slug> --paths <area paths>
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py compare .review/evidence/<slug>/baseline.json .review/evidence/<slug>/after.json --md .review/evidence/<slug>/evidence.md
```

| Evidence | From | Gate (defaults) |
|---|---|---|
| typecheck, lint, build, test pass or fail | `commands.typecheck`, `.lint`, `.build`, `.test` | A check that passed must still pass; a red check is never waved through |
| Passing and failing test counts | test runner summary (Jest, Vitest, pytest, unittest, node, go) | No more failures; no fewer passing tests unless `--allow-fewer-tests`, with the reason in the PR |
| Line coverage % | `commands.coverage`: istanbul or coverage.py report, Cobertura XML, or runner output | Drop no more than 0.5 points |
| Mutation score % | `commands.mutate` on `--paths`: Stryker report, PIT, cargo-mutants, or runner output | Drop no more than 1 point |
| Benchmark median | `commands.bench`, run 5 times | No more than 10% slower |
| Any number | a `METRIC name=value` line from any command (p95 latency, bundle size, old-API usages) | Gated with `--lower-is-better` or `--higher-is-better`; otherwise shown |
| Lines of code and files | `--paths` | Shown |

A check measured in the baseline and missing afterwards fails the comparison: evidence that
was not collected is not evidence. Snapshots and the comparison live under `.review/` and are
never committed; the Markdown table goes into the PR body under `## Evidence`.

Optional config keys these skills read: `commands.typecheck`, `commands.coverage` and
`commands.bench`, alongside the existing `commands.mutate`. A skill never adds a tool to the
project to fill a missing key. It records the gap in the report instead, and the user decides.

## Production-readiness rubric

`/sdd:productionize` scores an area on each item as **Ready**, **Partial** or **Missing**, with
evidence (a file and line, a command and its output, or the absence searched for). It is a
floor for "safe to put in front of users", adapted from Google SRE's production readiness
reviews, the twelve-factor app and OWASP ASVS level 1. Not every item applies to every
project: mark one **N/A** with the reason.

| Id | Item | Ready means |
|---|---|---|
| R1 | Safety net | The core flows and public surface have tests that run in CI and fail when behaviour breaks |
| R2 | Errors and failure modes | No swallowed errors; timeouts and bounded retries on network calls; input validated at the boundary; a user sees a useful message, not a stack trace |
| R3 | Configuration and secrets | No secrets, hosts or credentials in code or committed config; configuration from the environment; a documented example config |
| R4 | Security | Every entry point checks who is calling and what they may do; no injection (SQL, shell, HTML); dependencies free of known high-severity vulnerabilities by the ecosystem's audit command |
| R5 | Observability | Structured logs at the boundaries, errors reported somewhere a human will see them, a health check, and the few numbers that show the service works |
| R6 | Performance and limits | No unbounded queries, loops, payloads or memory; pagination; the hot path has a benchmark or a load test |
| R7 | Data | Schema changes are versioned migrations, idempotent and tested; data is validated on the way in; backups and restore are known |
| R8 | Build, deploy and rollback | Pinned dependencies with a lockfile; CI runs the checks; one command builds; deploy and rollback are written down |
| R9 | Maintainability | Strict types where the language has them, lint clean, no dead code or copy-paste modules, clear module boundaries |
| R10 | Documentation | A README that gets a new developer running; the non-obvious decisions recorded |

## Migration patterns

`/sdd:migrate` chooses one per migration and records why.

| Pattern | Use when | Rollback |
|---|---|---|
| **Codemod in waves** | Mechanical change with the same semantics: an API rename, a library major version with an upgrade tool, a test framework swap | Revert the wave's commit |
| **Branch by abstraction** | Replacing a component used in many places: put an interface in front of it, move callers to the interface, swap the implementation behind it | Point the interface back at the old implementation |
| **Strangler fig** | Replacing a system, service or set of routes: a facade routes slice by slice from old to new | Route the slice back to the old system |
| **Expand and contract** (parallel change) | Changing a public interface, schema or data format: add the new alongside the old, dual-write or adapt, migrate readers and writers, backfill, then remove the old | Until contract, the old path still works; contract is a separate, later change |
| **Parallel run** (differential) | Semantics where a silent difference is costly (money, permissions, calculations): run both on the same inputs, compare outputs, serve the old until mismatches are zero over an agreed sample | Keep serving the old |

Removing the old path in production (the contract step, dropping a column, deleting the old
service) cannot be undone. It is always its own change, after the user confirms the expand
phase is deployed and healthy.

## Tools

Use what the project already has. These are the mainstream choices per ecosystem, named so a
plan can propose one; adding one to a project is the user's decision.

| Need | JavaScript / TypeScript | Python | JVM | Other |
|---|---|---|---|---|
| Coverage | Vitest or Jest `--coverage` (v8 or istanbul) | coverage.py, pytest-cov | JaCoCo | `go test -cover`, cargo-llvm-cov |
| Mutation | StrykerJS | mutmut, cosmic-ray | PIT | cargo-mutants, Stryker.NET |
| Golden master / snapshots | Vitest or Jest snapshots | syrupy, ApprovalTests | ApprovalTests | ApprovalTests ports |
| Codemods | jscodeshift, ts-morph, ast-grep, official upgrade codemods | LibCST, Bowler, `ruff --fix`, pyupgrade | OpenRewrite | ast-grep, Comby, `go fix`, Coccinelle |
| Dependency rules | dependency-cruiser, eslint-plugin-boundaries | import-linter, deptry | ArchUnit | `go vet`, cargo-deny |
| Vulnerabilities | `npm audit` / `pnpm audit` | pip-audit | OWASP dependency-check | osv-scanner (any) |
| Complexity | lizard, ESLint `complexity` | lizard, radon | lizard, PMD | lizard |
| Benchmarks | Vitest bench, hyperfine, k6 | pytest-benchmark, hyperfine | JMH | hyperfine, `go test -bench` |
| Parallel run | GitHub Scientist ports | laboratory | Scientist4J | Scientist (Ruby) |

Any of these can feed the evidence table by printing `METRIC name=value` from a configured
command, for example a complexity total or a count of old-API usages.
