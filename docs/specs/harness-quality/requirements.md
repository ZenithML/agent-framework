# Harness Quality — Requirements

**Status:** Draft · **Domain:** `harness-quality` · **Created:** 2026-08-16

Product requirements for raising `agent-framework` to the bar set in [`docs/research/deepseek-harness-analysis.md`](../../research/deepseek-harness-analysis.md). The implementation checklist is [`tasks.md`](tasks.md).

This domain deliberately dogfoods our own spec structure (`docs/specs/<domain>/`) — a harness that defines a doc structure and does not use it is evidence against itself.

---

## 1. Problem

The **content** layer of this harness is strong. Eighteen skills, seven agents, a three-layer standards model with a documented rationale, and a self-containment rule for execution-layer docs that was clearly written from real regressions.

The **enforcement** layer is almost entirely absent.

Concretely, today:

- **CI has one workflow** ([`.github/workflows/release.yml`](../../../.github/workflows/release.yml)), and it only tags releases. Nothing runs on a pull request.
- **Our own quality rule was manual by design.** `AGENTS.md` (then `CLAUDE.md`, since removed and consolidated into `AGENTS.md`) says "Run `/sdd:lint-harness` before marking any PR ready for review"; `CONTRIBUTING.md` said *"There is no automated CI gate — this is a manual step before merging."* A rule enforced by asking an agent to remember it is a preference.
- **An official validator existed and was never run.** `claude plugin validate . --strict` **failed on this repository**: `plugin.json` declared a `skills` array of `{name, source}` objects, but that field's schema is a string-or-array of *directory paths*. The manifest was invalid and the declaration did nothing — Claude Code always scans `skills/` regardless. Fixed in this change; the gap it demonstrates is the point.
- **Two version numbers must agree** ([`plugins/sdd/.claude-plugin/plugin.json`](../../../plugins/sdd/.claude-plugin/plugin.json) and [`.claude-plugin/marketplace.json`](../../../.claude-plugin/marketplace.json)) and nothing checks that they do. If plugin behaviour changes without a bump, `release.yml` silently skips — the tag already exists, so a changed plugin ships under an unchanged version with no error anywhere.
- **The install path is untested.** `scripts/install-skills.sh` and `scripts/vendor.sh` are the primary delivery mechanism — they copy files, rewrite `${CLAUDE_PLUGIN_ROOT}` paths, and merge `.claude/settings.json` in someone else's repository. Neither has ever run in CI.
- **No decision records exist.** [`docs/INDEX.md`](../../INDEX.md) says "No ADRs yet". An ADR template ships in the plugin; the repo that ships it has never written one.
- **No incident records exist.** `standards/harness.md` says *"Several regressions have been caused by placing required steps behind a 'see the other document' pointer."* That sentence is the only surviving trace of the incidents that produced this harness's most important rule.
- **No LICENSE, no CHANGELOG, no stability statement.**

The cost is not hypothetical. Every rule the harness states about *other* repositories — self-containment, no rule drift, version discipline, standards/skills separation — currently applies to this repository on the honour system. The invalid manifest is what that looks like in practice.

### 1.1 Structural finding: config resolution is duplicated eighteen times

Every skill opens with the same "Configuration" preamble telling the agent how to resolve `.claude/sdd/config.json`, fall back to auto-detection, and default branches. `CONTRIBUTING.md` instructs authors to *"copy verbatim from any existing skill."*

The duplication is **correct** under our own self-containment standard — an execution-layer doc must stand alone for the agent reading it. But eighteen hand-maintained copies with no drift gate is a rule-drift generator, and there is no way to ask the harness what it actually resolved. The fix is generation plus a drift gate (W6), not deduplication.

> A second structural finding — `copilot-ship` as a flattened fork of `ship` — was resolved by deleting that skill in this change. Host variation is no longer a live concern, so no provider seam is proposed. See §3.

---

## 2. Goals

| # | Goal | Rationale |
|---|---|---|
| G1 | Every mechanically checkable rule this repo states is enforced by a gate that runs on every PR | Pillar 7. Unenforced rules train contributors that rules are optional |
| G2 | The delivery path (marketplace, vendor, flat copy) is exercised in CI before it reaches a consumer | Pillar 8. The install scripts write into other people's repositories |
| G3 | Decisions and incidents have a durable, structured home, and creating one is a rule | Pillars 5 & 6. The knowledge behind this harness currently lives in prose asides |
| G4 | Agent-facing docs have a tier taxonomy, one home per fact, and a context budget | Pillar 4. Always-loaded instructions are a per-request spend |
| G5 | Consumers can tell what is stable, what changed, and under what licence | Pillar 10 |

