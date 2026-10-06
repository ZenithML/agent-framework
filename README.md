# agent-framework

An open-source framework of reusable [Claude Code plugins](https://code.claude.com/docs/en/plugins)
for driving software work with an agent.

| Plugin | For |
|---|---|
| **`sdd`** | The pipeline — **spec → plan → implement → QA → publish**, with embedded critic gates and a TDD implement loop |
| **`render`** | Perceptual work — domains where a failure is something you *see* rather than something that throws |

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
cd /path/to/your-project && git add .claude/ && git commit -m "chore: install sdd harness"
```

Then open Claude Code in your project, run `/sdd-init` once, and `/ship <feature>` to start the
pipeline. To install through the GitHub marketplace or as a vendored copy instead, see
[Installation](docs/installation.md).

## Documentation

| Guide | Covers |
|---|---|
| [Installation](docs/installation.md) | Flat copy, GitHub marketplace and vendored copy, and how to update each |
| [Plugins](docs/plugins.md) | What `sdd` and `render` contain, and every skill |
| [Configuration](docs/configuration.md) | What `sdd-init` sets up, `.claude/sdd/config.json`, placeholders, the SessionStart hook |
| [Branching](docs/branching.md) | GitHub Flow (default), trunk-based and Gitflow |
| [Docs index](docs/INDEX.md) | Standards, research, and everything else in `docs/` |

## Contributing, license and security

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for local development, the checks to run, and
versioning. The project is licensed under the [Apache License 2.0](LICENSE), and contributions
are accepted under the same license. To report a vulnerability, follow [`SECURITY.md`](SECURITY.md)
rather than opening a public issue.
