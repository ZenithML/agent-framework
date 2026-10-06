# DeepSeek Harness — What They Do Right, and What a Good Harness Repo Should Have

Research report. Subject: [`deepseek-ai/deepseek-harness`](https://github.com/deepseek-ai/deepseek-harness) (`dsh`), MIT, ~121k stars, developer preview. Read at `master` on 2026-08-16.

This report has two parts:

- **Part 1** — what DeepSeek Harness does right, with the specific mechanism in each case.
- **Part 2** — a general rubric: what any good harness repo or plugin should have, extracted from Part 1 and stated so it can be scored.

Part 3 is the gap read against this repository; the actionable version lives in [`docs/specs/harness-quality/`](../specs/harness-quality/requirements.md).

---

## Part 0 — What `dsh` actually is

A Node.js agent harness built on vendored [Cordis](https://github.com/cordiverse/cordis), a dependency-injection/plugin runtime. The tagline is literal: **everything is a plugin** — the model adapter, the tool registry, the session log, and the agent loop itself are all plugins mounted into a shared context, so every part is replaceable from configuration.

Scale of the repo: ~40 package groups under `packages/`, a Python SDK, a native addon, 15 CI workflows, ~97 scripts in `scripts/` (most with a paired `.spec.ts`), 11 repo-local agent skills, a bilingual documentation website, and a frozen decision-record archive.

It is not a Claude Code plugin and not spec-driven. So the value to us is **not** the domain — it is the *repository engineering* around an agent system, which is directly transferable.

---

## Part 1 — What they do right

### 1.1 One extension mechanism, and no privileged core

> "There is no privileged core to patch: you extend dsh by mounting a plugin beside the others, and registrations are effects that unwind when their plugin unloads."

Three properties make this real rather than aspirational:

1. **Registrations are effects.** Every contribution goes through `ctx.effect()` / `ctx.on()`, and a registry's `register()` returns the disposer. Adding a thing and removing a thing are the same code path, so hot-reload and teardown are correct by construction rather than by discipline.
2. **A documented extension-point table.** `docs/architecture.md` ends with a *"Where new behavior goes"* table — 17 rows of `Goal → Mechanism` ("Add a model provider → register its adapter on `ctx.llm`", "Intercept a request, tool, or turn → use its `agent/*` or `tools/*` event"). This is the single highest-leverage artifact in the repo: it converts "where do I put this?" from a judgment call into a lookup.
3. **A rule that keeps the table honest.** From root `AGENTS.md`: *"Plugins, not loop changes: new behavior goes on documented extension points; changing `agent-loop` requires updating docs/architecture.md."* The map cannot silently drift from the territory, because changing the territory is defined as requiring a map edit.

**The lesson:** an extension-point table plus a rule that changing the core requires updating the table.

### 1.2 Capability seams — a swap unit that is never half-defined

A **seam** is a swappable capability with exactly three roles: a **Service Definition** (the interface), a **Service Provider** (an implementation), and a **Consumer** (usually a model-facing tool). The rule is stated as a completeness constraint:

> "A capability seam comprises Service Definition / Service Provider / Consumer roles. It is complete, never one role; split only when roles evolve independently."

The payoff they name explicitly: filesystem and subprocess providers share one execution world, so *pointing them at a remote sandbox moves Bash, PTY, and LSP with them, with no provider forks*. One swap, whole-product effect.

This is the structural answer to the most common harness failure — the near-duplicate fork. When a second environment needs slightly different behavior, a seam gives you a second provider; the absence of a seam gives you a copy of the pipeline that then drifts.

### 1.3 Composition is layered, declarative, and introspectable

A running `dsh` is a plugin tree composed at boot from ordered layers: each **bundle** in the **profile**'s order → the profile's `cordis.patch.yml` → the home-level patch → any `--patch` overlay. A patch targets a row by id and replaces its config or inserts new rows.

And critically:

```sh
dsh --profile web --dump-config
```

> "To see the tree your machine actually boots... Any row it prints can be replaced by a patch of your own."

Layered config is common. **A first-class command that prints the fully-resolved composition** is not, and it is what makes the layering debuggable instead of mystifying. Any harness with config precedence rules owes its users this command.

### 1.4 The load-bearing runtime invariant: model-visible ⟺ logged

> "Anything that reaches a model request must be reconstructable from the session log, and a runtime invariant asserts it. This is why a new model-visible input requires a new session event."

One rule, and it buys: replay, fork, resume, transcripts, telemetry, snapshot testing, and debuggability — all derived from a single append-only stream rather than each built separately. It is also *enforced at runtime*, not just documented.

Note the shape of the rule: it constrains **what may reach the model** by tying it to **what is durably recorded**. Any harness that assembles prompts from multiple sources needs some version of this, or it will eventually have context it cannot explain.

They pair it with a taxonomy of where invariants may look: *"Runtime invariants assert owned relationships. Check authoritative event streams or mutable data, not service or method presence, plugin metadata or effects, or fixed pure examples."* — i.e. an invariant must assert a *relationship that could actually be violated*, not the tautology that a thing was registered.

### 1.5 Agent-facing documentation is an engineered artifact with a budget

This is where `dsh` is furthest ahead of normal practice, and it is the most portable part.

**A tier taxonomy with one home per fact.** `docs/AGENTS.md` carries a table of twelve tiers, each with a *Job* column and — the part everyone omits — a **"Does NOT belong there"** column:

| Tier | Job | Does NOT belong there |
|---|---|---|
| Root `AGENTS.md` | Standing orders: rules needed in context every session, one to three lines each, linking its home | Stories, worked examples, situational procedures, anything restated from a linked home |
| `architecture.md` | Ordered map: composition, core packages, loop, seams, extension points | Type definitions, per-package detail, decision rationale, implementation-status annotations |
| Agent Notes | Active decision records: the why and what-was-given-up | Migration plans, acceptance checklists, spec-speak once shipped |
| Postmortems | Incident stories — the only tier where war-story narrative belongs | — |
| Cookbook | Step-by-step how-tos with numbered verify steps | Design rationale |
| Package README | The per-package contract: config, semantics, limitations, extension points | JSDoc restatement, generated-catalog restatement |
| Skills | Reusable workflows and specialized decision standards | Product and runtime contracts |

Placement then reduces to one line: *"bugs → postmortems; rationale → Agent Notes; procedures → cookbooks; type definitions → subsystems; package contracts → READMEs; standing orders → root AGENTS.md with a rationale link."*

**Word-count budgets, machine-enforced.** `scripts/doc-budgets.manifest.json` sets ceilings; `verify-doc-budgets` rejects excess *or missing* files. Root `AGENTS.md` ≤ 1,600 words; `architecture.md` ≤ 1,800; subtree `AGENTS.md` ≤ 600. When the gate goes red the procedure is ordered: **relocate → condense → raise the ceiling with justification in the PR.** And the framing is careful: *"Ceilings are guardrails, not reduction targets... A too-low ceiling is a budget bug."*

This is the correct model. An always-loaded instruction file is a **spend against every request's context window**, so it should have a budget like any other spend — and the budget should be defended by a script, not by a reviewer's mood.

**A named list of documentation anti-patterns — the "slop checklist".** Nine hunting targets, each mechanically greppable:

- The same rule stated in more than one home
- Narrated history: "previously", "now", "no longer", "used to", "renamed", "was moved"
- Implementation-status annotations in prose ("implemented!", "future: …") — *"status rots"*
- Hand-restated catalogs where a generator is authoritative
- Reasoning transcripts: step-by-step narration, proof of obvious branches, test walkthroughs
- Rationale repeated beside sibling methods instead of once at the owner
- Paragraph walls carrying several rules plus asides
- **Emphasis inflation** — *"bold, CAPS, or 'critically' everywhere means nothing stands out"*
- Spec-speak in shipped decision records

**Prose gates that a script can actually run.** `verify-md-links` (rejects missing targets *and* dead `#fragment` anchors), `verify-md-wrap` (one physical line per paragraph — makes prose diffs reviewable), `doc-typecheck` (fenced `ts` blocks must compile), `verify-type-equiv` (a type pasted into docs is registered in a manifest so it cannot drift from source), `verify-export-jsdoc`.

**And a symlink instead of a copy.** *"`CLAUDE.md` symlinks `AGENTS.md` at root, `packages/`, and `examples/`; edit the real file."* Multiple agent vendors, one source of truth, zero drift.

**Terminology discipline.** A genuinely unusual rule, and a good one:

> "Before writing `contract`, `boundary`, or `shape`, ask whether a more exact term names the subject: write `response fields`, `JSON validation`, or `ESM exports` instead of `response shape`, `validation boundary`, or `module shape`."

### 1.6 Decision records with a lifecycle, a closed taxonomy, and a mandatory losing side

**Agent Notes** live at `.agents/notes/{lifecycle}/{class}/yyyy-mm-dd-topic-title.md`.

- **Lifecycle** is the folder: `proposed/`, `implemented/`, `rejected/` — and a note *moves* as its status changes.
- **Class** is a closed set enforced by a gate (`scripts/agent-note-tree.ts`): `feature`, `bug-fix`, `simplification`, `architecture`, `process`, `testing`. Adding a class requires updating the canonical set and the doc. (`refactor` is *deliberately absent*, with the reasoning recorded: it overlaps `simplification`, whose discriminator — "does observable behavior change?" — already covers it.)
- **The in-file skeleton is gate-enforced per lifecycle.** `proposed/` gets `## Problem / ## Proposal / ## Alternatives considered / ## Acceptance criteria / ## Risks`. `implemented/` gets `## Problem / ## Decision / ## Alternatives considered / ## Consequences` — and the gate **rejects** `## Proposal`, `## Plan`, `## Migration plan`, `## Acceptance criteria` in an implemented note. Moving folders means rewriting the skeleton in the same change.
- **`## Alternatives considered` is mandatory,** with the reason stated: *"A decision recorded without what it beat invites re-litigation — the failure Agent Notes exist to prevent."* Alternatives are *recorded, never invented*; pre-format notes carry an explicit machine-recognised comment instead of a fabricated section.
- **The rule with teeth:** *"Every non-trivial change MUST add or update at least one Agent Note in the same PR."* Only purely mechanical edits are exempt.
- **`implemented/` notes are kept current with shipped reality** — when code later renames a package or changes a default, the note is updated *in the same change* (facts only, never the decision).
- **The archive is frozen.** Archived triplets are sealed with sidecar hashes and an append-only manifest; gates skip them; *"never edit or treat them as current authority."* Cross-links are relative markdown paths, never numbers, so they survive folder moves and are mechanically checkable.
- **No centralized index** — deliberately, with a decision record owning that rationale. The folder tree *is* the inventory.

The design insight worth stealing: **status is encoded in the path, not in a field**, so "what is proposed vs shipped vs rejected" is answered by `ls`, and moving a decision through its lifecycle is a `git mv` that a gate then forces you to finish properly.

### 1.7 Postmortems as a separate tier, wired into rules

`docs/postmortem/` is explicitly *not* the decision-record tier:

> "A post-mortem is NOT an Agent Note... It is a backward-looking record of a failure: what broke, the mechanism, why every safety net missed it, and the concrete guardrails added so the same class of bug fails loudly next time."

The write-it-or-not test is three-pronged and useful verbatim: **subtle** (a careful engineer would re-derive it the hard way) + **systemic** (it escaped through a gap in tests/tooling/conventions, not a typo) + **costly to rediscover**. Each opens with a thirty-second Executive summary.

Then `docs/defensive-patterns.md` converts incidents into rules:

> "Each pattern below is a class of defect that actually shipped or nearly shipped here, stated as the rule that prevents its recurrence."

Seven rules, each a real bug class — "Report orthogonal outcomes independently" (a process can time out *and* exit 0), "Dispose must reach quiescence, not just request it", "Contain callback exceptions in the dispatcher", "Never hand untrusted output the ambient environment or predictable paths", "Unlink link-shaped paths".

**The complete loop is visible in the repo**, and it is the thing to copy:

```
postmortem 0001 (ACP server crashed: `export default` dropped the plugin's `inject`)
  → rule in packages/AGENTS.md   ("service packages default-export their service class;
                                   function plugins named-export name/inject/Config/apply
                                   and have no default export")
  → test requirement in examples/AGENTS.md  (every example ships a *keyless* Loader smoke
                                             that boots the real cordis.yml)
  → and a negative-control mandate in docs/testing.md ("introduce the regression,
                                                        watch red, revert")
```

Incident → rule → gate → proof the gate fires. Most repos stop at the first arrow.

### 1.8 Testing stated as policy, with the agent-specific traps named

`docs/testing.md` defines five tiers with distinct jobs — unit, the coverage gate (`test:coverage`, per-file 100% on `packages/*/*/src`), real-API e2e, keyless snapshot, browser snapshot — and then states the rules that keep a green suite meaningful. The four that generalize to any agent harness:

**"Verify the world, not the self-report."**
> "An e2e assertion re-runs the command or re-reads the file externally; a keyword probe on the agent's own output lets a cheating agent pass. Assert untouched files are byte-identical."

This is *the* agentic testing insight. An agent that says "✅ done" is not evidence; the filesystem is.

**"Test the real entry path."**
> "'Real entry path' means the published artifact: a package `bin` runs built `lib/bin.js` under plain `node`, exposing failures tsx masks."

Test what ships, in the way it ships, not a convenient in-process approximation.

**"Prefer the real implementation over a mock."** Mock only the expensive or non-deterministic boundary (LLM adapter, network, clock); keep everything downstream real. *"A hand-rolled stand-in proves the bridge moves bytes, not that the shipping tool behaves as asserted."*

**Snapshot obligation tied to visibility.** *"Every non-trivial model-, protocol-, or human-visible change adds or updates a keyless scenario in the same PR through a runnable example's owning snapshot suite."* If a change alters what the model or the user sees, the assembled transcript must move too — package tests do not substitute.

Two more worth noting:

- **Coverage framing:** *"An uncovered line is often dead code the gate is correctly flagging for deletion, not a missing test to bolt on."* And immediately: *"Line coverage is necessary, never sufficient."*
- **Cost framing:** *"We are DeepSeek — do not ration real-API tests... A no-key test proves plumbing; only a with-key run proves the agent works against a real model."* Suites self-skip without a key so keyless CI and outside contributors stay green — *"Self-skip keeps secretless CI and keyless contributors unblocked; it is not a cost signal."*

### 1.9 Gates: ~97 scripts, and the gates themselves are tested

`scripts/` holds roughly 97 files, and the striking detail is how many have a paired `.spec.ts` — `run-gates.spec.ts`, `package-invariants.spec.ts`, `publint-all.spec.ts`, `ci-workflow.spec.ts`, `archived-agent-notes.spec.ts`, and so on. **The enforcement layer is itself under test**, because a silently-broken gate is worse than no gate: it manufactures false confidence.

The governing principle from root `AGENTS.md`:

> "Wire mechanically checkable invariants into an executed top-level gate and prove each changed acceptance path rejects an invalid case."

Two obligations in one sentence: (a) if a rule can be checked by a machine, it *must* be, and it must run from a top-level aggregate (`pnpm run doc-sync`, `pnpm run check:all`); (b) you must demonstrate the gate **rejects** something — a negative control.

**Local hooks are deliberately narrow.** Lefthook pre-commit fixes staged lint, checks staged whitespace, guards vendor metadata; pre-push runs *only* the incremental typecheck. Everything exhaustive belongs to CI:

> "Never default to the full suite or repeat a passing check for commit or push. CI owns exhaustive coverage and the platform matrix."

And the selection rule: *"Match evidence to the surface: focused tests for behavior, snapshots for model or user output, `doc-sync` for docs, build/hygiene and built smokes for published paths, and real-API e2e for provider behavior."* A per-diff evidence policy, not a reflex.

### 1.10 Repo-local agent skills that encode *maintainer procedure*, not product features

`.agents/skills/` holds eleven skills, and note what they are:

`dsh-pre-push-checks` · `dsh-code-review` · `dsh-doc-standards` · `dsh-prose-standard` · `dsh-find-simplifications` · `dsh-archive-agent-notes` · `dsh-merging-stacked-prs` · `dsh-translate-docs` · `dsh-doc-site-sync` · `dsh-trim-cot-leakage` · `record-browser-gif`

Every one is a **procedure a maintainer would otherwise hold in their head**. The doc tier table bounds them explicitly: *"Skills: reusable workflows and specialized decision standards. NOT product and runtime contracts (→ docs or source)."*

Four qualities of these skills are worth copying directly:

1. **Trigger-shaped descriptions.** `dsh-pre-push-checks`: *"Use before pushing, force-pushing, marking ready for review, or claiming checks pass on a deepseek-harness branch, and immediately after `gh stack sync` publishes rewritten branches, to select the smallest tests and checks that cover the outgoing diff without reflexively running the full repository suite."* The description enumerates *situations*, and it names the failure mode it exists to prevent.
2. **Honest about their own authority.** `dsh-code-review` opens: *"This skill is guidance, not a complete checklist."* It then separates **Sources of truth** → **Blocking requirements** (6, numbered) → **Manual checks** (14 bullets, each a semantic check no gate can do) → **Reporting findings**. Skills that pretend to be exhaustive get followed mechanically and miss everything else.
3. **Evidence discipline as explicit instruction.** *"report only commands run"* · *"Report pending checks as pending"* · *"Do not push and hope CI differs"* · *"Require sandbox evidence; never bypass genuine test failures"* · *"Do not claim the sync made the stack ready merely because the command succeeded."* These are guardrails against the specific way agents fail — narrating success they did not verify.
4. **They delegate the mechanical half to a script.** `dsh-pre-push-checks` doesn't ask the agent to eyeball the diff; it runs `pnpm --silent run change-scope --base <verified-base-ref>`, which emits versioned JSON separating committed / staged / unstaged / untracked paths. *"The command never guesses or fetches a base."* The skill spends its judgment on **selecting evidence**, not on computing facts a script computes better.

### 1.11 Rule-writing craft in `AGENTS.md`

Root `AGENTS.md` is ~1,500 words and carries ~30 rules. The format is consistent: **bold lead-in naming the rule → one or two sentences of content → a parenthetical link to the rationale's home.** Self-contained enough to act on, short enough to always be in context, linked so the *why* is one hop away.

A sample, because the content is as instructive as the form:

- **"Misconfiguration fails loud"** at load when self-contained, otherwise at the earliest resolvable point; never silently skip a missing referent.
- **"No hardcoded tunables in plugins"** — deployment-varying choices are validated `Config` fields changeable from config; *"a `DEFAULT_*` constant or test hook is not configurability."*
- **"Explicit > implicit at package boundaries"** — defaulting is an explicit `resolve(request): Spec` step, *"never a hidden `?? default` inside `run()`."*
- **"Trust TypeScript at typed same-process boundaries."** Do *not* add runtime validation or hostile-input tests for values the static interface requires; validate at parser/config, queued, model/tool JSON, durable/file, worker, process, and wire boundaries. — Notable because it is an **anti-defensive-programming rule with an explicit list of where defense *is* required**. Most repos only ever write the "validate everything" half and then drown in redundant checks.
- **"An empty `catch` names what it swallows"** and why nothing else can reach it; keep the `try` to one statement.
- **"Tests describe behavior, not correctness."** Change obsolete behavior with its tests; explain why in the PR.
- **"Prefer symmetry for parallel values"** — unexplained asymmetry usually signals a missed extraction.
- **"Choose PR history deliberately."** Rewrites use `--force-with-lease`, abort on remote movement, **never raw `--force`**.

### 1.12 Honest project stance, with an expiry date on the honesty

Two governance moves worth copying.

**A pre-release stance section that schedules its own deletion:**

> "**Remove this section at the first tagged release.** With no external consumers, prefer the correct foundation over compatibility shims: rename or repackage freely and update every reference together. Backends reject old on-disk formats."

It states the current trade-off (correctness over blast radius), the condition under which it stops applying, and the concrete permissions it grants. Compare the usual alternative — an unstated assumption that everyone eventually disagrees about.

Alongside it, versioning that matches the stance: SQLite uses a monotonic `SCHEMA_VERSION`; `dsh-session` holds `SESSION_FORMAT_VERSION` at `0` **with an explicit no-compatibility promise**. The promise is written down, including when there isn't one.

**A CONTRIBUTING.md that tells the truth:**

> "We are sorry that we cannot accept external pull requests at the moment. However, contributing code to this repository is far from the only way to help."

...followed by real alternatives (report in Discussions, upvote, build a plugin, tag it `dsh-plugin`, write guides, answer questions), and this:

> "We do not believe that packages in the official repository are inherently more important than packages created by the community. You may consider this repository an idea, an official showcase, and a source of inspiration, but not a mandate from us."

For a plugin-first architecture this is the correct posture, and it is *structurally* backed: because everything is a plugin, a community package genuinely is a peer of an official one. The ecosystem hook is one line — a GitHub topic — and it already produced a third-party `awesome-deepseek-harness` index.

### 1.13 Things they do that we should *not* copy

Not everything here generalizes:

- **Per-file 100% coverage** is affordable because inference and headcount are cheap for them. For a docs-and-prompts plugin it would be theatre.
- **~97 gate scripts** is proportional to a 40-package TypeScript monorepo. Our equivalent is closer to six.
- **Bilingual pairing with hash records and a custom git merge driver** is real machinery for a real requirement we don't have.
- **No external PRs.** A defensible choice at their scale and velocity; the opposite of what a small internal harness wants.
- **Stacked PRs with `gh stack sync`.** Powerful, and a large process surface — note that they needed a whole skill (`dsh-merging-stacked-prs`) plus a post-sync validation protocol to make it safe.

The transferable core is the *shape*: tiered docs with budgets, path-encoded decision records with mandatory alternatives, postmortems feeding rules feeding gates, testing tiers with world-verification, and skills that encode maintainer procedure while delegating computation to scripts.

---

## Part 2 — What a good harness repo / plugin should have

A rubric. Ten pillars; each has a *why*, and checklist items stated so they can be answered yes/no.

### Pillar 1 — A stated architecture with exactly one extension mechanism

*Why:* If there are two ways to add behavior, contributors will use both, and neither will be maintained.

- [ ] One named unit of extension (plugin / skill / stage / provider), defined in one document
- [ ] A **`Goal → Mechanism` extension-point table** — the reader looks up their goal and finds where the code goes
- [ ] A rule that **changing the core requires updating that table** in the same change
- [ ] Registration and deregistration are the same code path (add returns remove), so teardown is correct by construction
- [ ] The document is named as required reading before touching the core

### Pillar 2 — Seams, so variants are providers instead of forks

*Why:* The dominant failure mode of harnesses is the near-duplicate pipeline that drifts.

- [ ] Swappable capabilities are identified and named
- [ ] Each seam is defined by all of its roles (interface / implementation / consumer) — a partial seam is not a seam
- [ ] A rule that a second environment gets a **provider**, not a copy of the pipeline
- [ ] Any existing near-duplicate is listed as known debt with a seam that would resolve it

### Pillar 3 — Introspectable composition

*Why:* Layered configuration without a resolver dump is a source of unfalsifiable bug reports.

- [ ] Layer precedence is documented as an ordered list
- [ ] A **`--dump-config`-equivalent** prints the fully-resolved composition actually in effect
- [ ] Every resolved row is addressable by the override mechanism (no unpatchable rows)
- [ ] **Misconfiguration fails loud** at the earliest resolvable point; a missing referent is never silently skipped
- [ ] No hardcoded deployment-varying tunables — those are validated config fields

### Pillar 4 — Agent-facing docs as a budgeted, tiered artifact

*Why:* Always-loaded instructions are a per-request spend against context. Unbudgeted, they grow until the important rules are invisible.

- [ ] A **doc tier table** with a *Job* column **and a "does NOT belong here" column**
- [ ] A one-line placement rule (`bugs → X; rationale → Y; procedures → Z`)
- [ ] **One home per fact**; everywhere else links
- [ ] **Word budgets on always-loaded files**, enforced by a script, with an ordered escalation (relocate → condense → raise ceiling *with justification*)
- [ ] Machine-checkable cross-links only — relative paths, and a gate rejecting dead targets *and* dead anchors
- [ ] A named **anti-pattern / "slop" checklist** for docs, greppable
- [ ] Rules are written as: **bold name → one or two sentences → link to rationale**
- [ ] Multi-vendor entry points (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`) are **symlinks or generated**, never copies
- [ ] Docs state **current behavior, not change history** — no "previously/now/no longer", no status annotations that rot

### Pillar 5 — Decision records with lifecycle, closed taxonomy, and a mandatory losing side

*Why:* Undocumented decisions get re-litigated. Decisions documented without their alternatives get re-litigated *and* the re-litigation looks reasonable.

- [ ] Decision records exist and have a **home with a path-encoded status** (`proposed/` → `implemented/` → `rejected/`), so `ls` answers "what's shipped"
- [ ] A **closed class set**, enforced by a gate; adding a class is itself a documented change
- [ ] A **required section skeleton per lifecycle**, gate-enforced — including *rejecting* proposal-tense headings in a shipped record
- [ ] **`## Alternatives considered` is mandatory**, and alternatives are recorded rather than invented
- [ ] A rule that **every non-trivial change carries a decision record in the same PR**
- [ ] Shipped records are **kept factually current** with the code (paths, names, defaults) — the decision itself is never edited; it is superseded
- [ ] Superseded/low-value records are **archived and frozen**, never silently mutated, never cited as current authority

### Pillar 6 — Postmortems, and the incident → rule → gate loop

*Why:* An institution that fixes bugs but not the process that let them through re-ships the bug class.

- [ ] Postmortems are a **distinct tier** from decision records
- [ ] An explicit write-one test — **subtle + systemic + costly to rediscover**
- [ ] Each opens with a thirty-second **executive summary**; then mechanism, why every safety net missed it, and guardrails added
- [ ] A **defensive-patterns / anti-patterns document** where each rule is a bug class that actually occurred
- [ ] Every entry links **forward to the guardrail** it produced (rule, test, gate)
- [ ] Every non-obvious rule links **back to the incident** that motivated it

### Pillar 7 — Mechanical enforcement of every rule you claim to have

*Why:* An unenforced rule is a preference. Worse, it teaches contributors that rules are optional.

- [ ] **Every mechanically checkable rule has a gate.** If it can't be checked, say so and assign it to human review
- [ ] Gates run from a **top-level aggregate** command *and* in CI on every PR — not just a documented manual step
- [ ] **Gates are themselves tested**, with **negative controls**: plant the violation, watch it fail, revert
- [ ] Manifest / registry consistency is gated (declared entries ⇄ files on disk)
- [ ] Version-bump obligations are gated, not merely written in CONTRIBUTING
- [ ] Local hooks stay **narrow and fast**; CI owns exhaustive coverage and the platform matrix
- [ ] An **evidence-selection policy**: match the check to the surface the diff touches, rather than "run everything" or "run nothing"

### Pillar 8 — Testing tiers that verify the world

*Why:* For agent systems, the usual test pyramid misses the two failure modes that matter — the agent lying about success, and the shipped artifact behaving unlike the dev-mode one.

- [ ] Named tiers, each with a stated job and its own command
- [ ] **Verify the world, not the self-report** — re-read the file, re-run the command; never keyword-probe the agent's own output
- [ ] **Test the real entry path** — the published artifact, launched as users launch it
- [ ] **Mock only the expensive or non-deterministic boundary**; everything downstream is real
- [ ] **Snapshot/transcript coverage for model-visible and user-visible output**, updated in the same PR as the change
- [ ] Live-API tiers **self-skip without credentials**, so keyless CI and outside contributors stay green
- [ ] Coverage is framed as necessary-not-sufficient, and uncovered code is considered for deletion
- [ ] An **install / bootstrap smoke test** — if the product is installed into other repos, that install is exercised in CI

### Pillar 9 — Repo-local agent skills encoding maintainer procedure

*Why:* The knowledge that makes a maintainer effective is procedural, and it is exactly what an agent lacks.

- [ ] Skills exist for **maintainer procedures** (pre-push evidence, review, release, archiving), not only product features
- [ ] **Trigger-shaped descriptions** enumerating situations — and naming the failure mode the skill prevents
- [ ] Skills are **honest about authority** ("guidance, not a complete checklist") and separate **blocking requirements** from judgment
- [ ] Skills **delegate computation to scripts** and spend their tokens on judgment
- [ ] **Evidence discipline is written in**: report only commands actually run; report pending as pending; never claim success from a command exiting zero
- [ ] Execution-layer docs are **self-contained** — no step whose entire content is "see that other file"
- [ ] Deliberate duplication between execution-layer docs is **acknowledged and drift-gated**

### Pillar 10 — Governance, versioning, and ecosystem posture

*Why:* Consumers need to know what will break and what they're allowed to rely on; contributors need to know how to help.

- [ ] A **LICENSE**
- [ ] A **stated stability posture** — including "no compatibility promise" where that is the truth — with the **condition under which it changes**
- [ ] Versioning that a machine enforces (all manifests agree; behavior change ⇒ bump)
- [ ] A **changelog**, generated or maintained
- [ ] **Honest CONTRIBUTING**: what you accept, what you don't, and concrete alternative ways to help
- [ ] An **extension/ecosystem hook** — a topic, registry, or index — so third-party extensions are discoverable
- [ ] Issue/PR templates and a label taxonomy, if issues are how work arrives
- [ ] Docs describe the **shipped configuration**, and generated reference material is generated, not hand-restated

---

## Part 3 — Gap read against this repository

Scored against Part 2. Detail and remediation live in [`docs/specs/harness-quality/requirements.md`](../specs/harness-quality/requirements.md).

| Pillar | State | Headline gap |
|---|---|---|
| 1 · Architecture & extension points | ~ Partial | `standards/harness.md` defines layers well, but there is no `Goal → Mechanism` table for "how do I add a stage / gate / agent / config key" |
| 2 · Seams | ~ Partial | The clearest instance — `copilot-ship`, a flattened fork of `ship` for a second host — has since been deleted. What remains is minor: `gh` is assumed throughout with no VCS-host seam |
| 3 · Introspectable composition | ✗ Missing | Config resolution (`.claude/sdd/config.json` → auto-detect → defaults) is described in a preamble repeated in every skill; nothing prints the resolved values |
| 4 · Docs as budgeted artifact | ~ Partial | Good three-layer model and a real AGENTS.md routing contract; no tier table with exclusions, no budgets, no link gate, no slop checklist |
| 5 · Decision records | ✗ Missing | ADR template exists; `docs/INDEX.md` says "No ADRs yet". No lifecycle, no taxonomy, no mandatory alternatives, no rule requiring one |
| 6 · Postmortems → rules → gates | ~ Partial | `standards/harness.md` has a real anti-pattern table, but the incident behind it survives as one sentence ("Several regressions have been caused by...") with no record |
| 7 · Mechanical enforcement | ✗ **Weakest** | CI has exactly one workflow, and it only tags releases. `/sdd:lint-harness` was documented as *"no automated CI gate — this is a manual step."* Nothing ever ran `claude plugin validate`, so an invalid `plugin.json` shipped undetected (see below). Version-bump obligations and config-example validity remain ungated |
| 8 · Testing | ✗ Missing | No tests of any kind. The install scripts — the primary delivery path — have never been executed in CI |
| 9 · Skills | ✓ Strong | 19 skills, 7 agents, a genuine self-containment standard with a documented rationale. Closest to parity |
| 10 · Governance | ~ Partial | No LICENSE, no CHANGELOG, no stability statement, no issue/PR templates. Release automation exists and works |

**Found while writing this report.** `claude plugin validate . --strict` had never been run against this repository. It failed: `plugin.json` declared a `skills` array of `{name, source}` objects, but the field's schema is a string-or-array of *directory paths*, so the manifest was invalid and the declaration did nothing — Claude Code always scans `skills/` regardless. The field has been deleted and both manifests now validate. This is the gap-read in miniature: an official validator existed, was never wired to anything, and the repository had been shipping a malformed manifest.

**The one-line read:** the *content* layer of this harness is strong — the skills, the standards, and the three-layer model are well-designed and were clearly written from experience. The **enforcement** layer is almost entirely absent, so every rule currently depends on a human or an agent remembering it. That is the highest-leverage thing to change, and it is what the PRD leads with.

---

## Sources

- [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness) — `README.md`, `AGENTS.md`, `CONTRIBUTING.md`, `packages/AGENTS.md`, `examples/AGENTS.md`, `scripts/AGENTS.md`
- [`docs/architecture.md`](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/architecture.md) · [`docs/AGENTS.md`](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/AGENTS.md) · [`docs/testing.md`](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/testing.md) · [`docs/defensive-patterns.md`](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/defensive-patterns.md) · [`docs/development.md`](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/development.md) · [`docs/postmortem/README.md`](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/postmortem/README.md)
- [`.agents/notes/README.md`](https://github.com/deepseek-ai/deepseek-harness/blob/master/.agents/notes/README.md) — the Agent Notes standard
- [`.agents/skills/dsh-pre-push-checks`](https://github.com/deepseek-ai/deepseek-harness/blob/master/.agents/skills/dsh-pre-push-checks/SKILL.md) · [`.agents/skills/dsh-code-review`](https://github.com/deepseek-ai/deepseek-harness/blob/master/.agents/skills/dsh-code-review/SKILL.md)
- [Cordis](https://github.com/cordiverse/cordis) — the underlying plugin runtime
- [Dominic789654/awesome-deepseek-harness](https://github.com/Dominic789654/awesome-deepseek-harness) — the community index the `dsh-plugin` topic produced
- [The New Stack — "DeepSeek open sources an agent harness where everything is a plugin"](https://thenewstack.io/deepseek-harness-open-source-plugins/)
