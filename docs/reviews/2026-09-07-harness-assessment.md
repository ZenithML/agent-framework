# Harness assessment — September 2026

**Reviewer:** external (Claude, session-scoped) · **Subject:** this repository's pre-release history
· **Companion repo:** a separate, private harness repository (referred to below as the *shared
harness*)

A structural review of this harness against the vocabulary that emerged for agentic systems in
mid-2026 — *harness*, *loop*, and *graph* engineering — plus the defects that review surfaced
and the fixes applied on this branch.

The three terms are recent labels for practices that predate them. LangChain, whose framework
the graph label sells, opened its own response by calling it *"the latest term to come out of
X's AI content factory."* They are used here because they name three real design layers
cleanly, not because the vocabulary is settled.

---

## 1. What this harness is, in those terms

| Layer | Question it answers | What this repo has |
|---|---|---|
| **Harness** | What *can* an agent do in one turn? | `.claude/sdd/config.json` + JSON Schema placeholder seam · plugin packaging · doc templates · the three-layer standards model · SessionStart hook |
| **Loop** | When does it stop, and on what evidence? | TDD red→green→refactor per task · critic loops embedded in spec and plan · code critique after each task · QA cycles — **each with an iteration budget and a named escalation path** |
| **Graph** | Which paths are permitted, and who sees what? | `architect` supervising six specialists · context isolation between stages · a documented state-transition table · a human approval gate that `--autonomous` bypasses |

The layers are **nested, not ranked**: a loop runs inside a harness, and a graph is made of
nodes whose interesting members are loops. Moving outward buys capability and charges
coordination cost, so the operative question is never "which stage are we at" but "what is the
cheapest layer that holds this problem".

### 1.1 This architecture is L2, well executed

A supervisor that runs stages in sequence and routes failures back to itself with cycle
counters **is a loop**. The distinction that matters is not topology but *how the control flow
is represented*:

- A **loop** is one control cycle with budgets and stop conditions, enacted by a model
  following instructions.
- A **graph** is control flow declared *as data* that a runner traverses — which is what makes
  the topology inspectable and non-sequential shapes (fan-out, joins) expressible at all.

`agents/architect.md` holds its transition table in prose. That is a loop *documented* in graph
shape. Applying the parallelisation test to every edge in the pipeline returns the same answer
each time — the planner's output determines what the executor does, the executor's output
determines what the critic reviews, the critic's verdict determines whether the tester runs —
so **nothing in the pipeline runs in parallel and there is no fan-out anywhere in it.**

That is not a criticism. It is the correct layer for this problem, and it means the graph
machinery here is buying two things, both of which are loop properties:

1. **Context isolation** — each stage receives only what it needs.
2. **Retry routing with budgets** — REVISE → executor (max 2), FAIL → executor (max 3), then
   escalate.

The practical consequence: **do not invest in declarative-topology machinery.** Earn it the
first time three tasks genuinely want to run concurrently *and* those branches do not need each
other's context.

### 1.2 Two decisions here are ahead of the published guidance

**The sealed verifier.** `agents/tester.md` tests observable behaviour against declared
scenarios and its frontmatter declares no `Read`, no `Grep`, and no `Glob`. That is the
mitigation the literature arrives at for the most dangerous failure in this layer, reached
independently here. Published work on self-improving agents that authored both their policy and
their own tests found, across 35 model/task combinations, **every run self-scoring at or above
0.70 while 15 performed below random** and six sat at the benchmark floor. The seal — the judge
cannot see what it judges — is what prevents that.

Critically, the seal is **enforced at the tool layer, not in prose**. That is the right place:
"pass only the Test Scenarios section" is an instruction a model can exceed, whereas a tool that
is not declared cannot be called. See §2.1 for the two gaps in that enforcement.

**Externalised task state.** `tasks.md` as the unit of progress, plus per-task commits, is the
pattern Anthropic landed on after finding that *"compaction isn't sufficient"* for long-horizon
work. Compaction manages the context window; only external state manages the task.

### 1.3 What the standards layer gets right

`standards/harness.md` contains the most original material in either repository: the
cross-reference taxonomy. The four-way split — a navigational pointer works, a sub-detail
reference inside an active step works, delegating a whole step fails, and a passive system
prompt cannot orchestrate skills — is stated more precisely here than in any public source
found during this review, and it was evidently derived from real regressions rather than
theory.

`AGENTS.md` as a routing map that contains no rules is the other one. An ETH Zurich study found
LLM-generated agent instruction files *harmed* task performance while costing **20%+ more
tokens**, with well-designed human-written files delivering only ~4% improvement. A thin
routing table is the correct shape, and this repo reached it on reasoning.

