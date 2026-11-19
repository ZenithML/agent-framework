# How the SDD harness works

A visual guide to the `sdd` plugin: how one sentence becomes a reviewed pull request, who does
each step, what each agent is allowed to see, and how the harness gets into (and stays current
in) your repositories. The diagrams are [Mermaid](https://mermaid.js.org/), so they render on
GitHub.

This page explains; it does not define. The procedure is
[`ship-runbook.md`](../plugins/sdd/standards/ship-runbook.md), the design reasons are in
[`agent-pipeline.md`](../plugins/sdd/standards/agent-pipeline.md), and the role contracts are in
[`harness.md`](../plugins/sdd/standards/harness.md). When this page and those disagree, they win.
It describes sdd **0.19.0**.

Commands are written in plugin form (`/sdd:ship`). In a [flat copy](installation.md#flat-copy-recommended)
they have no namespace (`/ship`), and in Codex they are `$ship`.

- [The agentic SDLC in one picture](#the-agentic-sdlc-in-one-picture)
- [What the harness is made of](#what-the-harness-is-made-of)
- [One `/sdd:ship` run, step by step](#one-sddship-run-step-by-step)
- [Retry budgets and escalation](#retry-budgets-and-escalation)
- [Profiles: scaling the pipeline to the risk](#profiles-scaling-the-pipeline-to-the-risk)
- [Who sees what: context isolation and tool contracts](#who-sees-what-context-isolation-and-tool-contracts)
- [What a run leaves in your repository](#what-a-run-leaves-in-your-repository)
- [Where the orchestrator lives](#where-the-orchestrator-lives)
- [One harness, three coding agents](#one-harness-three-coding-agents)
- [Installing and upgrading](#installing-and-upgrading)
- [Layering: framework, platform, product repos](#layering-framework-platform-product-repos)

---

## The agentic SDLC in one picture

`/sdd:ship <feature>` is the single entry point for a code change. It walks the change through
the same lifecycle a careful team would: agree what to build, design it, build it test-first,
have it reviewed and tested by someone who did not write it, and open a pull request that CI
has to pass. A person is in the loop at two points: approving the spec, and reviewing and
merging the PR.

```mermaid
flowchart TB
    subgraph decide ["Decide what to build"]
        direction LR
        idea(["Feature in one sentence"]) --> spec["Spec<br/>requirements.md"] --> gate1{{"You approve<br/>the spec"}} --> plan["Plan<br/>design.md + tasks.md"] --> dgate["Design gate<br/>gate-design.py"]
    end
    subgraph build ["Build it, one task at a time"]
        direction LR
        impl["Implement<br/>test-first"] --> crit["Code critique"] --> qa["QA<br/>source-blind"]
        qa -->|next task| impl
    end
    subgraph ship ["Check the whole change and ship it"]
        direction LR
        explore["Exploratory QA<br/>whole feature"] --> review["Diff review<br/>proof of bug"] --> publish["Publish<br/>docs, PR, CI"] --> gate2{{"You review<br/>and merge"}}
    end
    decide --> build --> ship

    classDef human fill:#fef3c7,stroke:#b45309,color:#000
    classDef gate fill:#e0e7ff,stroke:#4338ca,color:#000
    class gate1,gate2 human
    class dgate,review gate
```

`--autonomous` removes the spec approval and runs to an open PR. Merging is never automated.

---

## What the harness is made of

The plugin lives in `plugins/sdd/` here, and in `.claude/` after a flat copy. It is mostly Markdown. Each kind of file has one job, and they point at each other
rather than repeating each other: a skill links to the standard it follows instead of copying
its rules.

```mermaid
flowchart TB
    agents_md["AGENTS.md<br/>rules + skill routing table"]

    subgraph plugin ["sdd plugin"]
        direction TB
        skills["skills/<br/>21 skills: ship, spec, plan,<br/>implement, review-diff, create-pr ..."]
        standards["standards/<br/>ship-runbook, agent-pipeline,<br/>harness, doc-structure, branching-model"]
        roles["agents/<br/>7 roles: planner, critic, executor,<br/>tester, qa-engineer, publisher, archivist"]
        templates["templates/docs/<br/>requirements, design, tasks, ADR"]
        gates["scripts/<br/>gate-design.py, gate-review.py"]
        tiers["config/<br/>config.schema.json, model-tiers.json"]
        hook["hooks/<br/>SessionStart for web and CI"]
    end

    config[".claude/sdd/config.json<br/>your commands, branches, dev server"]
    out[("docs/specs/&lt;domain&gt;/<br/>commits, pull request")]

    agents_md -->|routes a task to| skills
    skills -->|follow| standards
    skills -->|spawn| roles
    skills -->|read| config
    roles -->|fill in| templates
    skills -->|run| gates
    roles -->|resolve model by tier| tiers
    roles --> out
```

| Kind | Answers | Read by |
|---|---|---|
| Standard | *What* the rules are | People and agents |
| Skill | *How* an agent runs a workflow | Agents (you invoke them) |
| Agent role | *Who* does one job, with which tools | The skill that spawns it |
| `config.json` | *Which* commands and branches this repo uses | Skills, through placeholders such as `<TEST_CMD>` |
| Gate script | *Whether* an artifact passes a mechanical check | The orchestrator; exit 0 or 1 |

The full skill list is in [Plugins](plugins.md); the config keys are in
[Configuration](configuration.md).

---

## One `/sdd:ship` run, step by step

The session you type `/sdd:ship` into is the **orchestrator**. It follows the runbook, writes the
spec, design, tasks and PR itself, and spawns a separate agent for every step that needs
independence or a clean context. It never writes product code or tests.

```mermaid
sequenceDiagram
    autonumber
    actor You
    participant O as Orchestrator<br/>(your session)
    participant C as critic
    participant E as executor
    participant T as tester
    participant Q as qa-engineer
    participant CI as CI

    You->>O: /sdd:ship "add CSV export"
    Note over O: Stage 1 Spec: writes requirements.md
    O->>C: review requirements
    C-->>O: PASS or REVISE (loop)
    O->>You: approve the spec?
    You-->>O: approved
    Note over O: Stage 2 Plan: writes design.md + tasks.md
    O->>C: review design
    C-->>O: PASS or REVISE (loop)
    Note over O: Design gate: gate-design.py

    loop each task in tasks.md
        O->>E: one task id + design
        E-->>O: commit (red, green, refactor)
        O->>C: review the change
        C-->>O: PASS or REVISE
        O->>T: QA scenario (no source access)
        T-->>O: PASS or FAIL
    end

    O->>Q: play with the whole feature
    Q-->>O: bug fixes with regression tests + friction report
    Note over O: Stage 4c Review: /sdd:review-diff + gate-review.py
    Note over O: Stage 5 Publish: prepare-docs, PR description from specs
    O->>CI: open PR
    CI-->>O: green, or failure routed back to executor
    O->>You: PR link
```

| Stage | Who | Produces |
|---|---|---|
| 1 Spec | Orchestrator, following `planner.md`; critic loop | `requirements.md` with Given/When/Then acceptance criteria |
| 2 Plan | Orchestrator, following `planner.md`; critic loop | `design.md` (architecture, decisions, failure modes, test and QA scenarios), `tasks.md`, optional issues |
| Design gate | `gate-design.py` | Exit 0, or one `FAIL:` line per problem |
| 3 Implement | `executor`, one per task | One commit per task, tests first |
| Mutation gate | `commands.mutate` on the diff | Surviving mutants killed by new tests (`strict` or `--mutate`) |
| Code critique | `critic` | PASS or REVISE per task |
| 4 QA | `tester` | PASS or FAIL per task, from the outside |
| 4b Explore | `qa-engineer`, once | Fixes for confirmed bugs, a friction report for the PR |
| 4c Review | `/sdd:review-diff` + `gate-review.py` | `.review/findings.json`; at most two passes |
| 5 Publish | Orchestrator, following `publisher.md` | Docs sealed, PR opened, CI watched |

### Test-first, and in `strict` adversarially so

Under `standard` one executor does red, green and refactor in a single commit. Under `strict` the
tests and the code come from two executor invocations with opposite goals, so the code cannot be
shaped around tests it wrote for itself:

```mermaid
flowchart LR
    design["design.md<br/>test scenarios +<br/>failure modes matrix"] --> pros["Prosecutor<br/>executor, mode test-author<br/>writes failing tests only"]
    pros --> def["Defender<br/>executor, mode implement<br/>tests are read-only"]
    def -->|TEST_DISPUTE| pros
    def --> mut{"Mutation gate<br/>survivors?"}
    mut -->|yes, max 2 cycles| kill["executor, mode kill-mutant<br/>adds a test that kills it"]
    kill --> mut
    mut -->|none| critique["Code critique"]
```

---

## Retry budgets and escalation

Every loop has a budget. When one runs out, the run stops and tells you which budget, gate or
design gap needs a decision. It never skips a gate, edits a gate script, or relaxes the profile
to get past one.

```mermaid
stateDiagram-v2
    [*] --> Spec
    Spec --> SpecGate: interactive
    Spec --> Planning: autonomous
    SpecGate --> Planning: approved
    Planning --> DesignGate
    DesignGate --> Planning: fails once
    DesignGate --> Escalation: fails twice
    DesignGate --> Implementing: exit 0

    Implementing --> CodeCritique
    Implementing --> Planning: DESIGN_GAP
    CodeCritique --> Implementing: REVISE once
    CodeCritique --> Escalation: REVISE twice
    CodeCritique --> QA: PASS
    QA --> Implementing: FAIL once or twice
    QA --> Escalation: FAIL three times
    QA --> Implementing: PASS, next task
    QA --> Exploring: PASS, last task

    Exploring --> Reviewing: fixes kept or reverted
    Reviewing --> Publishing: pass
    Reviewing --> FixingFindings: pass 1 revise
    FixingFindings --> Reviewing: pass 2
    Reviewing --> Escalation: pass 2 revise

    Publishing --> Implementing: CI fails on code
    Publishing --> Publishing: CI flake, retry once
    Publishing --> Done: CI green
    Done --> [*]
    Escalation --> [*]: waits for you
```

The authoritative version, including the `fast` shortcuts, is the
[state machine in the runbook](../plugins/sdd/standards/ship-runbook.md#state-machine).

---

## Profiles: scaling the pipeline to the risk

`--profile` (or `pipeline.profile` in `config.json`) picks how much of the pipeline runs:
`fast` for small bugfixes, UI tweaks and docs; `standard` (the default) for ordinary features and
fixes; `strict` for payments, auth, data loss and concurrency.

```mermaid
flowchart TB
    subgraph fast ["fast"]
        direction LR
        f1["executor on the<br/>change description"] --> f2["review-diff"] --> f3["publish + CI"]
    end
    subgraph standard ["standard (default)"]
        direction LR
        s1["spec + plan<br/>with critic"] --> s2["design gate"] --> s3["implement, critique,<br/>QA per task"] --> s4["explore"] --> s5["review-diff"] --> s6["publish + CI"]
    end
    subgraph strict ["strict"]
        direction LR
        t1["spec + plan with full<br/>failure modes matrix"] --> t2["design gate<br/>--profile strict"] --> t3["Prosecutor, Defender,<br/>mutation gate, critique, QA"] --> t4["explore"] --> t5["review-diff"] --> t6["publish + CI"]
    end
    fast ~~~ standard ~~~ strict
```

Flags beat the profile for one run: `--explore` / `--no-explore` and `--mutate`. If a `fast`
change turns out to need a design decision, the run stops and asks whether to rerun with
`--profile standard`. The per-stage table is in the
[runbook](../plugins/sdd/standards/ship-runbook.md#profiles).

---

## Who sees what: context isolation and tool contracts

Independence is the point of having separate agents, so each one gets only the inputs its job
needs. A critic that saw the executor's reasoning would tend to agree with it; a tester that
could read the code would grade the code instead of the behaviour.

```mermaid
flowchart LR
    subgraph docs ["Spec docs"]
        req["requirements.md"]
        des_arch["design.md<br/>architecture + test scenarios"]
        des_qa["design.md<br/>QA scenarios"]
        tasks["tasks.md"]
    end
    code["Source code<br/>and diffs"]

    des_arch --> executor
    tasks -->|one task id| executor
    executor -->|writes| code

    code -->|changed files| critic
    des_arch --> critic

    des_qa --> tester
    req --> tester
    code -. "no Read, Grep or Glob tool" .-x tester

    style tester fill:#dcfce7,stroke:#15803d,color:#000
    style critic fill:#e0e7ff,stroke:#4338ca,color:#000
```

In Claude Code the boundary is enforced by each agent's `tools:` list, not by asking nicely: a
tool that is not declared cannot be called. Every agent declares a role, and every role has a
contract that `scripts/check-all.sh` checks.

| Role | Agents | Contract |
|---|---|---|
| author | `planner`, `executor`, `qa-engineer` | Needs `Read` and `Write`; writes specs, plans or code |
| reviewer | `critic` | No write tool: it cannot change what it judges |
| verifier | `tester` | No `Read`, `Grep` or `Glob`: it cannot see the implementation |
| orchestrator | `publisher` | Must declare `Agent`; broad access |
| auditor | `archivist` | Read-only inspection and reporting |

Each role also declares a model **tier** (`workhorse` for planner, critic, publisher, archivist
and qa-engineer; `fast` for executor and tester), resolved per provider through
`config/model-tiers.json`. In Codex the same contracts are instructions rather than enforced
tool lists. Details: [harness.md](../plugins/sdd/standards/harness.md#agent-roles-and-tool-contracts)
and the [context engineering table](../plugins/sdd/standards/ship-runbook.md#context-engineering-rules).

---

## What a run leaves in your repository

Specs are the source of truth, so they are written before code and kept current as the code
changes. A domain's docs move through `Draft` → `Review` → `Approved`.

```mermaid
flowchart LR
    subgraph domain ["docs/specs/&lt;domain&gt;/"]
        direction TB
        r["requirements.md<br/>user stories, acceptance criteria,<br/>Given/When/Then"]
        d["design.md<br/>architecture, decisions,<br/>failure modes, test + QA scenarios"]
        t["tasks.md<br/>checkboxes, issue links"]
        r --> d --> t
    end
    t --> commits["One commit per task<br/>on the feature branch"]
    commits --> pr["Pull request<br/>description drafted from the specs,<br/>explore report, review notes"]
    domain -.->|status listed in| idx["docs/INDEX.md"]
```

Acceptance criteria freeze when the design is approved. If a QA scenario later has to change,
that is a recorded decision in the design's Decisions table, never a quiet edit to make a test
pass. The layout rules are in
[doc-structure.md](../plugins/sdd/standards/doc-structure.md).

---

## Where the orchestrator lives

The orchestrator is always the session you started `/sdd:ship` in. That is a deliberate change
over several releases:

| Version | Orchestration |
|---|---|
| up to 0.14 | An `architect` subagent ran the pipeline and spawned every stage |
| 0.15.0 | Inline in the calling session by default; `architect` kept as an opt-in for several missions per session |
| 0.16.0 | The inline session also writes the spec, plan and PR itself instead of spawning `planner` and `publisher` |
| 0.19.0 | Inline only; the `architect` agent and `pipeline.orchestrator` are gone |

Keeping planning and publishing in your session means the spec approval is a normal back and
forth with you, and nothing has to be relayed up through nested subagents. To run several
features at once, run several sessions: a host such as
[agent-anywhere](https://github.com/zenithml/agent-anywhere) starts one thread per feature, and
each thread runs its own `/sdd:ship`.

```mermaid
flowchart TB
    host["Your host<br/>terminal tabs, or one thread per feature"]
    host --> s1["Session A<br/>/sdd:ship feature A"]
    host --> s2["Session B<br/>/sdd:ship feature B"]
    s1 --> a1["critic · executor · tester · qa-engineer"]
    s2 --> a2["critic · executor · tester · qa-engineer"]
```

Running one stage on its own (`/sdd:spec`, `/sdd:plan`, `/sdd:publish`) still spawns that
stage's agent; that path is for resuming or debugging.

---

## One harness, three coding agents

There is one canonical copy of the skills and roles. Claude Code, Codex and Antigravity (`agy`)
all read it; nothing is generated per client except Codex's MCP block.

```mermaid
flowchart LR
    subgraph repo ["Your repository"]
        agentsmd["AGENTS.md"]
        skills[".claude/skills/"]
        roles[".claude/agents/*.md"]
        link[".agents/skills<br/>symlink"]
        mcp[".mcp.json"]
        codexcfg[".codex/config.toml<br/>managed MCP block"]
        link --> skills
        mcp -->|sync_mcp.py| codexcfg
    end

    claude["Claude Code<br/>/ship"] --> agentsmd
    claude --> skills
    claude -->|registered roles| roles
    codex["Codex<br/>$ship"] --> agentsmd
    codex --> link
    codex -->|full role text into a<br/>fresh native subagent| roles
    codex --> codexcfg
    agy["agy"] --> link
```

How delegation and model selection work across hosts is the
[delegation contract](../plugins/sdd/standards/agent-pipeline.md#cross-harness-delegation);
setup is [Using Codex](installation.md#using-codex).

---

## Installing and upgrading

Three routes get the plugin into a repository; they differ only in how the files arrive.

```mermaid
flowchart TB
    src["agent-framework<br/>tagged release"]
    src -->|"install-skills.sh<br/>(recommended)"| flat["Flat copy<br/>committed .claude/<br/>commands: /ship"]
    src -->|"install-skills.sh --local"| local["Flat copy, uncommitted<br/>listed in .git/info/exclude<br/>commands: /ship"]
    src -->|"extraKnownMarketplaces<br/>in settings.json"| market["Marketplace<br/>fetched each session<br/>commands: /sdd:ship"]
    src -->|vendor.sh| vendor["Vendored copy<br/>.claude/vendors/<br/>commands: /sdd:ship"]
    flat & local & market & vendor --> init["/sdd-init once,<br/>then /ship &lt;feature&gt;"]
```

### How a flat-copy upgrade keeps your edits

A flat install writes `.claude/sdd/.harness-manifest`, the hash of every file it installed.
Re-running `install-skills.sh` from a newer checkout compares each file three ways (your copy, the
manifest, the new upstream) so it can tell your edits from upstream changes:

```mermaid
flowchart TB
    start(["Re-run install-skills.sh"]) --> m{"Manifest<br/>present?"}
    m -->|"no: installed before the manifest existed"| over["Overwrites every file<br/>check git diff afterwards"]
    m -->|yes| edited{"Did you edit<br/>this file?"}
    edited -->|no| shipped{"Does the new<br/>version still ship it?"}
    shipped -->|yes| update["Updated to upstream"]
    shipped -->|no| del["Deleted"]
    edited -->|yes| up{"Did upstream<br/>change it too?"}
    up -->|no| keep["Kept as you left it"]
    up -->|yes| conflict["Kept; new upstream copy written to<br/>.claude/sdd/upstream/&lt;path&gt;<br/>merge by hand, don't commit it"]
    conflict -.->|"--overwrite-local"| take["Take upstream instead"]
```

Compare `.claude/sdd/.harness-version` with this repo's plugin version to see whether a
consumer is behind. Every route is exercised in CI by `tests/install-paths.sh`; the commands are
in [Installation](installation.md).

---

## Layering: framework, platform, product repos

This repository is public and generic. An organisation that wants private plugins, private
integrations or a single pinned version across many repositories can put a thin **platform
layer** between the framework and its product repositories:

```mermaid
flowchart LR
    subgraph public ["Public"]
        fw["agent-framework<br/>sdd, render, ci-runner<br/>a tagged release per version bump"]
    end
    subgraph org ["Your organisation (optional)"]
        platform["Platform repo<br/>pins one framework release<br/>+ private plugins<br/>+ its own installer and marketplace"]
    end
    subgraph products ["Product repositories"]
        app1["app A<br/>flat copy"]
        app2["app B<br/>marketplace, pinned tag"]
    end
    solo["Any other repo"]

    fw -->|"re-pin to a new tag"| platform
    platform -->|"platform installer<br/>(not the public one)"| app1
    platform -->|"enable plugin at a tag"| app2
    fw -->|"install-skills.sh"| solo
```

The rules that keep the layers honest:

- **Framework changes go upstream.** A fix to a skill, agent or standard is a pull request to
  agent-framework, then a re-pin in the platform, then a refresh in each product repo. A change
  can therefore take one PR per layer.
- **A product repo installs from the layer directly above it.** The platform's installer runs
  the pinned framework release's own `install-skills.sh`, then copies the private plugins on top,
  so the flat copy and the marketplace route resolve to the same versions. Running the public
  installer in a platform-managed repo would install a different release and leave the private
  plugins out.
- **Never re-run an installer on a repo that has no `.harness-manifest`** without checking
  `git diff` afterwards: without the manifest it cannot tell your edits from stale files.

A repository with no platform layer simply installs from agent-framework, as in
[Installing and upgrading](#installing-and-upgrading).
