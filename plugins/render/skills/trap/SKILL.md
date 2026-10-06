---
name: trap
description: Record a bug that threw nothing as a symptom-keyed row, in the same change that fixes it. Does not trigger for a bug that already throws or logs something greppable, and does not trigger as a follow-up task after the fix has already shipped — the row belongs in the same commit.
---

**Usage:** `/render:trap <symptom>` — e.g. `/render:trap every frame reports 1
draw call`, `/render:trap two captures of one state differ in every pixel`

In a perceptual domain nearly every significant bug throws nothing and logs
nothing. Without a written record each session rediscovers the same one at full
cost. This is the cheapest permanent thing you can do after a hard debugging
session.

---

## Step 1: Write the symptom first, in the user's words

The **symptom is the key**, because the symptom is all a future session has. Not
"the info object resets per render call" — *"every frame reports 1 draw call"*.
Not "the ember pool retains state" — *"two captures of one state differ in every
pixel"*.

A future agent greps for what it is staring at.

## Step 2: Add the row

Append to the traps table in the relevant standard — conventionally
`docs/standards/art-direction/design.md`, or the standard for whichever
perceptual domain this was. Format:

```markdown
| Symptom | Cause |
|---|---|
| <what you saw, concretely> | <the mechanism, then the fix in one clause> |
```

Keep the cause to one or two sentences and make it *mechanical* — the reason it
happens, not a narrative of how you found it. If the fix has a name in the
codebase, use it.

## Step 3: Do it in the same commit as the fix

Not a follow-up. A traps row written later is a traps row not written.

## Step 4: Check whether it generalizes

If the cause is not specific to this project — a library's API resetting per
call, a headless browser not running its animation loop, a global seed not
fixing a system's *offset* into the sequence — say so in the row. Those are the
rows worth upstreaming into
`${CLAUDE_PLUGIN_ROOT}/standards/agent-graphics.md`.

---

## Rules

- **Never key a row by its cause.** Nobody searches for a cause they do not know.
- **One row per distinct symptom**, even where two share a mechanism — they will
  be searched for separately.
- **Do not delete rows** when the underlying bug is fixed. The row is the record
  that the trap exists at all; the fix is what stops it firing.
- **A standard with no traps table is a standard nobody has debugged against.**
  `/sdd:lint-harness` should flag it.
