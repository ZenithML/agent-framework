#!/usr/bin/env bash
#
# check-all.sh — every mechanical gate this repo claims to have.
#
# Runs locally with nothing installed (python3 stdlib only) and in CI as the
# same command, so a green local run means the same thing CI means.
#
# Usage:
#   ./scripts/check-all.sh            # check this repo
#   ./scripts/check-all.sh <root>     # check another root (used by the fixture runner)
#
# Exit code: 0 if every gate passes, 1 if any fails.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKS_DIR="$SCRIPT_DIR/checks"
ROOT="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "check-all.sh requires python3 on PATH (stdlib only — no packages needed)" >&2
  exit 2
fi

GATES=(
  skill_frontmatter
  coverage_ratchet
  version_bump
  description_collision
  evals_present
  manifest_complete
  markdown_links
  agent_tools_declared
  agent_tool_seal
)

OVERALL=0
PASSED=0
FAILED=()

for gate in "${GATES[@]}"; do
  echo "== $gate =="
  if python3 "$CHECKS_DIR/$gate.py" "$ROOT"; then
    echo "   PASS"
    PASSED=$((PASSED + 1))
  else
    echo "   FAIL"
    FAILED+=("$gate")
    OVERALL=1
  fi
done

echo
echo "──────────────────────────────────────────"
if [ "$OVERALL" -eq 0 ]; then
  echo "All ${#GATES[@]} gates passed."
else
  echo "$PASSED/${#GATES[@]} gates passed. Failed: ${FAILED[*]}"
fi

exit $OVERALL
