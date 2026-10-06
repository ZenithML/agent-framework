---
name: sdd-init
description: >
  Use when a repository is adopting this harness for the first time and needs bootstrapping —
  detect the stack, write config.json, seed the docs scaffold, make the initial commit. Does not
  trigger on a repository already carrying config.json and a docs scaffold, and does not trigger
  to add a single skill to an initialised repo.
---

**Usage:** `/sdd-init` (or `/sdd:sdd-init` when installed as a plugin)

Bootstraps a repo that has the sdd plugin enabled but no `.claude/sdd/config.json` yet. Detects the tech stack from manifest files, derives command defaults, confirms with the user, writes the config, seeds the docs scaffold (`docs/INDEX.md`, `docs/decisions/`, `AGENTS.md`), and commits everything.

---

## Step 1: Guard — check for existing config

```bash
test -f .claude/sdd/config.json && echo EXISTS || echo ABSENT
```

- **ABSENT** → continue to Step 2.
- **EXISTS** → show the current content of `.claude/sdd/config.json` to the user and ask: *".claude/sdd/config.json already exists. Overwrite it?"* Wait for confirmation. If denied, exit and report what was found.

## Step 2: Detect manifest files

Search for manifest files at the repo root and one level deep:

```bash
find . -maxdepth 2 \( -name "package.json" -o -name "pyproject.toml" -o -name "setup.py" \) \
  ! -path "*/node_modules/*" ! -path "*/.git/*" | sort
```

Read each found manifest in full. Build a list of detected stacks:

| Manifest found | Stack |
|---|---|
| `package.json` at root or in a subdir | JavaScript / TypeScript |
| `pyproject.toml` or `setup.py` at root or in a subdir | Python |
| Both | Hybrid monorepo |

Note the directory containing each manifest — a manifest at root means a flat single-stack project; manifests in subdirs (e.g. `backend/`, `frontend/`) indicate a monorepo layout. Record these paths for Steps 3–4.

## Step 3: Derive command defaults

**Python stack** (`pyproject.toml` / `setup.py` found):

Read `pyproject.toml` if present. Check for `[tool.ruff]`, `[tool.pytest.ini_options]`, and `[project.optional-dependencies]` sections.

- `install`: `pip install -e '.[dev]'` if a `dev` optional-dependency group exists, else `pip install -e .`; prefix with the Python manifest's subdir if monorepo (e.g. `pip install -e 'backend[dev]'`)
- `test` / `testOne`: `pytest` / `pytest {file}`; prefix with the subdir scope if monorepo (e.g. `pytest backend`)
- `lint`: `ruff check .` if `[tool.ruff]` is present, else `flake8`
- `build`: `python -m build` (requires the `build` package; replace with `hatch build`, `flit build`, or `poetry build` if those tools appear in `[build-system]` of `pyproject.toml`)
- `dev` / `devHost`: `uvicorn <module>:app --reload` / same with `--host 0.0.0.0`
  - Infer `<module>` from `pyproject.toml` `[project.scripts]` entry point, or try common patterns in order: `<package_name>.main`, `app.main`, `backend.main`, `src.main`
  - Use `fastapi dev` instead if FastAPI ≥ 0.99 appears in dependencies
- `devServer.url`: `http://localhost:8000`

**JavaScript / TypeScript stack** (`package.json` found):

Read the `scripts` section of `package.json` directly. Use actual script names found rather than guessing:

- **Detect the package manager first:** check for `pnpm-lock.yaml` (→ pnpm), `yarn.lock` (→ yarn), `package-lock.json` (→ npm ci), otherwise → npm install. All commands below use the detected PM.
- `install`: `pnpm install` / `yarn install` / `npm ci` / `npm install` per detection. pnpm and yarn manage monorepo workspaces from the root (single `pnpm install` or `yarn install`); for npm use `--prefix <subdir>` (e.g. `npm --prefix frontend ci`)
- `test`: `npm --prefix <subdir> test` (or `npm test` if flat); for pnpm use `pnpm --filter <pkg-name> test`, for yarn `yarn workspace <pkg-name> test`
- `lint`: run lint script if one exists; omit the key if not
- `build`: run build script if one exists
- `dev`: run dev script if one exists
- `devHost`: dev script with `--host` (e.g. `npm run dev -- --host`, or Vite equivalent)
- `devServer.url`: `http://localhost:5173` if Vite appears in `dependencies` or `devDependencies`, else `http://localhost:3000`

**Hybrid monorepo** (both stacks detected in subdirs):

Chain commands with `&&` to cover both sides. Derive each part from the rules above and combine. Example for `backend/` + `frontend/`:

```
install  → pip install -e 'backend[dev]' && npm --prefix frontend ci
test     → pytest backend && npm --prefix frontend test
lint     → ruff check backend && npm --prefix frontend run lint
build    → npm --prefix frontend run build
dev      → uvicorn backend.main:app --reload
devHost  → uvicorn backend.main:app --host 0.0.0.0 --reload
```

