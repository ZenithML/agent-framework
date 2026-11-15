#!/usr/bin/env python3
"""gate-design: mechanical check of a design.md before implementation starts.

Harness-agnostic (python3 standard library only), so Claude Code, Codex and agy run the same
check. It validates what a script can decide and leaves judgment to the critic:

  * the "Failure Modes & Degradation Matrix" section exists and parses as a table
  * strict: it covers Transport/Network, Concurrency/State and Boundary & Payloads
  * every row has all four cells filled, with no template placeholder left in them
  * every row's Test Scenario maps to a scenario in the Test Scenarios section
  * the Test Scenarios section has at least one BDD scenario

A row maps when its Test Scenario cell is contained in the Test Scenarios section (ignoring
case, punctuation and spacing), or contains the text of one of its `**Scenario:**` lines.

Usage: gate-design.py <design.md> [--profile fast|standard|strict] [--json]
Exit:  0 pass (or skipped by profile), 1 gate failed, 2 usage or unreadable file.

Profiles: fast skips the gate; standard needs a BDD scenario and, if the matrix is present,
validates it; strict also requires the matrix and its three categories.
"""
import argparse
import json
import re
import sys
from pathlib import Path

MATRIX_HEADING = "Failure Modes & Degradation Matrix"
COLUMNS = ["category", "failure condition", "expected system behavior", "test scenario"]
REQUIRED_CATEGORIES = ["transport/network", "concurrency/state", "boundary & payloads"]


def norm(text):
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text.lower()).split())


def section(text, heading, level=2):
    """Body of the first heading with this title, up to the next heading of the same or higher
    level. Lines inside fenced code blocks are never headings."""
    lines = text.splitlines()
    in_fence, start = False, None
    for i, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"(#{1,6})\s+(.*?)\s*$", line)
        if not m:
            continue
        if start is None:
            if len(m[1]) == level and m[2] == heading:
                start = i + 1
        elif len(m[1]) <= level:
            return "\n".join(lines[start:i])
    return None if start is None else "\n".join(lines[start:])


def table_rows(body):
    rows = []
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c) and any(cells):
            continue
        rows.append(cells)
    return rows


def is_placeholder(cell):
    return not cell.strip() or bool(re.fullmatch(r"<[^<>]*>", cell.strip())) or norm(cell) in {"tbd", "todo", "n a", "none"}


def check(text, profile):
    problems = []
    if profile == "fast":
        return problems, True
    scenarios = section(text, "Test Scenarios") or ""
    bdd = re.findall(r"(?m)^\s*[-*]\s+\*\*Scenario:\*\*\s*(.+)$", scenarios)
    bdd = [b for b in bdd if not re.fullmatch(r"Given \.\.\. When \.\.\. Then \.\.\.", b.strip())]
    if not bdd:
        problems.append("Test Scenarios has no BDD scenario (a '- **Scenario:** Given ... When ... Then ...' line)")

    body = section(text, MATRIX_HEADING)
    if body is None:
        if profile == "strict":
            problems.append(f"missing '## {MATRIX_HEADING}' section")
        return problems, False
    rows = table_rows(body)
    if not rows:
        problems.append(f"'{MATRIX_HEADING}' has no table")
        return problems, False
    header = [c.lower() for c in rows[0]]
    if header != COLUMNS:
        problems.append(f"matrix columns must be {' | '.join(COLUMNS)} (got {' | '.join(header)})")
        return problems, False
    data = rows[1:]
    if not data:
        problems.append("matrix has no rows")
    hay = norm(scenarios)
    seen = set()
    for n, row in enumerate(data, 1):
        if len(row) != 4:
            problems.append(f"matrix row {n}: expected 4 cells, found {len(row)}")
            continue
        cat, cond, behavior, scenario = row
        seen.add(norm(cat))
        for name, cell in zip(COLUMNS, row):
            if is_placeholder(cell):
                problems.append(f"matrix row {n} ({cat or '?'}): '{name}' is empty or still a placeholder")
        if not is_placeholder(scenario):
            cell = norm(scenario)
            mapped = cell in hay or any(norm(b) and norm(b) in cell for b in bdd)
            if not mapped:
                problems.append(f"matrix row {n} ({cat}): Test Scenario '{scenario}' does not match any scenario in Test Scenarios")
    if profile == "strict":
        for need in REQUIRED_CATEGORIES:
            if not any(norm(need) in s for s in seen):
                problems.append(f"matrix does not cover category '{need}'")
    return problems, False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("design", help="path to design.md")
    ap.add_argument("--profile", choices=["fast", "standard", "strict"], default="standard")
    ap.add_argument("--json", action="store_true", help="print a JSON result")
    args = ap.parse_args(argv)
    try:
        text = Path(args.design).read_text(encoding="utf-8")
    except OSError as e:
        print(f"gate-design: cannot read {args.design}: {e}", file=sys.stderr)
        return 2
    problems, skipped = check(text, args.profile)
    if args.json:
        print(json.dumps({"gate": "design", "profile": args.profile, "skipped": skipped,
                          "ok": not problems, "problems": problems}))
    elif skipped:
        print(f"gate-design: SKIP (profile {args.profile})")
    elif problems:
        for p in problems:
            print(f"FAIL: {p}")
        print(f"gate-design: FAIL ({len(problems)} problem(s), profile {args.profile})")
    else:
        print(f"gate-design: PASS (profile {args.profile})")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