---

## 2. Findings

Ordered by consequence. Fixes for F1–F5 are applied on this branch; F6 and F7 are recorded for
a decision.

### 2.1 F1 — One agent declares no tools at all (fixed)

`agents/planner.md` had no `tools:` key, so it inherited every tool available to its caller.
It is also the agent that authors `design.md`, including the QA Scenarios the sealed verifier
later checks. The least-restricted agent in the pipeline was the one writing the acceptance
criteria.

**Fixed:** explicit `tools:` on the planner, and a `role:` on all seven agents so the
declarations can be checked against a contract rather than read as prose.

### 2.2 F2 — Nothing prevented the seal from being removed (fixed by contract; gated on the next branch)

The tester's isolation rests entirely on the absence of three entries from a list. A future edit
adding `Read` to that list would unseal the verifier silently, with no test failing and no
reviewer necessarily noticing. The property with the highest cost of failure had the least
protection.

**Fixed:** each agent now declares a `role:`, and roles carry tool contracts —
`verifier` forbids every file-read tool, `reviewer` forbids every write tool. The gate that
enforces this arrives on the following branch.

### 2.3 F3 — Acceptance criteria can move to fit the implementation (fixed)

The planner authors the QA Scenarios; on `DESIGN_GAP` the architect routes back to the planner,
which may revise them. That is one seam where the test can shift to accommodate the code — the
co-evolution configuration the reward-hacking result describes, reachable through a legitimate
control path.

**Fixed:** `standards/agent-pipeline.md` now states that acceptance criteria are frozen at
design approval, and that a re-plan may change them only as an explicit, recorded decision —
never as a side effect of a retry.

### 2.4 F4 — Three skill descriptions are byte-identical to the agent they dispatch (fixed)

The description is the only text a model reads before deciding what to load. Where a skill and
its agent carry the same string there is no signal to discriminate:

| Skill | Agent | Before |
|---|---|---|
| `audit` | `archivist` | identical |
| `qa` | `tester` | identical |
| `publish` | `publisher` | identical |
| `architect` (skill) | `architect` (agent) | near-identical |

Compounding it, no stage skill stated what does *not* trigger it, and several opened by telling
the reader to use `/ship` instead — a skill whose first line is a redirect.

This matters *because* modular stage invocation is a deliberate requirement here, not an
accident. Both surfaces should exist; they simply have to be distinguishable. The two are
selected by different mechanisms and so want different wording: a **skill** description is read
by a model choosing what to do with free-text input and needs triggers plus a boundary; an
**agent** description is read by a caller that has already decided to spawn it and needs
capability plus contract.

**Fixed:** every stage skill now carries a distinct description with an explicit *"Does not
trigger"* clause naming the pipeline path; agent descriptions were reworded as contracts.

### 2.5 F5 — The verifier keeps `Bash`, and `Bash` can read source (documented, not closed)

`tester` declares no file-read tool, but it does declare `Bash` — which it needs in order to
start a dev server, and which can `cat` any file. The seal is therefore strong but not absolute.

The honest ranking of enforcement strength:

1. A prompt rule — weakest.
2. An agent's `tools:` list — real, because an undeclared tool cannot be called.
3. The environment — actual enforcement: if the source is not on disk where the agent runs,
   nothing can reach it.

The tester sits at level 2 with one documented hole. Closing it properly means running
verification against a built artifact in a directory without sources, which is a pipeline change
rather than a declaration change.

**Applied:** the hole is now recorded as a declared, accepted residual risk in
`standards/harness.md`, with the condition that would close it — rather than left as an
unexamined gap behind a prose rule that reads as absolute.

### 2.6 F6 — The enforcement layer is absent (recorded; addressed on the following branch)

This repository's own `docs/specs/harness-quality/requirements.md` states the finding better
than this review could: *"The content layer of this harness is strong. The enforcement layer is
almost entirely absent."* And: **"A rule enforced by asking an agent to remember it is a
preference."**

Concretely, at the time of review: CI had one workflow and it only tagged releases; nothing ran
on a pull request; `/sdd:lint-harness` was documented as a manual step; and `claude plugin
validate --strict` had never run, so an invalid `skills` array shipped in `plugin.json`
undetected.

Worth noting as a pattern rather than an incident: the same diagnosis — strong guides, absent
sensors — independently applies to the shared harness repository, whose linter accepts
`version: banana`, `updated: not-a-date`, a missing manifest, and an evaluations file whose
every scenario is `TODO`. Two codebases, same author, same gap, neither informing the other.
That is a systematic bias worth knowing about, and it is why the following branch puts gates in
place *before* the rules they enforce accumulate further.