## 3. Non-goals

- **Not** porting Cordis, a plugin runtime, or any TypeScript machinery. This is a docs-and-prompts plugin; ~97 gate scripts and per-file 100% coverage would be theatre (see the analysis, §1.13).
- **Not** rewriting the remaining skills. The content layer is the asset; this work wraps it in enforcement.
- **Not** a host provider seam. `copilot-ship` was the only host fork and it has been deleted; designing a seam for a variation that no longer exists is speculative generality. Revisit only if a second host is actually required.
- **Not** internationalisation, a documentation website, or stacked-PR tooling.
- **Not** opening the repository publicly. Ecosystem posture (G5) is scoped to a stability statement and a changelog; the access model is out of scope.
- **Not** building a test framework. Gates are Python scripts in `scripts/checks/`, run by one CI workflow.

## 4. Success criteria

The work is done when all of the following hold:

1. `claude plugin validate . --strict` and `claude plugin validate ./plugins/sdd --strict` **run on every pull request** and block on failure.
2. A pull request that changes any file under `plugins/sdd/` without bumping the version in **both** manifests **fails CI**.
3. A pull request that introduces a broken relative link in any tracked markdown file **fails CI**.
4. A pull request that changes an example config so it no longer validates against `config.schema.json` **fails CI**.
5. A pull request that edits the Configuration preamble in one skill but not the others **fails CI**.
6. `scripts/install-skills.sh` and `scripts/vendor.sh` run against a fixture project in CI, and their output is asserted — file set, path rewriting, `settings.json` merge, idempotency on a second run, and no clobbering of pre-existing `.claude/` content.
7. Each gate we write has a **negative control**: a fixture that the gate rejects, proving it fires.
8. `docs/decisions/` contains at least one record for each structural decision made by this work, each with an `## Alternatives considered` section.
9. `docs/postmortems/` contains the backfilled record of the step-delegation regression that motivates `standards/harness.md`.
10. A repo-root `LICENSE`, a `CHANGELOG.md`, and a stability statement exist.
11. `AGENTS.md` sits under a stated word budget, checked by a gate. (No `CLAUDE.md` exists in
    this repo — see W4 below.)

## 5. Workstreams

Gate scripts are **Python 3, standard library only** — no `pip install` step in CI, and JSON manifest work stays readable. `release.yml` already shells out to `python3`, so the dependency is not new.

### W1 — Mechanical enforcement (P0)

The gate layer: the official validator, four custom checks, one aggregate, one CI workflow.

**Lead with the tool that already exists.** `claude plugin validate --strict` checks `plugin.json` and `marketplace.json` schemas, duplicate plugin names, source path traversal, skill/agent/command frontmatter, and `hooks/hooks.json` — and warns when a marketplace entry's `version` disagrees with the plugin's, which `--strict` turns into an error. That is criterion 1 plus most of what a hand-rolled manifest and frontmatter gate would do, maintained upstream. Write custom checks only for what it does not cover.

**Scope.** `scripts/checks/` containing `version_bump.py`, `markdown_links.py`, `config_examples.py`, `preamble_drift.py`. One aggregate entry point (`scripts/check-all.sh`) that runs the two `claude plugin validate` invocations plus the four Python checks, runnable locally and invoked by CI. `.github/workflows/validate.yml` running the aggregate on `pull_request`.

**Acceptance.** Success criteria 1–5 and 7. Every custom check has a fixture under `tests/fixtures/checks/<check>/{pass,fail}/` and a runner asserting pass→0 and fail→non-zero.

**Rationale.** Highest-leverage workstream: it converts five documented obligations from hope into fact, and it is the prerequisite for trusting anything else in the repo.

**Explicitly split from `/sdd:lint-harness`.** That skill does four things, two of which are mechanical (prohibited screenshot mechanisms; skill-name references in changed standards) and two of which need judgment (step-delegation cross-references; rule drift between `copilot-instructions.md` and skills). The mechanical half moves to a Python check CI runs on every PR. The judgment half stays in the skill — and the skill gains a statement of its own authority, per Pillar 9.

