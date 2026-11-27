# Refactoring with evidence: PoC to production and migrations

**Date:** 2026-11-21
**Feeds:** [`plugins/sdd/standards/refactoring.md`](../../plugins/sdd/standards/refactoring.md),
`/sdd:productionize`, `/sdd:migrate`, `plugins/sdd/scripts/evidence.py`

The question: what practices make agent-driven refactoring trustworthy, for two jobs in
particular, taking a proof of concept to production and migrating code from one thing to
another, so that the result is better quality *and* the PR shows evidence of it?

## What the evidence says

### Tests passing is weaker evidence than it looks

- A 2026 differential-fuzzing study of LLM-generated refactorings found that test suites
  overstate functional equivalence; fuzzing old and new against each other caught differences
  the tests missed ([arXiv 2602.15761](https://arxiv.org/html/2602.15761)).
- In a refactoring benchmark, behavioural tests and a structural migration audit disagreed in
  both directions: some runs kept tested behaviour but failed the audit, many more passed the
  audit and failed behaviour (SWE Refactor Bench, as reported in the 2026 survey
  [arXiv 2609.12012](https://arxiv.org/pdf/2609.12012)).
- REFINE (2026), a multi-agent refactoring system, found that preserving critical asserts and
  failure calls held in only 57% of outputs, and its authors call their own checks proxies,
  not proofs ([arXiv 2608.23611](https://arxiv.org/pdf/2608.23611)).
- SWE Atlas scores refactoring tasks with a before/after behaviour-preservation check rather
  than test pass rate alone ([arXiv 2605.08366](https://arxiv.org/pdf/2605.08366)).

These are preprints, read at summary level; treat them as direction, not settled numbers.
**What the harness takes:** rule 5 (stack oracles in proportion to risk), the mutation score
in the evidence table, the structural audit as `METRIC old_usages`, and the parallel-run
pattern for costly semantics.

### Characterization first is still the foundation

Michael Feathers' characterization tests (*Working Effectively with Legacy Code*, 2004) and
golden-master or approval testing remain the starting point; recent agentic work uses
AI-written characterization tests to capture behaviour before model-led refactoring
([arXiv 2608.23616](https://arxiv.org/pdf/2608.23616)). The weak spot is a test that never
failed. **What the harness takes:** rule 1, and the executor's `characterize` mode, which must
show each test fails once under a deliberate break.

### Large migrations at Google and Airbnb

- Google's FSE 2025 industry paper, *Migrating Code At Scale With LLMs At Google*, covers 39
  migrations by three developers over twelve months: about 74% of code changes were
  LLM-generated, with an estimated 50% reduction in total time. Validation (build, tests) and
  human review and rollout stayed central ([arXiv 2504.09691](https://arxiv.org/pdf/2504.09691)).
- The companion experience report, *How is Google using AI for internal code migrations?*,
  stresses that success is not straightforward and the customisation lives in prompts,
  validation steps and the rollout ([arXiv 2501.06972](https://arxiv.org/html/2501.06972v1)).
- Airbnb migrated about 3,500 test files from Enzyme to React Testing Library in about six weeks
  against an 18-month estimate, with each step validated and retried with the errors and latest
  file fed back into the prompt (secondary source:
  [Analytics India Magazine](https://analyticsindiamag.com/global-tech/airbnb-uses-llms-to-pull-off-an-18-month-enzyme-to-rtl-migration-in-just-6-weeks-1);
  not checked against Airbnb's own write-up).

**What the harness takes:** rule 6 (mechanical first, the agent for the long tail, the same
checks on every change), the pilot slice whose failures refine the next waves, the fix cycle
that feeds errors back, and the per-wave snapshot.

### Long-standing practice

- Martin Fowler, *Refactoring* (2nd ed., 2018): the "two hats" of adding behaviour and
  restructuring, never worn at once; the strangler fig application; branch by abstraction.
- Kent Beck, *Tidy First?* (2023): separate structure changes from behaviour changes, in
  separate commits and often separate PRs; "make the change easy, then make the easy change".
- Danilo Sato, *Parallel Change* (expand and contract) on martinfowler.com.
- The Mikado method (Ellnestam and Brolund): try, see what breaks, revert, do the prerequisite
  first.
- GitHub's Scientist library: run old and new in production, compare, serve the old.
- Production readiness: Google SRE's production readiness review, the twelve-factor app, and
  OWASP ASVS level 1 inform rubric items R1 to R10.

## How it maps

| Practice | Where it lives |
|---|---|
| Characterization and golden master first | Rule 1; executor `characterize`; first tasks in `/sdd:productionize`; Step 3 in `/sdd:migrate` |
| Baseline before touching | Rule 2; `evidence.py snapshot --label baseline` |
| Two hats | Rule 3; task labels; executor `tidy` and `BEHAVIOUR_CHANGE`; behaviour-preservation criteria for the critic |
| Small reversible steps, expand and contract | Rule 4; one commit per wave; contract held back when irreversible |
| Multiple oracles | Rule 5; coverage, mutation, `METRIC` gates, differential test in a parallel run |
| Codemods first, agent for the tail, validate and retry | Rule 6; Step 2 and pilot in `/sdd:migrate` |
| Mikado, revert on cascade | Rule 7; `BEHAVIOUR_CHANGE`; failed waves reverted |
| Readiness bar | Rubric R1 to R10 in `/sdd:productionize` |
| Claims backed by numbers | `evidence.py compare` table in every PR, regressions block publishing |

## Ideas for later

Kept on purpose, not dropped for fit. Each could become a gate, a mode or its own skill.

1. **Differential fuzzing gate**: generate inputs (Hypothesis, fast-check) and compare old and
   new implementations automatically, as a `--differential` step in `/sdd:migrate`.
2. **Shadow traffic for services**: replay recorded production requests against old and new
   (GoReplay, Diffy-style comparison) before cutting over a strangler-fig slice.
3. **Architecture fitness functions**: dependency rules (dependency-cruiser, import-linter,
   ArchUnit) that fail when a module boundary is crossed, run as a configured command and
   gated through `METRIC`.
4. **Code-health trend**: complexity, churn and hotspot analysis (lizard, git log churn, in the
   spirit of CodeScene) to choose *where* to refactor first, as a `--hotspots` report.
5. **Stacked PRs per wave** for large migrations, so each wave is reviewed and merged on its own.
6. **Mikado graph artefact**: record the prerequisite tree in `.review/` as the run discovers it,
   so a stopped migration resumes from the graph.
7. **Production evidence after merge**: DORA change-failure rate and error-rate deltas after a
   deploy, linked back to the PR, closing the loop from "evidence before merge" to "evidence in
   production".
8. **A `/sdd:refactor` skill** for plain structural refactors that are neither a PoC hardening
   nor a migration (extract module, remove duplication), reusing the same labels and evidence.
9. **Approval-test helpers per stack** in templates, so `characterize` produces consistent golden
   files with scrubbers for time and ids.
10. **Evidence history**: keep snapshot summaries per merged PR (outside `.review/`) to plot a
    repository's coverage and mutation score over time.
