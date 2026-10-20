<!-- sdd:triage-pr -->
## Review triage

6 files, 17 changed lines.
**Read closely: 2 hunks, 3 lines.** Review normally: 3 files, 7 lines. Safe to skip: 2 files, 7 lines.

### 1. Read closely
- [ ] `src/auth/session.ts` L42 (+2 −1) — sensitive path: auth; adds eval(
- [ ] `src/old/x.py` → `src/auth/x.py` (+0 −0) — sensitive path: auth

### 2. Review normally
- `src/lib/cart.ts` (+5 −1, 2 hunks)
- `src/util.js` (+1 −0, 1 hunk)
- `assets/logo.png` (binary)

### 3. Safe to skip
- `package-lock.json` (+3 −2) — lockfile
- `src/util.js` (+1 −1) — whitespace only

### Coverage
Tiers come from path and content heuristics, not from understanding the code. "Review normally"
is not "safe": nothing fired there, which is all the triage claims. Tick each item in section 1
as you read it. An item still unticked when you approve was not reviewed — say so in the review
instead of approving silently.