### W2 — Delivery verification (P0)

**Scope.** A fixture consumer project under `tests/fixtures/consumer/`. CI jobs that run `install-skills.sh` and `vendor.sh` against it and assert the result. A second-run idempotency assertion and a pre-existing-`.claude/` no-clobber assertion.

**Acceptance.** Success criterion 6. Runs on `ubuntu-latest` **and** `macos-latest`, because the scripts use `sed`/`find` whose BSD and GNU behaviours differ and the README recommends the flat-copy path to macOS users.

**Rationale.** These scripts modify a repository we do not own. A path-rewrite bug or a `settings.json` merge that overwrites instead of merging is a data-loss bug in a consumer's repo. It has never been tested.

### W3 — Decision and incident records (P1)

**Scope.** Adopt a trimmed Agent Notes model:

- `docs/decisions/{proposed,implemented,rejected}/{class}/YYYY-MM-DD-topic.md`
- Class set — closed, gate-enforced: `feature`, `bug-fix`, `simplification`, `architecture`, `process`. (`testing` folds into `process` at our scale; the exclusion is itself recorded.)
- Required skeleton per lifecycle, gate-enforced, including **rejecting proposal-tense headings in an implemented record**.
- **`## Alternatives considered` mandatory.**
- `docs/postmortems/` with the subtle + systemic + costly test and an executive-summary-first format.
- A rule in `AGENTS.md`: a non-trivial change carries a decision record in the same PR.
- Backfill: the step-delegation regression behind `standards/harness.md`; the `${CLAUDE_PLUGIN_ROOT}` path-rewrite fix (commit `d9d42e5`); the skills-not-discovered vendoring bug (commit `6c0ba3f`); and the invalid `skills` manifest field found in this change — four real incidents whose only record is a commit subject line.

**Acceptance.** Success criteria 8–9, plus a format gate with a negative control.

**Rationale.** Path-encoded status means `ls` answers "what shipped". Mandatory alternatives are what stop a decision being re-litigated by someone who cannot see what it beat.

### W4 — Doc tiers, budgets, and the extension map (P1)

**Scope.**

- Extend `plugins/sdd/standards/doc-structure.md` with a **tier table including a "does NOT belong here" column** and the one-line placement rule.
- A **slop checklist** — the greppable doc anti-patterns.
- **Word budgets** in `scripts/doc-budgets.json` with the ordered escalation (relocate → condense → raise ceiling with PR justification). Initial ceilings: `AGENTS.md` ≤ 600, each standard ≤ 2,000, each `SKILL.md` ≤ 2,500. No `CLAUDE.md` ceiling — see below.
- A **`Goal → Mechanism` extension table** in `plugins/sdd/standards/agent-pipeline.md`: add a pipeline stage / add a gate / add an agent / add a config key — each row naming the file to touch and the gate that will check it.
- A rule that changing the pipeline requires updating that table.
- `CLAUDE.md` was removed from this repo rather than kept as a generated or symlinked projection of `AGENTS.md`: this repo's Claude Code version falls back to `AGENTS.md` when no `CLAUDE.md` is present, so there is nothing to keep in sync. `plugins/sdd/standards/harness.md` documents this as a repo-specific choice, not a rule the shared standard imposes on projects that adopt the plugin — a consumer repo whose client requires a `CLAUDE.md` still keeps one, as a one-line `@AGENTS.md` pointer. Gate only what can drift: `AGENTS.md`'s budget, and that no `CLAUDE.md` reappears as a duplicate.

**Acceptance.** Success criterion 11, plus the extension table existing and being referenced from `CONTRIBUTING.md`.

### W6 — Config introspection (P2)

Numbering preserved from the original draft; W5 (host seam) was dropped, see §3.

**Scope.** A `/sdd:config` skill (or a `--dump-config`-equivalent step in `sdd-init`) that prints the fully-resolved configuration: each placeholder, its value, and its source — explicit config file, auto-detection, or default. Extract the Configuration preamble to one canonical source under `plugins/sdd/standards/` and generate the per-skill copies, so the duplication our self-containment rule requires is machine-maintained rather than hand-copied.

**Acceptance.** Given a repo with no `.claude/sdd/config.json`, the command reports every placeholder with `source: auto-detected` or `source: default` and the value used. Generated preambles are byte-identical, checked by W1's drift gate.

