# Verification Apparatus — Standard

How to make a domain verifiable by an agent when the failure mode is a
*perception* rather than an *exception*.

This is the generalised form of what
[Kenton-GMI/sakura-crossing](https://github.com/Kenton-GMI/sakura-crossing)
does for its visual domain. It applies to any repo and any domain, and it is
the reason that project reaches a quality bar its owner could not have
specified in advance.

`agent-graphics.md` is the graphics-specific instance of this standard. The
skills are `/render:render-init` (build the apparatus), `/render:frames`
(operate it), `/render:tune` (change one value against it) and `/render:trap`
(record what it caught).

---

## 1. The problem it solves

An agent is strong where a failure raises, logs, or fails an assertion. It is
blind where a failure is something you *see*, *hear*, *read*, or *feel* — a flat
render, an ugly layout, a confusing error message, a query that returns correct
rows in 40 seconds, a chart nobody can read.

In those domains the loop breaks in a specific way: the agent makes a change,
observes nothing, declares success, and the human becomes the only sensor in the
system. Progress is then bounded by how often the human looks, and quality is
bounded by how well the human can articulate what is wrong.

The fix is not better prompting. It is **building the agent a sensor**, and
then giving it a fixed set of things to point the sensor at.

The reference repo's `CLAUDE.md` is 185 KB and the largest section is titled
"Verifying visual changes — read this before touching anything visual". That
proportion is the lesson.

---

## 2. The five parts

Any domain the repo ships in should have all five. They are listed in the order
they should be built.

### 2.1 An observation endpoint

A way for the agent to make the artifact's real output into a file it can read.

> `npm run dev` mounts `POST /__shot`, and `window.__shot()` renders one frame
> and writes it to `.shots/`. Then `Read` the file.

Per domain:

| Domain | Endpoint |
|---|---|
| 3D / game render | dev-server route that renders one frame at a given pose to an image |
| Web UI | headless browser screenshot at fixed viewports (Playwright is preinstalled) |
| CLI | golden-file capture of stdout/stderr with ANSI preserved |
| API / query | recorded response + `EXPLAIN ANALYZE` written to a file |
| Audio | waveform or spectrogram PNG |
| Docs / prose | rendered HTML or PDF page, not the source markdown |

Two rules that make an endpoint actually usable:

- **It must be deterministic.** Seed every RNG on the path to the output.
  Without this, before/after frames differ for reasons unrelated to the change
  and no comparison means anything.
- **It must not depend on real time.** Headless pages do not run
  `requestAnimationFrame`; CI has no wall clock you can wait on. Reach a state
  by *stepping* the simulation (`for (i…) update(1/60)`), never by sleeping.

**Build the endpoint before doing the work, not after.** If the quality of the
deliverable cannot be read out of a file, that is the first task in the plan.

### 2.2 A named observation set

A checked-in list of observations, each with a comment saying **what it shows
and why it is in the list**. The reference keeps ~120 camera positions, named
by intent — "the money shot", "the school gate", "inside a refuge".

This is a regression suite whose oracle is judgment rather than an assert. Its
value is that it is *fixed*: the agent re-observes the same set before and after
a change, so a regression in something it was not thinking about still shows up.

Discipline:

- Every entry names its subject. If the observation does not contain the thing
  its comment names, **suspect the observation, not the artifact.**
- Derive the observation's parameters, never hand-write them. The reference
  documents three camera lines written with a sign error that "returned a
  perfectly composed frame of something else" — invisible unless you check.
- An entry that has never actually been looked at is a liability, not coverage.

### 2.3 Cheaper oracles than observation

For each perceptual property, find a *numeric proxy* that can be asserted in a
normal test. Prefer the proxy; use observation to discover which proxy matters.

The reference's examples are the model:

> "Can this be seen?" is a raycast, not a screenshot — and it can be asked with
> no browser at all.

> `hillSafety(world)` samples every collider and platform inside a keep-out and
> reports the worst height it finds; it must read 0.00.

> Build it headless in the page and read the stack. This turns "the page is
> blank and there is nothing in the console" into a file and a line number.

Generalised: visibility → raycast; readability → contrast ratio; density →
element count; cost → draw calls or query rows scanned; layout → bounding-box
overlap; "does it even construct" → a headless build against a three-method
stub. Each of these runs in milliseconds and can gate CI, where an image cannot.

### 2.4 A symptom-keyed traps table

A table of failures that threw nothing, **indexed by what you observe**, not by
what is broken:

> | Thing | Why |
> | Planet sphere must have `castShadow = false` | …Symptom: everything
> uniformly dark for no visible reason. |
> | A multi-material mesh must keep its `geometry.groups` through the bake |
> …Symptom: a district where nobody has put their sign up. |

The symptom is the key because the symptom is all the agent has. This is the
highest-value document an agent can inherit: without it, every session
rediscovers the same silent failure from scratch, at full cost.

Every standard in `docs/standards/` should carry one. Add a row whenever a bug
is found that produced no error.

### 2.5 Calibration of the instrument

Record the noise floor of any measurement used to make decisions, or the agent
will chase noise:

> Wall-clock frame time on this machine drifts 33–42 ms run to run with nothing
> changed, so it cannot resolve anything smaller than about 8 ms. Compare draw
> calls when judging a change.

Also record what does *not* matter, with the measurement that proved it —
"halving the internal resolution changes nothing (19.3 → 19.1 ms)" saves every
future session from optimising the wrong thing.

---

## 3. Two cross-cutting disciplines

These are not verification, but they are what makes verification actionable.

### 3.1 One choke point per cross-cutting concern

Any property that must hold *globally* needs a single constructor and a written
"never build X directly" rule. The reference has `cel()` / `flat()` for every
material and `PAL` for every colour; the whole town's look is retunable from one
file as a result.

The same shape applies to logging, error envelopes, auth checks, feature flags,
date formatting, currency, i18n strings. Two requirements:

- The rule is stated in the standard as a prohibition, in those words.
- The rule is enforced by a lint rule or a test. **A convention an agent can
  violate silently, it will** — and the violation is invisible until the day
  someone needs the global change.

### 3.2 The failure record

The reference keeps a `NEXT.md` that records, per round of work, *what the round
actually found* — "almost always a bug that threw nothing, logged nothing and
looked fine in a screenshot". Not a changelog: a record of how the work went
wrong, including where the verification apparatus itself lied.

This is the input to §2.4. Sessions are amnesiac; the record is the memory.

---

## 4. How this repo adopts it

### As standards

Each domain-specific standard in a consuming repo's `docs/standards/` carries a
**Verification apparatus** section naming its five parts, and a **Traps** table.
Domains whose oracle is already mechanical — code style, where lint and tests
answer the question — need the traps table but not the endpoint.

### As harness

The claim to check for any new domain is: *what does "wrong" look like here, and
can the agent observe it?* If the answer is no, the observation endpoint is the
first task in the plan, ahead of the feature.

Specifically for the `sdd` pipeline skills:

- **`/sdd:plan`** — a design doc touching a perceptual domain must declare which
  observations verify it and which numeric proxies gate CI, in the same place it
  declares acceptance criteria. A design that cannot say how it will be seen is
  not ready.
- **`/sdd:qa`** — extend from "observable behaviour" to explicitly include
  *perceptual* observables: re-shoot the named set, read every frame, report
  against the look contract rather than against a checklist of features.
- **`/sdd:lint-harness`** — add checks that every standard has a traps table,
  and that the repo's declared choke points are actually enforced by a rule.
- **`/sdd:sdd-init`** — when it detects a rendering or UI stack, delegate to
  `/render:render-init` so a new repo starts with the sensor already wired.

### The part a human still supplies

Two things, and neither is domain expertise:

1. **A reference and a named target.** "Make it look better" is not actionable;
   "cel-shaded anime background, like *this repo*" is. Picking the reference is
   the human's job, and it is most of the direction.
2. **Insisting on the loop.** Refusing work in a perceptual domain until the
   sensor exists.

Everything between those two the agent can find on its own — but only once it
can see.
