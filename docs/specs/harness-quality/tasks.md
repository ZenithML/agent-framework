# Harness Quality — Tasks

Implementation checklist for [`requirements.md`](requirements.md). Update as work completes.

Priority: **P0** blocks trusting the repo · **P1** durable knowledge & governance · **P2** sequenced last.

Effort: **S** ≤ half a day · **M** ~1–2 days · **L** > 2 days.

Gate scripts are **Python 3, stdlib only** — no CI install step.

---

## Done

- [x] **D1** Delete the `copilot-ship` skill and every reference (`README.md`, `standards/agent-pipeline.md`, `standards/harness.md`, `lint-harness` regex, `plugin.json`) — *owner decision; removes the host fork and the motivation for a host seam*
- [x] **D2** Delete the invalid `skills` array from `plugin.json` — the field's schema is a string-or-array of directory paths, not `{name, source}` entries. `claude plugin validate` failed on this repo before the fix; both manifests now pass `--strict`
- [x] **D3** Drop the redundant `metadata.pluginRoot` from `marketplace.json` — the `./`-prefixed `source` already resolves from the marketplace root
- [x] **D4** Update `CONTRIBUTING.md`: no manifest edit when adding a skill, and both lint commands documented

---

## M1 — Gates and governance

### W1 · Mechanical enforcement (P0)

The official validator does most of this. Write custom checks only for what it does not cover.

- [ ] **T1.1** Wire `claude plugin validate . --strict` and `claude plugin validate ./plugins/sdd --strict` into `check-all.sh` — **S** — *Covers manifest schema, duplicate names, source path traversal, skill/agent frontmatter, `hooks.json`, and marketplace⇄plugin version agreement. Criterion 1*
- [ ] **T1.2** `scripts/checks/version_bump.py` — if any path under `plugins/sdd/**` differs from the merge base, `plugin.json` version must differ from the base's, and `marketplace.json` must equal it — **M** — *Criterion 2. The validator checks agreement; only this checks that the number went **up***
- [ ] **T1.3** `scripts/checks/markdown_links.py` — every relative markdown link in tracked `.md` files resolves; `#anchor` fragments resolve to a real heading — **M** — *Must skip template content that skills emit into a **consumer's** repo. A naive checker already false-positives on `sdd-init/SKILL.md:367-368`, where `standards/branching/design.md` is a link in a file the skill writes elsewhere, not a link from this repo. Fenced blocks and lines containing `<DOCS_ROOT>` are the signal*
- [ ] **T1.5** `scripts/checks/config_examples.py` — `config.example.npm.json` and `config.example.python.json` validate against `config/config.schema.json`; the schema's key set matches the placeholder table in `README.md` — **M** — *Stdlib only: hand-roll the subset of JSON Schema the file uses rather than taking a `jsonschema` dependency*
- [ ] **T1.6** `scripts/checks/preamble_drift.py` — the Configuration preamble block is byte-identical across every skill that carries it; print the diff on mismatch — **S**
- [ ] **T1.7** `scripts/check-all.sh` — aggregate runner; per-check pass/fail summary; non-zero on any failure; runnable locally with no install step — **S**
- [ ] **T1.8** Negative-control fixtures: `tests/fixtures/checks/<check>/{pass,fail}/` for all four custom checks, plus a runner asserting pass→0 and fail→non-zero — **M** — *Criterion 7. A gate without one is not done*
- [ ] **T1.9** `.github/workflows/validate.yml` — runs `check-all.sh` on `pull_request` and on `push` to `main`; runs the fixture runner in the same job; **pins the Claude Code CLI version** — **S**
- [ ] **T1.10** Split `/sdd:lint-harness`: move steps 3 & 5 (prohibited screenshot mechanisms, skill-name references in changed standards) into `scripts/checks/`; keep steps 2 & 4 (step-delegation, rule drift) in the skill; add a "this skill is judgment, not a complete checklist — the mechanical half runs in CI" preamble — **M**
- [ ] **T1.11** Update `AGENTS.md` to reference the CI gate now that `CONTRIBUTING.md` has been corrected (D4) — **S** — *Superseded in shape, not substance: `CLAUDE.md` was removed and consolidated into `AGENTS.md`'s Always-on rules, which already names `./scripts/check-all.sh`. Re-verify the wording still satisfies this task rather than re-checking it blind.*