### W7 — Governance (P1, cheap)

**Scope.** `LICENSE`. `CHANGELOG.md` (Keep a Changelog format, or generated from the release workflow's existing category config in `.github/release.yml`). A **stability statement** in `README.md` following the DeepSeek pattern — current posture, what consumers may rely on, and the condition under which it changes, with a scheduled removal. Issue and PR templates. `CODEOWNERS`.

**Acceptance.** Success criterion 10.

### W8 — Plugin eval (P2, spike)

**Scope.** Timeboxed spike on `claude plugin eval` — Claude Code's plugin eval suite runner, with a JSON report and CI support. It may require early-access enablement on this account; establishing that is part of the spike.

**Acceptance.** A go/no-go with evidence: can it assert skill *behaviour* (does `/sdd:spec` produce a conforming `requirements.md`?), or only presence? If go, an eval suite for the pipeline entry points wired into `validate.yml`.

**Rationale.** W1 proves the plugin is well-formed and W2 proves it installs. Neither proves a skill *works*. This is the only tier that reaches that, and it is officially supported rather than something we would build.

---

## 6. Sequencing

```
M1  W1 + W7          Gates land; repo becomes self-enforcing. Cheap, unblocks everything.
M2  W2               Delivery path verified on Linux and macOS.
M3  W3 + W4          Knowledge layer: decision records, postmortems, tiers, budgets, extension map.
M4  W6, then W8      Config introspection; then the eval spike.
```

W1 before everything: the doc gates in W4 and the format gate in W3 both build on the W1 aggregate, and W7 is small enough to ride along.

## 7. Risks

| Risk | Mitigation |
|---|---|
| **Gate theatre** — checks that pass without proving anything | Every custom gate ships a negative-control fixture. A gate without one is not done (criterion 7) |
| **Over-engineering for an eighteen-file plugin** | Non-goals are explicit; the target is four custom checks plus the official validator, not DeepSeek's ~97 |
| **The version-bump gate blocks docs-only PRs** | Scope it to `plugins/sdd/**`. Changes to `docs/`, `README.md`, and `scripts/` do not require a bump |
| **Decision records become a tax nobody pays** | The exemption for mechanical edits is explicit, and the skeleton is short. If adoption fails after M3, record *that* as a decision and drop the rule rather than letting it rot |
| **`claude plugin validate` changes behaviour between CLI versions** | Pin the Claude Code version in `validate.yml` and bump it deliberately. A validator that silently changes what it accepts is worse than none |
| **Budgets used as reduction targets** | Copy DeepSeek's framing verbatim: ceilings are guardrails; a too-low ceiling is a budget bug, and raising it with justification is a normal outcome |
| **`claude plugin eval` is unavailable or presence-only** | W8 is a timeboxed spike with an explicit no-go outcome, sequenced last and blocking nothing |

## 8. Resolved decisions

Recorded here rather than dropped, so they are not re-litigated. Each should become a `docs/decisions/` record under W3 (task T3.9).

| # | Question | Resolution |
|---|---|---|
| 1 | Gate language — Bash or Python? | **Python 3, stdlib only.** Owner decision. No install step in CI; `release.yml` already uses `python3` |
| 2 | Does `plugin.json` need a hand-maintained `skills` array? | **No — and ours was invalid.** The field's schema is a string-or-array of directory *paths*; ours was an array of `{name, source}` objects, so `claude plugin validate` failed. The default `skills/` scan always runs. Field deleted; both manifests now validate |
| 3 | Is `marketplace.json` `metadata.pluginRoot` + `source` double-prefixed? | **Redundant, now removed.** `pluginRoot` prepends to relative sources so you can write `"sdd"` instead of `"./plugins/sdd"`; our `./`-prefixed source already resolves from the marketplace root. Two ways of saying one thing, one of them ambiguous. Dropped `metadata`; validation passes |
| 4 | Should `copilot-ship` become a host provider seam? | **Neither — the skill is deleted.** Owner decision. Removes the fork, and with it the only motivation for a host seam. Recorded in §3 non-goals so it is not reproposed |
| 5 | Is `claude plugin eval` worth adopting? | **Spike it, sequenced last.** Promoted from an open question to W8 with an explicit no-go outcome |