The `dev` / `devHost` and `devServer.url` fields describe the **primary** server (the one skills will open for screenshots and smoke tests). Default to the Python backend; note in the confirmation message that the frontend dev server is not included here.

## Step 4: Infer source dir and test metadata

**`source.dir`**:
- Flat Python: `src` if a `src/` directory exists at root, else the package name from `pyproject.toml` `[project].name` (hyphens → underscores), else `.`
- Flat JS/TS: `src` if a `src/` directory exists, else `.`
- Monorepo Python+JS: the Python subdir (e.g. `backend`)
- Monorepo Python-only or JS-only: the subdir containing the manifest

**`test.filePattern`** and **`test.configFile`**:
- Python: `test_*.py, *_test.py` / `pyproject.toml`
- JS/TS with Vitest (`vitest.config.*` present or `vitest` in devDependencies): `*.test.ts, *.test.tsx` / `vitest.config.ts`
- JS/TS with Jest otherwise: `*.test.ts, *.test.tsx` / `jest.config.ts` (or `.js` variant if found)
- Hybrid: use Python test metadata (the skill pipeline's TDD loop operates on the backend by default)

## Step 5: Detect branching model

```bash
git branch -r 2>/dev/null | grep -oE 'origin/(main|master|development|develop|dev)\b' | sed 's|origin/||' | sort
```

Apply this logic:

- Remote has `development`, `develop`, or `dev` → **Gitflow** resolved: set `devBranch` to the first one found in this preference order: `development` > `develop` > `dev`; set `mainBranch` to `main` if present, otherwise `master` if present, otherwise ask the user which production branch to use. Record topology as `gitflow`.
- Remote has only `main` or `master`, or no remote branches found → **GitHub Flow** (the default): record `mainBranch` (and `devBranch` equal to it) and topology `github-flow`. Step 6 offers trunk-based as the alternative; do not ask an open question.

## Step 6: Confirm with the user

Compose the full config JSON from the values derived in Steps 3–5. Omit any key whose value matches the schema default and was not explicitly overridden by the user — keep the file minimal. Always include `"$schema": "https://raw.githubusercontent.com/zenithml/agent-framework/main/plugins/sdd/config/config.schema.json"`.

Present the config and any open questions in a **single message** — do not make separate round trips.

**If topology is Gitflow (detected):** show the config JSON and say: *"Here's what I detected. Confirm to write this, or tell me what to change. I'll also create the docs scaffold (`<DOCS_ROOT>/INDEX.md`, `<DOCS_ROOT>/standards/`, `<DOCS_ROOT>/decisions/`, `AGENTS.md`) unless those files already exist."*

**If topology is GitHub Flow (the default — single main branch or fresh repo):** show the config JSON and the default together in one message:

> *"Here's what I detected — please confirm or correct the config:*
>
> [config JSON]
>
> *No separate development branch exists, so I'll use **GitHub Flow** (the default): feature branches cut from `main`, merged via PR; `main` is always deployable and deploying on merge. If the team instead works **trunk-based** — very short-lived branches (hours to a couple of days), incomplete work behind feature flags — say so and I'll record that instead.*
>
> *I'll also create the docs scaffold (`<DOCS_ROOT>/INDEX.md`, `<DOCS_ROOT>/standards/`, `<DOCS_ROOT>/decisions/`, `AGENTS.md`) unless those files already exist."*

(Use `docs.root` from the proposed config for `<DOCS_ROOT>`; default to `docs`.)

Record the topology (GitHub Flow unless the user picks trunk-based) for use in Step 8a. (Both GitHub Flow and trunk-based use the same config shape — `devBranch == mainBranch` — so the topology choice does not affect the config JSON.)

Wait for the user's response:
- **Confirmed as-is** → proceed to Step 6a.
- **Corrections given** → apply the changes, show the updated JSON, and ask once more before writing.

## Step 6a: Offer plugin source choice

After the user confirms the generated .claude/sdd/config.json but before writing files, present a single combined message offering how to install/enable the sdd plugin for the repository. Offer three choices and ask for a single selection. Use the Bash tool to run commands, Read/Edit/Write to show or modify files, and ask the user for confirmations before any commit.

Choices (present as buttons):

- "Use remote GitHub (recommended)" — plugin resolved from GitHub each session.
- "Vendor plugin into this repo (pin & commit local copy)" — copy plugin into `.claude/vendors/<repo-name>/` and enable `sdd@<repo-name>`.
- "Skip / I'll configure later" — do not change `.claude/settings.json`.

If the user chooses "Use remote GitHub (recommended)":

1. Ensure a `.claude/settings.json` at repo root has the following keys (create or update):

```json
{
  "extraKnownMarketplaces": {
    "sdd-harness": { "source": { "source": "github", "repo": "zenithml/agent-framework" } }
  },
  "enabledPlugins": { "sdd@sdd-harness": true }
}
```

2. Implementation (agent actions):
- If `.claude/settings.json` exists, run:

```bash
python3 - <<'PY'
import json,sys
p='.claude/settings.json'
# (agent: run a safe update that preserves unrelated keys)
PY
```

(Prefer using a small python snippet or the Write/Edit tools to merge the keys while preserving other data.)

- Show the user the diff: `git --no-pager diff -- .claude/settings.json || true`.
- Ask: "Stage and commit this change?" If the user confirms, run `git add .claude/settings.json && git commit -m "chore: enable sdd@sdd-harness (marketplace: zenithml/agent-framework)"`.

If the user chooses "Vendor plugin into this repo (pin & commit local copy)":

1. Run dry-run: `scripts/vendor.sh --dry-run <target-dir>` and show its output.
2. Ask: "Proceed to copy files and update .claude/settings.json?" If yes, run:

```bash
scripts/vendor.sh --name <vendor-key> <target-dir>
```

where `<vendor-key>` defaults to the repo directory name; the script updates `.claude/settings.json` to add the vendor marketplace and enable `sdd@<vendor-key>`.

3. After the script completes, show the added files under `.claude/vendors/<vendor-key>/` (use `ls -R .claude/vendors/<vendor-key> | sed -n '1,200p'`) and show `git status --porcelain` and `git --no-pager diff -- .claude/settings.json`.
4. Ask: "Stage and commit the vendored files?" If confirmed, run:

```bash
git add .claude/
git commit -m "chore: vendor sdd plugin for <vendor-key>"
```

If the user chooses "Skip / I'll configure later":

- Proceed to Step 7 without modifying `.claude/settings.json`.

Notes and constraints:
- Always show the planned commands and their outputs and ask for explicit confirmation before mutating the repository (staging or committing).
- Preserve unrelated keys in existing `.claude/settings.json` when updating.
- Use `--dry-run` to preview the vendor script behaviour before making changes.

## Step 7: Write .claude/sdd/config.json

```bash
mkdir -p .claude/sdd
```

Write the confirmed JSON to `.claude/sdd/config.json`.

## Step 8: Seed the docs scaffold

Read `docs.root` from the confirmed config (default: `docs`). Use that value as `<DOCS_ROOT>` throughout this step.

For every file below, skip it silently if it already exists — never overwrite.

If any file write fails (permission error, disk full, etc.), report the error, list which files were and were not written, and exit without committing. The user can fix the cause and re-run the `sdd-init` skill — the existing-file guard prevents double-writes.

---

### 8a. Branching standard

```bash
mkdir -p <DOCS_ROOT>/standards/branching
```

Write `<DOCS_ROOT>/standards/branching/design.md` using the topology resolved in Steps 5–6 and the branch names from the confirmed config. Fill in the concrete branch names — do not use placeholders.

**Gitflow template** (devBranch ≠ mainBranch):

```markdown
# Branching Model — Standard

This project uses **Gitflow**: features are developed on `feature/*` branches cut
from `<DEV_BRANCH>` and merged back via PR. `<MAIN_BRANCH>` is production-only.

## Topology

| Branch | Purpose |
|---|---|
| `<MAIN_BRANCH>` | Production / release — never pushed to directly |
| `<DEV_BRANCH>` | Integration — all feature PRs target this branch |
| `feature/<domain>` | One branch per feature domain, cut from `<DEV_BRANCH>` |
| `hotfix/<name>` | Urgent production fixes — cut from `<MAIN_BRANCH>`, PR'd into both branches |

## Rules

- Never push directly to `<MAIN_BRANCH>` or `<DEV_BRANCH>` — both are PR-only.
- Merge `<DEV_BRANCH>` into a feature branch and resolve conflicts locally before opening a PR.
- Use Conventional Commits prefixes: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- Delete feature branches after merging.
```

**GitHub Flow template** (devBranch == mainBranch, topology = github-flow):

```markdown
# Branching Model — Standard

This project uses **GitHub Flow**: feature branches are cut from `<MAIN_BRANCH>`,
developed, then merged back via PR. `<MAIN_BRANCH>` is always in a deployable state;
merging a PR triggers deployment.

## Topology

| Branch | Purpose |
|---|---|
| `<MAIN_BRANCH>` | Always deployable — merging here triggers deployment |
| `feature/<domain>` | One branch per feature domain, cut from `<MAIN_BRANCH>` |
| `hotfix/<name>` | Urgent fixes, also cut from `<MAIN_BRANCH>` |

## Rules

- `<MAIN_BRANCH>` must always be deployable — never merge a branch with failing tests or incomplete features.
- Open a PR early for discussion, not only when the branch is ready to merge.
- Never push directly to `<MAIN_BRANCH>` — it is PR-only.
- Use Conventional Commits prefixes: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- Delete feature branches after merging.
```

**Trunk-based template** (devBranch == mainBranch, topology = trunk-based):

```markdown
# Branching Model — Standard

This project uses **trunk-based development**: very short-lived feature branches are
cut from `<MAIN_BRANCH>` and merged back frequently. Incomplete work is hidden behind
feature flags rather than kept in long-lived branches.

## Topology

| Branch | Purpose |
|---|---|
| `<MAIN_BRANCH>` | Trunk — all feature PRs target this branch |
| `feature/<domain>` | Short-lived branch, cut from `<MAIN_BRANCH>` — merge within a day or two |
| `hotfix/<name>` | Urgent fixes, also cut from `<MAIN_BRANCH>` |

## Rules

- Never push directly to `<MAIN_BRANCH>` — it is PR-only.
- Keep feature branches short-lived (hours to a couple of days); use feature flags for incomplete work.
- Every commit to `<MAIN_BRANCH>` must leave the build and tests green.
- Use Conventional Commits prefixes: `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`.
- Delete feature branches after merging.
```

---

### 8b. Code style standard

```bash
mkdir -p <DOCS_ROOT>/standards/code-style
```

Write `<DOCS_ROOT>/standards/code-style/design.md` using the linting tools detected in Steps 2–3. Include only the sections relevant to the detected stacks. Do not include commands — those live in skills.

**Python section** (include if Python stack detected):

```markdown
## Python

- Linter: **ruff**. Configuration in `pyproject.toml` under `[tool.ruff]`.
  <!-- Replace with flake8 / pylint if ruff was not detected -->
- All public functions and classes must have type annotations.
- Docstrings for public APIs only; inline comments for non-obvious invariants only.
- Maximum line length: 88 characters (ruff default).
```

**TypeScript / React section** (include if JS/TS stack detected):

```markdown
## TypeScript / React

- Linter: **ESLint**. Configuration in `eslint.config.*` or `.eslintrc.*`.
  <!-- Add Prettier note if detected in devDependencies -->
- TypeScript strict mode must remain enabled.
- Prefer named exports over default exports.
- One component per file; filename matches the component name in PascalCase.
```

**General section** (always include):

```markdown
## General

- No commented-out code committed to the repository.
- No TODO / FIXME comments — open an issue instead.
- PR descriptions must reference the relevant spec domain.
```

---

### 8c. Docs index

```bash
mkdir -p <DOCS_ROOT>
```

Write `<DOCS_ROOT>/INDEX.md` with the Standards section pre-populated from the standards just created:

```markdown
# Documentation Index

## Standards

| Standard | Description |
|---|---|
| [Branching model](standards/branching/design.md) | Branch topology and commit conventions |
| [Code style](standards/code-style/design.md) | Linting tools and coding conventions |

## Specs

| Domain | Status | Summary |
|---|---|---|

## Decisions

| ADR | Status | Summary |
|---|---|---|
```

---

### 8d. Decisions directory

```bash
mkdir -p <DOCS_ROOT>/decisions
touch <DOCS_ROOT>/decisions/.gitkeep
```

---

### 8e. AGENTS.md

Write `AGENTS.md` at the repo root. This file is a routing map only — no rules, no explanations.

```markdown
## Standards

| Topic | Document |
|---|---|
| Branching model | `<DOCS_ROOT>/standards/branching/design.md` |
| Code style | `<DOCS_ROOT>/standards/code-style/design.md` |

## Skill routing

| Task type | Skill |
|---|---|
| Any code change | `/sdd:ship` |
| Review a PR | `/sdd:review-pr` |
```

---

## Step 9: Commit

Check whether the repo has any commits:

```bash
git log --oneline -1 2>/dev/null || echo NO_COMMITS
```

Determine which sdd-related files exist and are untracked or modified. Substitute `<DOCS_ROOT>` with the actual resolved path (from `docs.root` in the confirmed config, defaulting to `docs`) before running:

```bash
git status --short \
  .claude/sdd/config.json \
  .claude/settings.json \
  AGENTS.md \
  <DOCS_ROOT>/INDEX.md \
  <DOCS_ROOT>/decisions/.gitkeep \
  <DOCS_ROOT>/standards/branching/design.md \
  <DOCS_ROOT>/standards/code-style/design.md \
  2>/dev/null
```

Stage only files that appear in that output, then commit:

- **NO_COMMITS** (fresh repo): commit message `chore: install sdd-harness plugin`
- **Has commits**: commit message `chore: initialise sdd-harness — config and docs scaffold`

Report the commit hash. Suggest `/sdd:ship <feature>` as the next step.