### 2.7 F7 — Distribution plumbing dominates the change history (recorded, no fix proposed)

**36 of 62 commits** touch install, vendor, marketplace, `plugin.json`, or settings plumbing —
58% of the repository's history spent on the delivery mechanism rather than the pipeline, the
agents, or the standards. The repo's own spec calls the install path untested and flags the
no-clobber case as *"the data-loss case."*

No fix is proposed because this is a scope decision, not a defect. If the primary consumer is a
repository that clones the harness, the marketplace and both installer scripts are removable and
the maintenance saving is the largest single item available. If plugin distribution is genuinely
required, the install path needs the CI fixture coverage the harness-quality spec already
specifies (T2.1–T2.6) before it reaches another consumer.

---

## 3. Fixes applied on this branch

| # | Change | Files |
|---|---|---|
| 1 | `role:` on all seven agents; explicit `tools:` on `planner` | `plugins/sdd/agents/*.md` |
| 2 | Distinct descriptions with a *"Does not trigger"* clause on every stage skill | `plugins/sdd/skills/*/SKILL.md` |
| 3 | Agent descriptions reworded as contracts rather than triggers | `plugins/sdd/agents/*.md` |
| 4 | Acceptance criteria frozen at design approval | `plugins/sdd/standards/agent-pipeline.md` |
| 5 | Verifier seal, role contracts, and the declared `Bash` residual risk | `plugins/sdd/standards/harness.md` |
| 6 | Cross-reference rule extended to whole files, not only numbered steps | `plugins/sdd/standards/harness.md` |
| 7 | Version bump in both manifests | `plugin.json`, `marketplace.json` |

Item 6 closes a scope bug worth naming on its own: `/sdd:lint-harness` step 2 iterates *numbered
steps* looking for one whose only content is a pointer. The eight stage-dispatch skills have no
numbered steps — the whole file is the reference — so the anti-pattern this harness identified
from its own regressions was invisible to the check written for it. The standard now
distinguishes legitimate **dispatch** (a skill that parses arguments and hands off to an agent
carrying the contract) from **step delegation**, so the rule covers files without rejecting the
modular entry points.

## 4. What the following branch adds

`feature/enforcement-layer` ports the gate set built for the shared harness, adapted to this
repository's layout and conventions:

- Layout-aware discovery — `plugins/*/skills/**` and `.claude/skills/**`.
- A **coverage ratchet** rather than a flag day: stricter rules apply to the skills listed as
  covered, and the list may only grow. Nineteen skills cannot adopt a seven-field frontmatter
  schema in one commit, and pretending otherwise produces either a red pipeline everyone learns
  to ignore or a gate nobody turns on.
- `claude plugin validate --strict` on both manifests, which this repository has and the shared
  harness does not.
- The two agent gates that make F1 and F2 mechanical.
- A negative-control fixture per gate. A gate that has never rejected anything is not known to
  work.

## 5. Recommendations not addressed by either branch

1. **Decide F7.** The 58% figure is the strongest argument in this review for a scope cut.
2. **Write the two remaining mechanisable rules as gates** — the 500-line body cap and
   version-bump-on-change. Both are currently `judgment` and neither needs to be.
3. **Record the incident behind the cross-reference rule.** `standards/harness.md` says
   *"Several regressions have been caused by…"* — that sentence is the only surviving trace of
   the most valuable rule in this harness. The ADR template ships here and has never been used.
4. **Do not build the declarative graph.** Revisit only when a genuine fan-out appears.

---

<details>
<summary>Review method and limits</summary>

Findings were verified by execution, not by reading alone: the shared harness's linter was run
against deliberately malformed fixtures to establish which of its documented rules actually
bind, agent frontmatter was parsed to confirm tool declarations, and commit classification for
F7 was counted rather than estimated.

Limits worth stating. No independent third-party benchmark compares agent topologies against
each other on a common task, so every performance figure cited here is either vendor-supplied or
a single organisation's internal evaluation; treat them as order-of-magnitude, and measure on
this harness's own workload before relying on any of them. Three widely circulated numbers were
excluded as untraceable to a primary source: a claimed 6× time-horizon jump in frontier models,
a "70% of agent performance lives outside the model" figure, and a set of unsourced 30–50%
harness-impact percentages. The harness/loop/graph taxonomy itself is a teaching frame
constructed by practitioners in mid-2026 and has not been independently validated; the
mechanisms underneath it are well evidenced and considerably older than the labels.

</details>
