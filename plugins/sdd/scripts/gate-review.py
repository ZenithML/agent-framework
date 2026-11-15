#!/usr/bin/env python3
"""gate-review: mechanical check of .review/findings.json written by review-diff.

Harness-agnostic (python3 standard library only). It enforces the rules a script can decide:

  * the file is valid JSON in the findings v1 shape, with at most 15 findings
  * every `high` finding has a concrete `reproduction` (proof of bug), not a placeholder
  * the verdict follows the findings: `revise` when any finding is `high`, otherwise `pass`
  * two-pass rule: a `verification` pass lists only `high` findings, and with --previous
    the earlier file must be an `audit` pass of the same base and an earlier head; a
    `verification` file is never followed by another pass

With --final the gate also fails unless the verdict is `pass`, which is what the runbook
uses after the verification pass to decide whether the change may be published.

Usage: gate-review.py [findings.json] [--previous pass1.json] [--final] [--json]
       (default path: .review/findings.json)
Exit:  0 pass, 1 gate failed, 2 usage or unreadable file.
"""
import argparse
import json
import sys
from pathlib import Path

CATEGORIES = {"correctness", "security", "scope", "tests", "maintainability"}
SEVERITIES = {"high", "medium", "low"}
MAX_FINDINGS = 15
MIN_REPRO = 12


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")), None
    except OSError as e:
        return None, f"cannot read {path}: {e}"
    except json.JSONDecodeError as e:
        return None, f"{path} is not valid JSON: {e}"


def is_blank(value):
    return not isinstance(value, str) or not value.strip() or (value.strip().startswith("<") and value.strip().endswith(">"))


def check(doc, previous=None, final=False):
    problems = []
    if not isinstance(doc, dict):
        return ["top level must be a JSON object"]
    if doc.get("version") != 1:
        problems.append("version must be 1")
    for key in ("head", "base", "summary"):
        if is_blank(doc.get(key)):
            problems.append(f"'{key}' is required")
    mode = doc.get("pass_mode")
    if mode not in ("audit", "verification"):
        problems.append("pass_mode must be 'audit' or 'verification'")
    verdict = doc.get("verdict")
    if verdict not in ("pass", "revise"):
        problems.append("verdict must be 'pass' or 'revise'")
    findings = doc.get("findings")
    if not isinstance(findings, list):
        problems.append("findings must be a list")
        return problems
    if len(findings) > MAX_FINDINGS:
        problems.append(f"{len(findings)} findings; the maximum is {MAX_FINDINGS}")
    highs = 0
    for n, f in enumerate(findings, 1):
        if not isinstance(f, dict):
            problems.append(f"finding {n}: must be an object")
            continue
        where = f"finding {n} ({f.get('file', '?')}:{f.get('line', '?')})"
        if is_blank(f.get("file")):
            problems.append(f"{where}: 'file' is required")
        if not isinstance(f.get("line"), int) or isinstance(f.get("line"), bool) or f["line"] < 1:
            problems.append(f"{where}: 'line' must be a positive integer")
        if f.get("side") not in ("new", "old"):
            problems.append(f"{where}: 'side' must be 'new' or 'old'")
        if f.get("category") not in CATEGORIES:
            problems.append(f"{where}: 'category' must be one of {sorted(CATEGORIES)}")
        for key in ("summary", "failure_scenario"):
            if is_blank(f.get(key)):
                problems.append(f"{where}: '{key}' is required")
        sev = f.get("severity")
        if sev not in SEVERITIES:
            problems.append(f"{where}: 'severity' must be one of {sorted(SEVERITIES)}")
        if sev == "high":
            highs += 1
            repro = f.get("reproduction")
            if is_blank(repro) or len(repro.strip()) < MIN_REPRO:
                problems.append(f"{where}: high finding has no proof of bug; give a failing test or exact trace in 'reproduction', or downgrade it")
        if mode == "verification" and sev != "high":
            problems.append(f"{where}: a verification pass lists only unresolved high findings and proven regressions, not '{sev}'")
    if verdict in ("pass", "revise") and (verdict == "revise") != (highs > 0):
        problems.append(f"verdict '{verdict}' contradicts {highs} high finding(s): revise exactly when any finding is high")
    if previous is not None:
        if not isinstance(previous, dict):
            problems.append("previous file must be a JSON object")
        else:
            if mode != "verification":
                problems.append("with --previous this file must have pass_mode 'verification'")
            if previous.get("pass_mode") != "audit":
                problems.append("previous file must be an 'audit' pass: a review converges in at most two passes")
            if previous.get("base") != doc.get("base"):
                problems.append("base differs from the previous pass; both passes review the same change")
            if previous.get("head") == doc.get("head"):
                problems.append("head equals the previous pass; verification must follow the fix commit")
    if final and verdict != "pass":
        problems.append("final verdict is not 'pass'; fix or escalate, there is no third review pass")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("findings", nargs="?", default=".review/findings.json")
    ap.add_argument("--previous", help="the pass-1 findings file, kept before pass 2 overwrote the main one")
    ap.add_argument("--final", action="store_true", help="also require verdict 'pass'")
    ap.add_argument("--json", action="store_true", help="print a JSON result")
    args = ap.parse_args(argv)
    doc, err = load(args.findings)
    previous = None
    if err is None and args.previous:
        previous, err = load(args.previous)
    if err:
        print(f"gate-review: {err}", file=sys.stderr)
        return 2
    problems = check(doc, previous, args.final)
    if args.json:
        print(json.dumps({"gate": "review", "ok": not problems, "problems": problems}))
    elif problems:
        for p in problems:
            print(f"FAIL: {p}")
        print(f"gate-review: FAIL ({len(problems)} problem(s))")
    else:
        print("gate-review: PASS")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
