---
name: render-init
description: Give a project the sensor — capture endpoint, named observation set, determinism, budgets — before any perceptual work starts. Does not trigger on a project that already has the sensor scaffolded — use frames or tune instead.
---

**Usage:** `/render:render-init`

Scaffold the verification apparatus for a project whose output is judged by
looking. **This is the first task in any perceptual plan, not a follow-up.**
Until it exists, the human is the only sensor in the system and progress is
bounded by how often they look.

> Run once per project. Afterwards use `/render:frames` and `/render:tune`.

---

## Step 1: Establish what "wrong" looks like here

Read the project and answer, in writing:

- What is the deliverable a human judges by eye? A rendered frame, a page, a
  chart, a document?
- What is the smallest thing that fully determines one of those outputs? That
  set is the project's **state**.
- What already animates or randomises on its own? Those are the things that will
  break determinism, and finding them now is much cheaper than finding them
  from a byte diff later.

## Step 2: Determinism first

An observation you cannot repeat is not evidence. Before building capture:

- **Seed every RNG on the path to the output.** A scoped global override is
  enough to start; it does not require migrating every call site.
- **Freeze the clock.** Anything reading wall-clock time — animation, grain,
  flicker — must be driven by an explicit, steppable time.
- **Never reach a state by waiting.** Step the simulation a fixed number of
  times. Headless environments do not run animation loops.
- **Suspend anything that advances on its own** for the duration of an
  observation, and restore it afterwards.

## Step 3: The capture endpoint

Build the smallest thing that writes the real output to a file the agent can
read. For a dev server, a route that renders one named state and writes an
image. Gate it on the dev build — its absence is then a reliable signal that a
production build is being inspected.

It must take a **state** and produce **one** output, deterministically. It must
capture through the product's own pipeline: photographing a path the user never
sees is worse than not looking.

## Step 4: The named observation set

Create the set as code, with `intent` a **required** field so a frame nobody can
justify does not compile. Seed it with, at minimum:

- one baseline per major visual mode / theme / level;
- the **worst case** for readability — the most crowded, most cluttered state;
- each thing whose appearance is load-bearing for the product;
- one state per tier or device class, if the project has them.

Derive observation parameters; never hand-write an angle or a coordinate.

## Step 5: Instrumentation and budgets

Record a cost reading per observation. Prefer a stable quantity (draw calls,
element count, query rows) over a noisy one (wall-clock time). **Leave budgets
empty on the first run** — an unmeasured frame should report as unbudgeted,
which is the correct verdict. Fill them from the first deterministic run plus
headroom.

Then prove the gate fires: lower one ceiling deliberately, confirm a non-zero
exit, and put it back.

## Step 6: Wire it up

- A one-command driver (`shoot` or equivalent) that runs the whole set headless
  and exits non-zero on a breach.
- The `render.*` keys in `.claude/sdd/config.json`.
- A traps table in the project's standard, empty but present.
- The look statement: the target, and a **reference** if one exists. "Make it
  look better" is not actionable; "like *this*" is.

## Step 7: Verify the sensor before trusting it

- Shoot the set twice with no changes. **Every output must be byte-identical.**
  If not, go back to step 2 — something still moves.
- Read every image. Confirm each contains what its `intent` claims.
- Confirm none of the capture code reaches the production build.

Do not report this skill complete until the two-run comparison passes. A sensor
that lies is worse than no sensor: it produces confident wrong answers.

---

## Rules

- **Build the sensor before the feature.** If quality cannot be read out of a
  file, that is the first task in the plan.
- **The first run should fail loudly** — every observation unbudgeted, nothing
  compared yet. That is the apparatus working.
- **Prefer numeric proxies to images wherever one exists.** Images are for
  discovery; proxies gate CI, where an image cannot.
