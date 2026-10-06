# Configuration

Both plugins are stack-agnostic. Project-specific commands and paths come from a small
`.claude/sdd/config.json` in each consuming repo rather than being hardcoded.

## What `sdd-init` sets up

The `sdd-init` skill does four things:
1. detects your tech stack from `package.json`, `pyproject.toml` and `setup.py`, including
   monorepo layouts
2. shows you the resulting config for confirmation
3. writes `.claude/sdd/config.json`
4. commits the following docs scaffold:

```
AGENTS.md                              — routing map: standards + skill routing table
docs/
  INDEX.md                             — master index (Standards section pre-populated)
  standards/
    branching/design.md                — branch topology, naming rules, commit conventions
    code-style/design.md               — linting tools and coding conventions
  specs/<domain>/                      — created by /sdd:ship as features are developed
  decisions/                           — architectural decision records (empty, ready to use)
```

**Standards are stubs to grow into.** `sdd-init` fills in what it can detect: the branching
topology (see [Branching](branching.md)), branch names, and linting tools (ruff, ESLint,
Prettier). The team then adds project-specific rules, such as type annotation policy, component
conventions and performance budgets.

Standards contain rules in plain language for both humans and agents. They do not contain
implementation commands. Those live in skills, which read `.claude/sdd/config.json` for the real
toolchain specifics.

Templates for requirements, design, tasks and ADRs ship with the harness and the pipeline uses
them automatically. They live at `.claude/templates/docs/` for a flat install, or
`${CLAUDE_PLUGIN_ROOT}/templates/docs/` for the plugin methods.

## Writing the config by hand

`sdd-init` covers the common case. If you need to write `.claude/sdd/config.json` by hand, for
CI-only setup or an unusual toolchain, the full schema is
[`plugins/sdd/config/config.schema.json`](../plugins/sdd/config/config.schema.json). Example
configs:

- [`config.example.npm.json`](../plugins/sdd/config/config.example.npm.json): React / Node
- [`config.example.python.json`](../plugins/sdd/config/config.example.python.json): Python / FastAPI

Every field is optional. Without the file, skills auto-detect commands from manifests and
default branches to `main`.

### How placeholders resolve

Skills use placeholders that map to config keys:

| Placeholder | Config key |
|---|---|
| `<INSTALL_CMD>` | `commands.install` |
| `<TEST_CMD>` / `<TEST_CMD> <test-file>` | `commands.test` / `commands.testOne` |
| `<LINT_CMD>` · `<BUILD_CMD>` | `commands.lint` · `commands.build` |
| `<DEV_CMD>` · `<DEV_HOST_CMD>` | `commands.dev` · `commands.devHost` |
| `<SHOOT_CMD>` | `commands.shoot` |
| `<SOURCE_DIR>` | `source.dir` |
| `<MAIN_BRANCH>` · `<DEV_BRANCH>` | `branching.mainBranch` · `branching.devBranch` |
| `<feature-branch>` | `branching.featurePrefix` + `<domain>` |

## SessionStart hook for web and CI

The plugin ships a `SessionStart` hook (`hooks/hooks.json`) that runs automatically in
**remote sessions** (claude.ai/code and CI). It installs dependencies and runs the test suite,
driven by `.claude/sdd/config.json`. If a `GITHUB_PERSONAL_ACCESS_TOKEN` environment variable is
present, it also sets up the `gh` CLI; set the variable in your claude.ai project secrets or CI
environment.

The hook does nothing in local Claude Code sessions, so it is safe to leave enabled. Plugin
hooks load automatically once the plugin is enabled. The flat copy declares the hook in
`.claude/settings.json` for you.
