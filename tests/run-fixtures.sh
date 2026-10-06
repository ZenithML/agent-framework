#!/usr/bin/env bash
#
# run-fixtures.sh — negative controls for every gate.
#
# A gate that has never rejected anything is not known to work. For each gate
# there is a `pass/` fixture it must accept and a `fail/` fixture it must
# reject; this asserts both. A gate without fixtures is reported as untested
# and fails the run.

set -uo pipefail

TESTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$TESTS_DIR/.." && pwd)"
CHECKS_DIR="$ROOT/scripts/checks"
FIXTURES="$TESTS_DIR/fixtures/checks"

OVERALL=0

for gate_py in "$CHECKS_DIR"/*.py; do
  gate="$(basename "$gate_py" .py)"
  [ "${gate#_}" != "$gate" ] && continue   # skip _common.py

  dir="$FIXTURES/$gate"
  if [ ! -d "$dir/pass" ] || [ ! -d "$dir/fail" ]; then
    echo "UNTESTED  $gate — needs tests/fixtures/checks/$gate/{pass,fail}/"
    OVERALL=1
    continue
  fi

  out=$(python3 "$gate_py" "$dir/pass" 2>&1); rc=$?
  if [ $rc -ne 0 ]; then
    echo "BROKEN    $gate — rejected its own pass fixture (exit $rc)"
    echo "$out" | sed 's/^/            /'
    OVERALL=1
  else
    echo "ok        $gate accepts pass/"
  fi

  out=$(python3 "$gate_py" "$dir/fail" 2>&1); rc=$?
  if [ $rc -eq 0 ]; then
    echo "INERT     $gate — accepted its fail fixture, so the gate does not fire"
    OVERALL=1
  else
    echo "ok        $gate rejects fail/  ($(echo "$out" | grep -c 'FAIL ') finding(s))"
  fi
done

echo
if [ "$OVERALL" -eq 0 ]; then
  echo "Every gate accepts its pass fixture and rejects its fail fixture."
else
  echo "Fixture run failed — see above."
fi
exit $OVERALL