> T1.4 (frontmatter validation) is **dropped** — `claude plugin validate` covers skill, agent, and command frontmatter. T1.0 and T1.12 (the discovery and `pluginRoot` questions) are answered in [`requirements.md`](requirements.md) §8 and applied in D2/D3.

### W7 · Governance (P1, cheap)

- [ ] **T7.1** Add `LICENSE` — **S** — *Blocked on: which licence. Needs an owner decision*
- [ ] **T7.2** Add `CHANGELOG.md`; wire it to the existing category config in `.github/release.yml` — **S**
- [ ] **T7.3** Stability statement in `README.md` — current posture, what consumers may rely on, the condition that ends it, and a scheduled removal (DeepSeek's pre-release-stance pattern) — **S**
- [ ] **T7.4** `.github/ISSUE_TEMPLATE/` (bug, skill request) and `.github/pull_request_template.md` — the PR template asserts: gates run, version bumped if `plugins/sdd/**` touched, decision record attached if non-trivial — **S**
- [ ] **T7.5** `CODEOWNERS` — **S**

---

## M2 — Delivery verification

### W2 · Install path (P0)

- [ ] **T2.1** `tests/fixtures/consumer/` — a minimal project with a pre-existing `.claude/settings.json` carrying unrelated keys, plus a pre-existing `.claude/skills/` directory — **S**
- [ ] **T2.2** CI job: run `install-skills.sh` against the fixture; assert the expected file set, that every `${CLAUDE_PLUGIN_ROOT}` occurrence was rewritten to a repo-relative `.claude/` path with **zero** remaining, that the SessionStart hook is declared, and that the `.harness-version` stamp is written — **M**
- [ ] **T2.3** Assert **no clobber**: pre-existing `settings.json` keys survive the merge; pre-existing `.claude/skills/` content is untouched — **S** — *This is the data-loss case*
- [ ] **T2.4** Assert **idempotency**: a second run produces an identical tree and does not duplicate the hook declaration — **S**
- [ ] **T2.5** Same coverage for `vendor.sh`, including `--name` and `--dry-run` (dry-run must change nothing) — **M**
- [ ] **T2.6** Run the W2 matrix on `ubuntu-latest` **and** `macos-latest` — **S** — *BSD vs GNU `sed`/`find` divergence is exactly what these scripts rely on*

---

## M3 — Knowledge layer

### W3 · Decision & incident records (P1)

- [ ] **T3.1** `docs/decisions/README.md` — lifecycle folders, the closed class set (`feature`, `bug-fix`, `simplification`, `architecture`, `process`), path convention `{lifecycle}/{class}/YYYY-MM-DD-topic.md`, the required skeleton per lifecycle, and the mandatory-alternatives rule — **M**
- [ ] **T3.2** `scripts/checks/decision_format.py` — header block, `Status:` agreeing with its folder, required sections present, **proposal-tense headings rejected in `implemented/`**, `## Alternatives considered` present — **M**
- [ ] **T3.3** Negative-control fixtures for T3.2 — **S**
- [ ] **T3.4** `docs/postmortems/README.md` — the subtle + systemic + costly test, executive-summary-first format, and the requirement to link forward to the guardrail produced — **S**
- [ ] **T3.5** Backfill postmortem: the step-delegation regression behind `standards/harness.md` — **S** — *Today its only trace is one sentence of prose*
- [ ] **T3.6** Backfill postmortem: `${CLAUDE_PLUGIN_ROOT}` path rewrite + `.claude/` clobber guard (commit `d9d42e5`) — **S** — *Links forward to T2.2/T2.3 as its guardrail*
- [ ] **T3.7** Backfill postmortem: skills not discovered until copied to `.claude/skills/` (commit `6c0ba3f`) — **S** — *Links forward to T2.2*
- [ ] **T3.8** Backfill postmortem: the invalid `skills` manifest field (D2) — an official validator existed, was never wired to anything, and a malformed manifest shipped — **S** — *Links forward to T1.1*
- [ ] **T3.9** Add the rule to `AGENTS.md`: a non-trivial change carries a decision record in the same PR; mechanical edits exempt — **S**
- [ ] **T3.10** Write decision records for the five resolved decisions in [`requirements.md`](requirements.md) §8 — **M**
- [ ] **T3.11** Update `docs/INDEX.md` to link decisions and postmortems; consider generating it — **S**

### W4 · Doc tiers, budgets, extension map (P1)

- [ ] **T4.1** Extend `plugins/sdd/standards/doc-structure.md` with the tier table (**including the "does NOT belong here" column**) and the one-line placement rule — **M**
- [ ] **T4.2** Add the slop checklist — duplicated homes, narrated history, status annotations, hand-restated catalogs, reasoning transcripts, paragraph walls, emphasis inflation — **S**
- [ ] **T4.3** `scripts/doc-budgets.json` + `scripts/checks/doc_budgets.py` — ceilings, missing-file rejection, ordered escalation documented in the failure message — **M**
- [ ] **T4.4** Bring `AGENTS.md` under budget — **M** — *No `CLAUDE.md` remains to keep in sync: this repo's Claude Code version falls back to `AGENTS.md` when the file is absent, so the file was removed outright rather than kept as a generated or symlinked projection. The gate only needs to enforce `AGENTS.md`'s budget and that no `CLAUDE.md` reappears as a duplicate.*
- [ ] **T4.5** `Goal → Mechanism` extension table in `plugins/sdd/standards/agent-pipeline.md`: add a stage / add a gate / add an agent / add a config key — each row naming the file and the gate — **M**
- [ ] **T4.6** Add the rule: changing the pipeline requires updating the extension table in the same change — **S**
- [ ] **T4.7** Reference the extension table from `CONTRIBUTING.md`, replacing the remaining prose "Adding a skill" steps — **S**

---

## M4 — Introspection and behaviour

### W6 · Config introspection (P2)

- [ ] **T6.1** Extract the Configuration preamble to a single canonical source under `plugins/sdd/standards/`; generate the per-skill copies; wire generation into `check-all.sh` so T1.6 checks generated output — **M**
- [ ] **T6.2** `/sdd:config` (or a `sdd-init` step) printing every placeholder with its resolved value and source (`config-file` / `auto-detected` / `default`) — **M**
- [ ] **T6.3** Document config precedence as an ordered list in `standards/harness.md` — **S**

### W8 · Plugin eval (P2, spike)

- [ ] **T8.1** Establish whether `claude plugin eval` is available on this account (it may need early-access enablement) and what its suite format and JSON report look like — **S**
- [ ] **T8.2** Spike it against two skills (`spec`, `create-pr`): can it assert skill *behaviour*, not just presence? Produce a go/no-go with evidence — **M** — *Blocked on T8.1*
- [ ] **T8.3** If go: eval suite for the pipeline entry points, wired into `validate.yml` — **L** — *Blocked on T8.2*

---

## Ordering constraints

```
T1.1..T1.6 → T1.7 → T1.9        checks, then aggregate, then CI
T1.8 gates "done" for W1        no custom gate ships without a negative control
T2.* after T1.9                 reuse the workflow scaffolding
T3.6, T3.7 → link forward to T2.2/T2.3 as their guardrails
T3.8 → links forward to T1.1 as its guardrail
T4.3 → T4.4                     budgets before trimming to them
T6.1 changes T1.6's subject     preamble becomes generated; gate checks generated output
T8.1 → T8.2 → T8.3              availability, then viability, then build
```

## Not doing (and why)

Recorded so these do not get re-proposed. See analysis §1.13 and [`requirements.md`](requirements.md) §3.

- **A host provider seam** — `copilot-ship` was the only host fork and it is deleted. Designing a seam for a variation that no longer exists is speculative generality. Revisit only if a second host is actually required
- **Per-file 100% coverage** — no runtime code to cover
- **~97 gate scripts** — proportional to a 40-package monorepo; ours is four custom checks plus the official validator
- **Bilingual doc pairing** — no requirement
- **Stacked PRs / `gh stack sync`** — needs a whole skill plus a post-sync validation protocol to be safe; wildly disproportionate here
- **A documentation website** — `README.md` plus `docs/` is sufficient at this size
- **Closing the repo to external PRs** — the opposite of what a small internal harness wants
