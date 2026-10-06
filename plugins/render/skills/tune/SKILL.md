---
name: tune
description: Change one theme value against the frame set — shoot baseline, vary, compare, keep the winner with the frames as evidence. Does not trigger without an existing frame set to compare against (run render-init and frames first), and does not trigger just to re-observe the set with nothing changed (that is frames).
---

**Usage:** `/render:tune <what to change>` — e.g. `/render:tune shadows are too
dark in chapter 3`, `/render:tune ink is too heavy at distance`

A perceptual value is settled by looking, not by reasoning. This is the loop for
doing that without burning a turn per guess.

> **Configuration.** Same keys as `/render:frames`. The theme is the project's
> configuration layer — conventionally `src/theme/theme.*`.

---

## Step 1: Name the frames that can show it

Pick the smallest subset of the named set where the change would be visible,
**plus at least one frame where it must not be visible**. A tuning change that
improves its target and quietly wrecks an unrelated chapter is the normal
failure here.

If no existing frame can show the change, add one to the set first, with an
`intent` that says what it is for. A value nobody can observe is not tunable.

## Step 2: Shoot the baseline and keep it

```bash
<SHOOT_CMD> <ids>
cp -r <shots-dir> <shots-dir>.before
```

Read the baseline images now, before changing anything. You need to know what
you are starting from, not what you assume you are starting from.

## Step 3: Change one value in the theme

**One.** In the theme file — never in the engine, never at a call site. If the
value you want to change is not in the theme, that is the finding: report it and
stop. Something the project needs to tune and cannot is a boundary bug, not a
tuning task.

Bracket rather than creep: if you do not know the direction, try a clearly-too-far
value first. Overshooting once tells you the sign and the rough scale in a single
shot; nudging tells you nothing for three.

## Step 4: Shoot, compare, iterate

Re-shoot the same ids. Put the before and after side by side and say what
actually changed — not what you intended to change.

Stop when the frame matches the look contract, or after about three brackets.
Three failed brackets means the value is not the cause; go back to step 1.

## Step 5: Keep or revert, and say which

If keeping: commit the theme change alone, with the reason and the frames that
justify it. If the value moved a budget, re-shoot the whole set before
committing.

If reverting: say what you tried and what it looked like. A recorded negative
result is worth more than a silent revert — it stops the next session repeating
it.

---

## Rules

- **One value per iteration.** Two changes and one comparison teaches nothing.
- **The theme is the only place you edit.** Reaching into the engine to tune a
  look is how the boundary erodes.
- **A value that improves the target frame and regresses a control frame has not
  been found yet.** Keep going or revert; do not ship it and hope.
- **Record the numbers you rejected**, in the theme as a comment or in the
  standard. "Gain 2.2 overshot into lilac" saves the next session a turn.
