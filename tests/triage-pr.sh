#!/usr/bin/env bash
#
# triage-pr.sh — run the unit and CLI tests for the triage-pr script.
#
# Works from any directory: it resolves the repo root from its own location.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

python3 -m unittest discover -s tests/triage-pr -p 'test_*.py'
