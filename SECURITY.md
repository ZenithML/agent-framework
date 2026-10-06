# Security Policy

## Supported versions

Only the latest release on `main` receives security fixes. Pin a `ref` in your
marketplace config if you need a fixed version, and update it when a fix ships.

## Scope

This repository ships prose (skills, agents, standards, templates) plus a small
amount of executable code: the `SessionStart` hook in `plugins/sdd/hooks/`, the
installer scripts in `scripts/`, and the gates in `scripts/checks/`. Reports are
in scope when they concern any of these — for example, a skill or hook that
leads an agent to run untrusted input as a command, an installer that writes
outside its target directory, or a gate that can be made to pass on bad input.

Vulnerabilities in Claude Code itself should be reported to Anthropic, not here.

## Reporting a vulnerability

**Do not open a public issue.** Use GitHub's private vulnerability reporting:
the **Report a vulnerability** button on this repository's **Security** tab.

Please include the affected file and version, steps to reproduce, and the
impact you observed. You can expect an acknowledgement within 7 days and a
decision on a fix within 30 days. Reporters are credited in the release notes
unless they ask not to be.
