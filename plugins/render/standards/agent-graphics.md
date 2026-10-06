# Building Graphics-Heavy Software With an Agent — Standard

Twelve practices, and one architectural rule, for any project whose output is
judged by looking. Nothing here is specific to a language, an engine or a
rendering library.

Derived from a study of [Kenton-GMI/sakura-crossing](https://github.com/Kenton-GMI/sakura-crossing)
— a Three.js town rendered as a cel-shaded anime background whose only binary
asset is a music file — and from applying its method to a repository that had
none of it.

The companion standard is `verification.md`, which generalises the same method
beyond graphics. The skills that operate this standard are `/render:frames`,
`/render:tune`, `/render:trap` and `/render:render-init`.

---

## The architectural rule

**Three layers, three lifecycles, three consumers. Never one bundle.**

| Layer | Consumer | Ships to users? | Changes when |
|---|---|---|---|
| **Harness** — skills, standards, procedures | the agent | no | the *method* improves |
| **Engine** — render/capture/probe code | the browser | yes | a *capability* is added |
| **Theme** — palette, params, frames, prose | both | yes (data) | the *look* changes |

Dependencies point one way: **Theme ← Engine ← App**. The theme imports
nothing. The engine imports the theme's *type*, never a theme *instance*. The
harness imports nothing at all — it is prose.

Two falsifiable tests keep the boundary honest. Run them whenever something new
is added and you are unsure where it goes:

- **Swap test.** Replace the theme with a different world's. The app compiles,
  runs, and looks like a different product with **zero engine edits.** If an
  engine file had to change, that thing was misfiled as engine — it is theme.
- **Transplant test.** Copy the engine into an empty project. It type-checks
  against an all-defaults theme. If it fails because some product concept is
  missing, that thing was misfiled as engine — it is app.

A third, cheap and mechanical: **no hex colour literal and no domain noun**
("brazier", "torii", "boss") appears anywhere under the engine directory. Make
it a lint rule.

---

## The twelve practices

### 1. Build the sensor before the feature

An agent working on a visual domain with no way to see its output is guessing,
and the human becomes the only sensor in the system. Progress is then bounded by
how often the human looks.

The first task in any graphical plan is a **capture endpoint** — a dev-only
route that renders one frame of a named state to a file the agent can `Read`.
Not a nice-to-have and not a follow-up: it is the precondition for everything
below. See `verification.md` §2.1, alongside this file.

### 2. Determinism is a precondition for judgment

Seed every RNG on the path to a frame. Without it, before and after differ for
reasons unrelated to the change and no comparison means anything.

Corollary: **never reach a state by waiting.** Headless pages do not run
`requestAnimationFrame`. Step the simulation — `for (i…) update(1/60)` — so any
state is reproducible and addressable by a number.

### 3. Style is a pipeline decision, made once

A look is produced by a small number of layers applied to *everything*: the
lighting model, the shadow-colour policy, the edge treatment, the grade. Decide
them up front and name the target. A project that never made this decision has a
default realistic renderer with effects bolted on, and no amount of per-object
work will rescue it.

### 4. One choke point per cross-cutting visual concern

Every material is built by one factory. Every colour comes from one palette.
State the rule as a prohibition — *"never construct a material directly"* — and
**enforce it with a lint rule.** A convention an agent can violate silently, it
will, and the violation is invisible until the day someone needs a global
change.

Test of whether you have this: can the entire product's shadow hue be changed by
editing one line? If not, you do not have a choke point, you have a habit.

### 5. Theme is data, not code

Everything a designer would want to change is serializable plain data: colours,
band stops, light intensities, pass parameters, budgets, tier policy. Data can
be validated, diffed, unit-tested with no GPU, and generated. Code cannot.

The chain of passes is part of the data. `['ink','grade','fxaa']` and
`['bloom','grade']` are two different products from one engine — that is the
difference between a configuration layer and a skin.

### 6. Shadows are coloured, not dark

The most transferable art fact available: the hue shift in shadow is most of
what separates a stylized look from an untreated 3D one. Shadow colour is a
design decision, not the absence of light. Apply it at all three levels —
ambient/hemisphere, per-material dark band, and the grade's split-tone.

### 7. Named observations, addressed by intent

Keep a checked-in list of captures, each commented with *what it shows and why
it is in the list* — "the crowd worst case", "the money shot". Re-shoot the
relevant subset before and after every visual change and **look at every one**.

It is a regression suite whose oracle is judgment. Its value is that the set is
fixed, so a regression in something nobody was thinking about still surfaces.
Derive capture parameters; never hand-write an angle. A wrong pose returns a
perfectly composed frame of something else.

### 8. Prefer numeric proxies; use frames to find which proxy matters

For each perceptual property, find a number that can be asserted in an ordinary
test: visibility → raycast, readability → contrast ratio, cost → draw calls,
layout → bounding-box overlap, "does it even construct" → headless build against
a stub. These run in milliseconds and gate CI, where an image cannot.

Frames are for discovery. Proxies are for defence.

### 9. Calibrate the instrument, then compare the stable quantity

Record the noise floor of any measurement used to make a decision. Wall-clock
frame time on a dev machine typically drifts more than the change is worth —
compare draw calls instead. Also record what has been proven *not* to matter,
with the measurement that proved it, so future sessions skip the dead end.

### 10. Traps are keyed by symptom

Maintain a `| Symptom | Cause |` table per visual domain. The symptom is the key
because the symptom is all the agent has. Append a row every time a bug is found
that threw nothing — which, in this domain, is nearly all of them.

**A clean console means nothing. Render a frame and look at it.**

### 11. Budget per frame, asserted in CI

Every named frame carries a cost ceiling (draw calls, triangles, programs).
Exceeding it fails the build. Without this, stylistic work degrades performance
by a hundred invisible increments and the regression is attributed to whatever
happened to land last.

### 12. Every tier gets art direction

If the low tier disables the whole finishing chain, the majority of users are
shipped ungraded raw output — i.e. no art direction at all. Tier down the
*expensive* layers (multi-pass bloom, high-res shadows); keep the cheap ones (a
single grade pass) everywhere. The tier policy belongs in the theme, per pass,
not as one on/off switch.

---

## What the human still supplies

Two things, and neither is domain expertise:

1. **A reference and a look statement.** "Make it look better" is not
   actionable; "cel-shaded anime background, like *this repo*" is. Choosing the
   reference is most of the art direction, and it does not require being able to
   execute it.
2. **Insisting on the loop.** Refusing perceptual work until the sensor exists.

Everything between those two the agent can find — but only once it can see.

---

## Where each layer lives

| Layer | Home | Delivery |
|---|---|---|
| Harness | this plugin | plugin / flat copy |
| Engine | its own versioned package | dependency or vendored |
| Theme | the consuming repo, next to its source | ordinary committed files |

The harness marketplace must **not** carry rendering code: different consumer,
different lifecycle, and a plugin that pulls in a 3D library is a plugin nobody
can install. Keeping them apart is the whole point.

### A worked example

One browser game built on this standard applies all twelve. Its engine layer is a
`stylekit/` module, its theme layer a separate `theme/` module, and a design spec
carries the interfaces and the migration path. Five things it found on the way to a
deterministic frame — none of which threw or logged anything — are worth knowing
before you start:

1. **A per-call statistics reset.** `renderer.info` resets on *each* draw call,
   so a post-processed frame reported one draw call: the final fullscreen quad.
   Ten plausible readings before an image obviously containing more than one
   object gave it away.
2. **The wall clock.** Film grain, flame flicker and a bobbing prop each read
   `performance.now()` rather than a delta, so every observation was taken at a
   different moment.
3. **A live animation loop** advancing the world between observations.
4. **Carried state**: a camera that lerps rather than snaps, a rig that keeps
   its facing, a particle pool that never resets, and a light that orbits
   *inside the render loop* — outside the stepped path, so suspending the loop
   froze it at an arbitrary phase.
5. **RNG sequence position.** A global seed fixes the sequence but not a given
   system's offset into it, so a pool's scatter still moved whenever unrelated
   code drew a different number of randoms first. Named streams fixed it.

Expect your own list to be about this long, and to be found the same way.
