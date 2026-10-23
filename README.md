# agent-framework

An open-source framework of reusable [Claude Code plugins](https://code.claude.com/docs/en/plugins)
for driving software work with an agent.

| Plugin | For |
|---|---|
| **`sdd`** | The pipeline — **spec → plan → implement → QA → publish**, with embedded critic gates and a TDD implement loop |
| **`render`** | Perceptual work — domains where a failure is something you *see* rather than something that throws |
| **`ci-runner`** | CI on your own machine — a `ci-runner` command that installs a self-hosted GitHub Actions runner and switches a repo between it and GitHub-hosted runners |

**Framework, not a hosted service.** Everything runs inside your own Claude Code sessions and
your own repository. No account, server or external infrastructure is required.

## Tech stack

The plugins are Markdown skills, agents and standards for Claude Code, plus a JSON config schema.
The installers, gates and tests are Bash and Python 3 (standard library only). Both plugins are
stack-agnostic: each consuming repo describes its own toolchain in `.claude/sdd/config.json`.

## Getting started

Copy the harness into your project and commit it:

```bash
git clone https://github.com/zenithml/agent-framework.git
./agent-framework/scripts/install-skills.sh /path/to/your-project
cd /path/to/your-project && git add AGENTS.md .claude/ .agents/ && git commit -m "chore: install sdd harness"
```

To also wire the project for Codex, add `--harness claude,codex`. Skills are exposed through a
symlink, native subagents read the canonical Markdown roles, and MCP definitions are synced
from `.mcp.json`; see [Using Codex](docs/installation.md#using-codex). `agy` is covered by default.

Then open Claude Code in your project, run `/sdd-init` once, and `/ship <feature>` to start the
pipeline. To install through the GitHub marketplace or as a vendored copy instead, see
[Installation](docs/installation.md).

## Working on this framework

Launch Claude or Codex from this checkout's root. Discovery links expose the canonical
`plugins/sdd/skills` to both clients, and `.claude/agents` exposes the canonical roles to
Claude. Use `/ship` in Claude or `$ship` in Codex; no plugin installation is needed for
this source checkout. Consumer plugin installations still use `/sdd:ship`.

## Documentation

| Guide | Covers |
|---|---|
| [Installation](docs/installation.md) | Flat copy, GitHub marketplace and vendored copy, and how to update each |
| [Plugins](docs/plugins.md) | What `sdd`, `render` and `ci-runner` contain, and every skill |
| [Configuration](docs/configuration.md) | What `sdd-init` sets up, `.claude/sdd/config.json`, placeholders, the SessionStart hook |
| [Branching](docs/branching.md) | GitHub Flow (default), trunk-based and Gitflow |
| [Docs index](docs/INDEX.md) | Standards, research, and everything else in `docs/` |

## Contributing, license and security

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for local development, the checks to run, and
versioning. The project is licensed under the [Apache License 2.0](LICENSE), and contributions
are accepted under the same license. To report a vulnerability, follow [`SECURITY.md`](SECURITY.md)
rather than opening a public issue.
