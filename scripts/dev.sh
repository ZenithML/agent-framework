#!/usr/bin/env bash
#
# dev.sh — start Claude Code with this checkout's plugins loaded live.
#
# `--plugin-dir` reads the plugin straight from the working tree for this session
# only: nothing is installed or cached, so there is no version to bump and no
# reinstall after an edit. Run /reload-plugins in the session to pick up changes.
# Skills keep their namespace (/sdd:ship, /sdd:create-pr).
#
# Usage:
#   scripts/dev.sh [--with-render] [--with-ci-runner] [claude args...]

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v claude >/dev/null 2>&1 || { echo "dev.sh requires the claude CLI on PATH" >&2; exit 1; }

DIRS=(--plugin-dir "$ROOT/plugins/sdd")
while [[ "${1:-}" == --with-* ]]; do
  case "$1" in
    --with-render) DIRS+=(--plugin-dir "$ROOT/plugins/render") ;;
    --with-ci-runner) DIRS+=(--plugin-dir "$ROOT/plugins/ci-runner") ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

# An installed copy of the same plugin is the usual source of "I edited it and nothing changed".
if claude plugin list 2>/dev/null | grep -q '^  ❯ sdd@'; then
  echo "dev.sh: an installed sdd@... plugin exists (see 'claude plugin list'); if the session" >&2
  echo "        seems to run stale skills, disable or uninstall it so only the live copy loads." >&2
fi

exec claude "${DIRS[@]}" "$@"
