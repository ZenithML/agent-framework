# Installation

Pick the method that matches your situation:

| Your situation | Method |
|---|---|
| **You just want it to work** — locally, on claude.ai/code, and in CI — with no install step that can silently skip on a fresh VM | **[Flat copy](#flat-copy-recommended)** (recommended) |
| You want every session to fetch the harness from GitHub, pinned or tracking `main` | **[GitHub marketplace](#github-marketplace)** |
| You want a frozen copy committed to your repo, pinned to a version, with no GitHub access needed at runtime | **[Vendored copy](#vendored-copy)** |

All three end the same way: run the onboarding skill once, then the **ship** skill to start the
pipeline. They differ only in *how the skills get into your repo*. Every method is exercised in
CI by [`tests/install-paths.sh`](../tests/install-paths.sh).

> **Command names differ by method.** Flat copy installs the skills **without** the `sdd:`
> namespace, so you invoke them as `/ship`, `/spec`, `/sdd-init`. The marketplace and vendored
> methods install them as a **plugin**, which keeps the namespace: `/sdd:ship`, `/sdd:spec`,
> `/sdd:sdd-init`. (The `sdd-init` name avoids clashing with Claude Code's built-in `/init`.)

After installing, see [Configuration](configuration.md) for what `sdd-init` sets up.

---

## Flat copy (recommended)

Copies the harness (skills, agents, standards, templates, config schema, and the SessionStart
hook) straight into your project's `.claude/` directory. They become ordinary committed files,
so **every session type loads them unconditionally**. There's no marketplace and no install step
to go wrong on a cloud VM.

**Step 1: get a checkout of this harness** (anywhere on your machine):

```bash
git clone https://github.com/zenithml/agent-framework.git
cd agent-framework
```

**Step 2: install it into your project.** Point the script at your project's root (add
`--dry-run` first if you want to preview, and `--with-render` to include the render plugin):

```bash
./scripts/install-skills.sh /path/to/your-project
```

The script does these things:
- copies `plugins/sdd/{skills,agents,standards,templates,config,hooks}` into
  `<your-project>/.claude/`
- rewrites the plugin's `${CLAUDE_PLUGIN_ROOT}` paths to repo-relative `.claude/` paths, and
  `/sdd:<skill>` references to `/<skill>` (flat-installed skills have no namespace)
- declares the SessionStart hook in `.claude/settings.json`
- symlinks `.agents/skills` to `.claude/skills`, so Antigravity (`agy`) and Codex discover the skills
  too (skipped with a warning if `.agents/skills` already exists)
- with `--harness codex`, also wires up Codex (see [Using Codex](#using-codex))
- writes a `.claude/sdd/.harness-version` stamp and a `.claude/sdd/.harness-manifest` that
  records each installed file's hash, so a later re-run can tell your edits from upstream changes

It refuses to write into a `.claude/` it didn't create unless you pass `--force`. With `--force`
it installs alongside your own skills and leaves them untouched.

**Step 3: commit the files in your project:**

```bash
cd /path/to/your-project
git add .claude/ .agents/   # plus .codex/ if you used --harness codex
git commit -m "chore: install sdd harness"
```

**Step 4: open Claude Code in your project and run `/sdd-init`.** Then run `/ship <feature>` to
start the pipeline.

**To update later:** `git pull` in your harness checkout, re-run
`./scripts/install-skills.sh /path/to/your-project`, and commit. The re-run updates harness
files you have not edited and deletes the ones a newer version no longer ships. Files you **have**
edited since the last install are kept. If upstream changed one of those too, the new upstream copy
is written to `.claude/sdd/upstream/<path>` for you to merge by hand (don't commit that directory),
or pass `--overwrite-local` to take the upstream version. An install from before the manifest
existed has no record of your edits, so its first re-run overwrites them. Check `git diff` after
that run. Compare `.claude/sdd/.harness-version` against this
repo's plugin version to see whether you are behind.

### Using Codex

`./scripts/install-skills.sh --harness claude,codex /path/to/your-project` (the `claude` entry is
implied, since `.claude/` stays the one canonical copy). A project can serve Claude Code, `agy` and
Codex at once. Codex has no plugin marketplace path here; flat copy is the supported route.

| Piece | Claude Code | Codex |
|---|---|---|
| Rules | `AGENTS.md` | `AGENTS.md` (same file) |
| Skills | `.claude/skills/` | `.agents/skills/`, a symlink to `.claude/skills/`; invoke with `$ship`, `$sdd-init` or `/skills` |
| Subagents | `.claude/agents/*.md` | `.codex/agents/*.toml`, **generated** from the `.md` files on every install. Edit the `.md`, never the `.toml` |
| MCP servers | `.mcp.json` | `.codex/config.toml`: the installer mirrors `.mcp.json` into a marked `[mcp_servers.*]` block and leaves the rest of the file alone |

Differences to know about:
- **Tool seal is advisory in Codex.** Codex agents have no `tools:` allowlist. The generated
  instructions restate each role's contract, and `reviewer`/`auditor` agents get
  `sandbox_mode = "read-only"`, but the verifier's "cannot read the implementation" guarantee is a
  prompt rule there, the weakest kind per the [harness standard](../plugins/sdd/standards/harness.md).
- **Models are not mapped.** `model: opus|sonnet` has no Codex equivalent, so generated agents inherit
  the session model. Set `[agents]` defaults in `.codex/config.toml` if you want otherwise.
- **MCP env interpolation.** Codex does not expand `${VAR}`. `Authorization: Bearer ${X}` becomes
  `bearer_token_env_var = "X"` and bare `${X}` values become forwarded env vars; other interpolation
  is forwarded with a warning.
- **Trust.** Codex reads project `.codex/` config only for a trusted project.
- **No SessionStart hook.** The remote-VM setup hook is Claude Code on the web only and is not
  installed for Codex.
- Re-run the installer after editing `.mcp.json` or an agent to refresh `.codex/`.

---

## GitHub marketplace

Each session fetches the plugin from GitHub. That fetch is an install step, and it can silently
skip on a fresh claude.ai/code or CI VM, so prefer [flat copy](#flat-copy-recommended) if
reliability there matters. You don't need a checkout of this repo; you only edit one file. The
repository is public, so no GitHub token is needed.

**Step 1: add two keys to your project's `.claude/settings.json`** (create the file if it does
not exist), then commit it so every teammate and CI session inherits the plugin:

```json
{
  "extraKnownMarketplaces": {
    "sdd-harness": {
      "source": { "source": "github", "repo": "zenithml/agent-framework" }
    }
  },
  "enabledPlugins": {
    "sdd@sdd-harness": true,
    "render@sdd-harness": true
  }
}
```

Omit the `render` line for projects with no visual output. Add `"ci-runner@sdd-harness": true`
for the `/ci-runner:setup` skill; the `ci-runner` command itself is installed with
`plugins/ci-runner/install.sh` from a checkout (see its [README](../plugins/ci-runner/README.md)).

To pin an exact version, add a `ref` to the source. Without one, the repo tracks the default
branch and picks up updates automatically:

```json
"source": { "source": "github", "repo": "zenithml/agent-framework", "ref": "v0.6.0" }
```

**Step 2: open Claude Code in your project and run `/sdd:sdd-init`.** Then run
`/sdd:ship <feature>` to start the pipeline.

> **Warning:** Do not add a directory marketplace for `sdd-harness` to your global
> `~/.claude/settings.json` unless you intend every local repository to resolve `sdd-harness`
> to that path. Claude Code keeps one source per marketplace name per machine.

---

## Vendored copy

Commits a frozen copy of the plugin into your repo (under `.claude/vendors/`) and enables it
through a *local* marketplace. It works offline and pins an exact version with no GitHub access
at runtime. Like the marketplace method, and unlike flat copy, the skills stay namespaced:
`/sdd:ship`, `/sdd:sdd-init`.

**Step 1: get a checkout of this harness** (anywhere on your machine):

```bash
git clone https://github.com/zenithml/agent-framework.git
cd agent-framework
```

**Step 2: vendor it into your project** (add `--dry-run` first to preview):

```bash
./scripts/vendor.sh /path/to/your-project
```

The vendor key defaults to your project's directory name (override it with `--name`). For a
project at `/home/alice/my-repo`, the script does three things:
- copies the plugin into `<your-project>/.claude/vendors/my-repo/`
- names that local marketplace `my-repo`
- updates `<your-project>/.claude/settings.json` to register the marketplace and enable
  `sdd@my-repo`

**Step 3: commit the files in your project:**

```bash
cd /path/to/your-project
git add .claude/
git commit -m "chore: vendor sdd plugin"
```

**Step 4: open Claude Code in your project and run `/sdd:sdd-init`.** Then run
`/sdd:ship <feature>` to start the pipeline.

**To update later:** `git pull` in your harness checkout and re-run
`./scripts/vendor.sh /path/to/your-project`. It is idempotent and overwrites the previous copy.
