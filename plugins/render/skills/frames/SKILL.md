---
name: frames
description: Re-shoot the project's named observation set, read every frame, and report against the look contract. Does not trigger on a project with no capture endpoint yet (run render-init first), and does not trigger to change a value and compare (that is tune).
---

**Usage:** `/render:frames [frame-id ...]`

Re-observe the named set before and after any change to a perceptual domain, and
**look at every result**. A green budget table means the costs held, not that
the output is right.

> **Configuration.** Resolve `<DEV_CMD>` and `<SHOOT_CMD>` from
> `.claude/sdd/config.json` (`commands.dev`, `commands.shoot`). If absent,
> read `package.json` scripts — conventionally `dev` and `shoot`. The project's
> observation set lives where its `render.framesPath` config says, defaulting to
> `src/theme/frames.*`; its look contract is `docs/standards/art-direction/design.md`.

---

## Step 1: Confirm the sensor exists

If the project has no capture endpoint, **stop and run `/render:render-init` first.**
Do not attempt a perceptual change without one — see
`${CLAUDE_PLUGIN_ROOT}/standards/agent-graphics.md`, practice 1.

## Step 2: Read the look contract before looking at anything

Read the project's art-direction standard, in particular its **look statement**
and its **traps table**. You are about to judge images; judge them against a
written intent, not against taste you invented this session.

## Step 3: Shoot

```bash
<DEV_CMD>      # background, if not already running
<SHOOT_CMD>    # whole set, or pass ids for a subset
```

A subset is fine while iterating. **Shoot the whole set before reporting done** —
the value of a fixed set is that a regression in something nobody was thinking
about still surfaces.

## Step 4: Read the index, then every image

Open the generated index first: it lists each frame's id, its `intent`, its cost
and its budget verdict in one place. Then `Read` **every image**, including the
ones whose numbers look fine.

For each frame ask, in this order:

1. **Does it contain the thing its `intent` names?** If not, suspect the
   observation before the artifact — a wrong camera pose returns a perfectly
   composed picture of something else. Derive the pose; never hand-write one.
2. **Does it match the look contract?** Name the clause it violates.
3. **Is the subject readable?** Silhouette separation from the background, and
   from other subjects, at the distance the user actually sees it.

## Step 5: Report

State, per frame: unchanged / improved / regressed / broken — and for anything
but "unchanged", *why*, in one sentence tied to the contract.

Then give the verdict as a whole. Do not report a perceptual change as done on
the strength of a passing budget table.

## Step 6: Record anything that threw nothing

If this run found a bug that produced no error and no log — the normal case in
this domain — run `/render:trap` to add a symptom-keyed row in the same change
that fixes it.

---

## Rules

- **A clean console means nothing.** Render a frame and look at it.
- **Compare draw calls, not milliseconds.** Wall-clock frame time on a dev
  machine drifts more than most changes are worth.
- **Never widen a budget to make a run pass.** Raise a ceiling only deliberately,
  in the change that needs it, with the reason in the commit message.
- **Two runs must be identical.** If they are not, determinism is broken and no
  comparison you make this session means anything — fix that first.
