# Agent guidance

## SDD harness

| Task | Entry point |
|---|---|
| Ship a change | Claude Code: `/ship`; Codex: `$ship` or `/skills` |
| Write requirements or design | `/spec` or `/plan` (Codex: `$spec`, `$plan`) |
| Implement a task | `/implement` (Codex: `$implement`) |
| Independent review or observable QA | `/critique` or `/qa` (Codex: `$critique`, `$qa`) |
| Explore a running app, find and fix bugs | `/qa-explore` (Codex: `$qa-explore`); `--report-only` changes nothing |
| Open or review a pull request | `/create-pr` or `/review-pr` (Codex: `$create-pr`, `$review-pr`) |
| Bootstrap project configuration | `/sdd-init` (Codex: `$sdd-init`) |
| Inspect pipeline rules and delegation | `.claude/standards/agent-pipeline.md` |
| Read canonical role instructions | `.claude/agents/` (both clients use these Markdown files) |
| Refresh Codex MCP definitions after editing `.mcp.json` | `python3 .claude/sdd/sync_mcp.py` (Python 3.11+); add `--check` for drift |

Skills live in `.claude/skills/`; `.agents/skills` is their discovery symlink.
Project commands and branches live in `.claude/sdd/config.json`.
