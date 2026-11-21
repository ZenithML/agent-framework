#!/usr/bin/env python3
"""evidence: before/after evidence for refactors, migrations and productionization.

Harness-agnostic (python3 standard library only). Two subcommands:

  snapshot  run the project's configured commands from .claude/sdd/config.json and record, for
            each, whether it passed and how long it took, plus the numbers a script can read
            from its output: test counts, line coverage, mutation score, benchmark timings,
            any `METRIC name=value` lines, and the size of the given paths.
  compare   diff two snapshots, print a Markdown table, and exit 1 on any regression: a check
            that passed and now fails, more failing or fewer passing tests, coverage or
            mutation score down beyond a tolerance, a slower benchmark, or a check that was
            measured before and is missing after.

Usage:
  evidence.py snapshot --label <name> [--out DIR] [--config PATH] [--only test,lint,...]
                       [--paths P ...] [--metric-cmd CMD ...] [--bench-runs N]
                       [--timeout SECONDS] [--json]
  evidence.py compare BEFORE.json AFTER.json [--max-coverage-drop PTS] [--max-mutation-drop PTS]
                       [--max-bench-regression PCT] [--allow-fewer-tests]
                       [--lower-is-better NAME ...] [--higher-is-better NAME ...]
                       [--max-metric-regression PCT] [--md FILE] [--json]
Exit:  0 pass, 1 regression (compare) or a check that could not run (snapshot), 2 usage.

Commands come from `commands.<name>` in the config. A `{changed_files}` placeholder (used by
`commands.mutate`) is filled with --paths; without --paths that command is skipped and noted.
`commands.bench` runs --bench-runs times (default 5) and records the median wall time.
--metric-cmd runs an extra command only for the `METRIC` lines it prints (for example a count of
remaining uses of an old API); a failing --metric-cmd is a usage error, not evidence.
Snapshots land in --out (default .review/evidence) as <label>.json; a .review/ directory gets a
`.gitignore` of `*` so evidence is never committed by accident.
"""
import argparse
import datetime
import json
import re
import shlex
import statistics
import subprocess
import sys
import time
from pathlib import Path

VERSION = 1
CHECKS = ["typecheck", "lint", "build", "test", "coverage", "mutate", "bench"]
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
METRIC = re.compile(r"^\s*METRIC\s+([A-Za-z0-9_.:-]+)\s*=\s*(-?\d+(?:\.\d+)?)", re.M)
SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv", ".next",
             "coverage", ".review", "target", ".turbo"}
TAIL = 40


# ---------------------------------------------------------------- output parsers

def clean(text):
    return ANSI.sub("", text or "")


def parse_tests(out):
    """Passed/failed counts from common runners' summaries, or None."""
    out = clean(out)
    # Jest: "Tests:       1 failed, 10 passed, 11 total"; Vitest: "Tests  2 failed | 10 passed (12)"
    for line in reversed(out.splitlines()):
        if re.match(r"\s*Tests:?\s", line) and re.search(r"\d+ (passed|failed)", line):
            p = re.search(r"(\d+) passed", line)
            f = re.search(r"(\d+) failed", line)
            if p or f:
                return {"passed": int(p.group(1)) if p else 0, "failed": int(f.group(1)) if f else 0}
    # pytest: "==== 3 failed, 10 passed, 1 skipped in 0.52s ===="
    for line in reversed(out.splitlines()):
        if re.search(r"\b(passed|failed|error)s?\b.* in [\d.]+s", line):
            p = re.search(r"(\d+) passed", line)
            f = re.search(r"(\d+) failed", line)
            e = re.search(r"(\d+) errors?", line)
            return {"passed": int(p.group(1)) if p else 0,
                    "failed": (int(f.group(1)) if f else 0) + (int(e.group(1)) if e else 0)}
    # node --test / TAP: "# pass 10" "# fail 0"
    p = re.findall(r"^# pass (\d+)", out, re.M)
    if p:
        f = re.findall(r"^# fail (\d+)", out, re.M)
        return {"passed": int(p[-1]), "failed": int(f[-1]) if f else 0}
    # unittest: "Ran 12 tests in 0.01s" then "OK" or "FAILED (failures=1, errors=2)"
    ran = re.findall(r"^Ran (\d+) tests? in", out, re.M)
    if ran:
        total = int(ran[-1])
        bad = sum(int(n) for n in re.findall(r"(?:failures|errors)=(\d+)", out))
        return {"passed": total - bad, "failed": bad}
    # go test -v: count "--- PASS" / "--- FAIL"
    gp, gf = len(re.findall(r"^\s*--- PASS", out, re.M)), len(re.findall(r"^\s*--- FAIL", out, re.M))
    if gp or gf:
        return {"passed": gp, "failed": gf}
    return None


def coverage_from_files(root, since):
    """Line coverage % from a report written during this run, or None."""
    def fresh(p):
        return p.is_file() and p.stat().st_mtime >= since - 1
    p = root / "coverage" / "coverage-summary.json"          # istanbul / v8 json-summary
    if fresh(p):
        try:
            return float(json.loads(p.read_text())["total"]["lines"]["pct"])
        except (ValueError, KeyError, TypeError):
            pass
    p = root / "coverage.json"                                # coverage.py `coverage json`
    if fresh(p):
        try:
            return float(json.loads(p.read_text())["totals"]["percent_covered"])
        except (ValueError, KeyError, TypeError):
            pass
    for rel in ("coverage.xml", "coverage/cobertura-coverage.xml"):  # Cobertura
        p = root / rel
        if fresh(p):
            m = re.search(r'<coverage[^>]*\bline-rate="([\d.]+)"', p.read_text(errors="replace"))
            if m:
                return round(float(m.group(1)) * 100, 2)
    return None


def coverage_from_output(out):
    out = clean(out)
    m = re.findall(r"^All files\s*\|\s*([\d.]+)\s*\|\s*[\d.]+\s*\|\s*[\d.]+\s*\|\s*([\d.]+)", out, re.M)
    if m:                                                     # istanbul text: % Lines is column 4
        return float(m[-1][1])
    m = re.findall(r"^TOTAL\s.*?(\d+(?:\.\d+)?)%\s*$", out, re.M)  # coverage.py report
    if m:
        return float(m[-1])
    m = re.findall(r"coverage: ([\d.]+)% of statements", out)  # go test -cover
    if m:
        return float(m[-1])
    return None


def mutation_from_files(root, since):
    p = root / "reports" / "mutation" / "mutation.json"       # Stryker mutation-testing-report-schema
    if not (p.is_file() and p.stat().st_mtime >= since - 1):
        return None
    try:
        files = json.loads(p.read_text())["files"]
    except (ValueError, KeyError, TypeError):
        return None
    detected = valid = 0
    for f in files.values():
        for m in f.get("mutants", []):
            s = m.get("status")
            if s in ("CompileError", "RuntimeError", "Ignored"):
                continue
            valid += 1
            detected += s in ("Killed", "Timeout")
    return round(100 * detected / valid, 2) if valid else None


def mutation_from_output(out):
    out = clean(out)
    m = re.findall(r"mutation score[^\d\n]*([\d.]+)", out, re.I)  # Stryker, mutmut wrappers, generic
    if m:
        return float(m[-1])
    m = re.findall(r"Killed \d+ \((\d+)%\)", out)                  # PIT
    if m:
        return float(m[-1])
    m = re.search(r"(\d+) missed, (\d+) caught", out)              # cargo-mutants
    if m:
        missed, caught = int(m.group(1)), int(m.group(2))
        return round(100 * caught / (missed + caught), 2) if missed + caught else None
    return None


def metrics_from_output(out):
    return {name: float(v) for name, v in METRIC.findall(clean(out))}


def size_of(root, paths):
    files = lines = 0
    for rel in paths:
        base = (root / rel)
        items = [base] if base.is_file() else (p for p in base.rglob("*") if p.is_file())
        for p in items:
            if any(part in SKIP_DIRS for part in p.relative_to(root).parts[:-1]):
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            files += 1
            lines += sum(1 for line in text.splitlines() if line.strip())
    return {"files": files, "lines": lines}


# ---------------------------------------------------------------- snapshot

def git(root, *args):
    try:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def run(cmd, root, timeout):
    start = time.time()
    try:
        proc = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True,
                              timeout=timeout)
        code, out = proc.returncode, (proc.stdout or "") + "\n" + (proc.stderr or "")
    except subprocess.TimeoutExpired as e:
        code = 124
        out = clean((e.stdout or b"").decode(errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or ""))
        out += f"\n[evidence] timed out after {timeout}s"
    return code, out, round(time.time() - start, 3), start


def snapshot(args):
    root = Path(args.root).resolve()
    cfg_path = root / args.config
    try:
        cfg = json.loads(cfg_path.read_text())
    except OSError:
        print(f"cannot read {cfg_path}; run /sdd:sdd-init or pass --config", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"{cfg_path} is not valid JSON: {e}", file=sys.stderr)
        return 2
    commands = cfg.get("commands", {})
    only = [c.strip() for c in args.only.split(",")] if args.only else CHECKS
    unknown = [c for c in only if c not in CHECKS]
    if unknown:
        print(f"unknown check(s): {', '.join(unknown)}; choose from {', '.join(CHECKS)}", file=sys.stderr)
        return 2

    snap = {"version": VERSION, "label": args.label,
            "created": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
            "git": {"sha": git(root, "rev-parse", "HEAD"), "branch": git(root, "branch", "--show-current"),
                    "dirty": bool(git(root, "status", "--porcelain"))},
            "paths": args.paths, "commands": {}, "skipped": {}, "tests": None, "coverage": None,
            "mutation": None, "bench": None, "metrics": {}, "size": None}

    for name in only:
        cmd = commands.get(name)
        if not cmd:
            snap["skipped"][name] = f"commands.{name} is not configured"
            continue
        if "{changed_files}" in cmd:
            if not args.paths:
                snap["skipped"][name] = "needs --paths to fill {changed_files}"
                continue
            cmd = cmd.replace("{changed_files}", " ".join(shlex.quote(p) for p in args.paths))
        runs = args.bench_runs if name == "bench" else 1
        durations, code, out, started = [], 0, "", time.time()
        for i in range(runs):
            code, out, secs, start = run(cmd, root, args.timeout)
            if i == 0:
                started = start
            durations.append(secs)
            if code != 0:
                break
        snap["commands"][name] = {"cmd": cmd, "exit": code, "ok": code == 0,
                                  "seconds": durations[0] if runs == 1 else statistics.median(durations),
                                  "tail": "\n".join(clean(out).rstrip().splitlines()[-TAIL:])}
        snap["metrics"].update(metrics_from_output(out))
        if name == "test" or (name == "coverage" and snap["tests"] is None):
            snap["tests"] = parse_tests(out) or snap["tests"]
        if name == "coverage":
            found = coverage_from_files(root, started)
            snap["coverage"] = found if found is not None else coverage_from_output(out)
        if name == "mutate":
            found = mutation_from_files(root, started)
            snap["mutation"] = found if found is not None else mutation_from_output(out)
        if name == "bench" and code == 0:
            snap["bench"] = {"runs": durations, "median": statistics.median(durations)}
    for cmd in args.metric_cmd:
        code, out, _, _ = run(cmd, root, args.timeout)
        found = metrics_from_output(out)
        if code != 0 or not found:
            print(f"--metric-cmd failed or printed no METRIC line: {cmd}\n{clean(out)[-2000:]}", file=sys.stderr)
            return 2
        snap["metrics"].update(found)
    if "coverage" in snap["metrics"]:
        snap["coverage"] = snap["metrics"]["coverage"]
    if "mutation_score" in snap["metrics"]:
        snap["mutation"] = snap["metrics"]["mutation_score"]
    if args.paths:
        snap["size"] = size_of(root, args.paths)

    out_dir = root / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    review = root / ".review"
    if out_dir.resolve().is_relative_to(review.resolve()) and not (review / ".gitignore").exists():
        (review / ".gitignore").write_text("*\n")
    target = out_dir / f"{args.label}.json"
    target.write_text(json.dumps(snap, indent=2) + "\n")

    if args.json:
        print(json.dumps(snap, indent=2))
    else:
        print(f"[evidence] {args.label} at {snap['git']['sha'][:12] or 'no git'}"
              f"{' (dirty tree)' if snap['git']['dirty'] else ''} -> {target}")
        for name, c in snap["commands"].items():
            print(f"  {name}: {'pass' if c['ok'] else 'FAIL (exit %d)' % c['exit']} in {c['seconds']}s")
        for name, why in snap["skipped"].items():
            print(f"  {name}: skipped, {why}")
    return 0


# ---------------------------------------------------------------- compare

def fmt(v):
    if v is None:
        return "n/a"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def compare_snaps(before, after, opts):
    rows, problems = [], []

    def row(check, b, a, change, result):
        rows.append({"check": check, "before": fmt(b), "after": fmt(a), "change": change, "result": result})
        if result in ("regressed", "failing"):
            problems.append(f"{check}: {fmt(b)} -> {fmt(a)} ({result})")

    for name in CHECKS:
        b, a = before["commands"].get(name), after["commands"].get(name)
        if not b and not a:
            continue
        if b and not a:
            row(name, "pass" if b["ok"] else "fail", None, "not measured after", "regressed")
            continue
        if a and not b:
            row(name, None, "pass" if a["ok"] else "fail", "new check", "info" if a["ok"] else "regressed")
            continue
        result = "ok" if a["ok"] and b["ok"] else "improved" if a["ok"] else \
            "regressed" if b["ok"] else "failing"
        row(name, "pass" if b["ok"] else "fail", "pass" if a["ok"] else "fail", "", result)

    bt, at = before.get("tests"), after.get("tests")
    if bt and at:
        df = at["failed"] - bt["failed"]
        row("failing tests", bt["failed"], at["failed"], f"{df:+d}",
            "regressed" if df > 0 else "improved" if df < 0 else "failing" if at["failed"] else "ok")
        dp = at["passed"] - bt["passed"]
        row("passing tests", bt["passed"], at["passed"], f"{dp:+d}",
            "regressed" if dp < 0 and not opts.allow_fewer_tests else "improved" if dp > 0 else "ok")
    elif bt and not at:
        row("test counts", f"{bt['passed']} passed", None, "not readable after", "regressed")

    def pct_row(label, b, a, max_drop):
        if b is None and a is None:
            return
        if b is not None and a is None:
            row(label, b, a, "not measured after", "regressed")
            return
        if b is None:
            row(label, b, a, "new", "info")
            return
        d = round(a - b, 2)
        row(label, b, a, f"{d:+g} pts", "regressed" if d < -max_drop else "improved" if d > 0 else "ok")

    pct_row("line coverage %", before.get("coverage"), after.get("coverage"), opts.max_coverage_drop)
    pct_row("mutation score %", before.get("mutation"), after.get("mutation"), opts.max_mutation_drop)

    bb, ab = before.get("bench"), after.get("bench")
    if bb and ab:
        pct = round(100 * (ab["median"] - bb["median"]) / bb["median"], 1) if bb["median"] else 0.0
        row("bench median s", bb["median"], ab["median"], f"{pct:+g}%",
            "regressed" if pct > opts.max_bench_regression else "improved" if pct < -opts.max_bench_regression else "ok")
    elif bb and not ab:
        row("bench median s", bb["median"], None, "not measured after", "regressed")

    bm, am = before.get("metrics", {}), after.get("metrics", {})
    for name in sorted(set(bm) | set(am)):
        if name in ("coverage", "mutation_score"):
            continue
        b, a = bm.get(name), am.get(name)
        if b is None or a is None:
            gated = name in opts.lower_is_better or name in opts.higher_is_better
            row(name, b, a, "not measured after" if a is None else "new",
                "regressed" if a is None and gated else "info")
            continue
        pct = round(100 * (a - b) / abs(b), 1) if b else (0.0 if a == b else float("inf"))
        result = "info"
        if name in opts.lower_is_better:
            result = "regressed" if pct > opts.max_metric_regression else "improved" if a < b else "ok"
        elif name in opts.higher_is_better:
            result = "regressed" if -pct > opts.max_metric_regression else "improved" if a > b else "ok"
        row(name, b, a, f"{a - b:+g}", result)
    for name in list(opts.lower_is_better) + list(opts.higher_is_better):
        if name not in bm and name not in am:
            problems.append(f"{name}: gated metric was not measured in either snapshot")

    bs, as_ = before.get("size"), after.get("size")
    if bs and as_:
        row("lines of code", bs["lines"], as_["lines"], f"{as_['lines'] - bs['lines']:+d}", "info")
        row("files", bs["files"], as_["files"], f"{as_['files'] - bs['files']:+d}", "info")

    notes = []
    for label, s in (("before", before), ("after", after)):
        if s.get("git", {}).get("dirty"):
            notes.append(f"The {label} snapshot was taken on a dirty tree.")
        for name, why in s.get("skipped", {}).items():
            notes.append(f"{label}: {name} skipped ({why}).")
    return rows, problems, notes


def markdown(before, after, rows, problems, notes):
    head = (f"Evidence: `{before['label']}` ({before['git']['sha'][:7] or 'n/a'}) vs "
            f"`{after['label']}` ({after['git']['sha'][:7] or 'n/a'})")
    out = [head, "", "| Check | Before | After | Change | Result |", "|---|---|---|---|---|"]
    out += [f"| {r['check']} | {r['before']} | {r['after']} | {r['change']} | {r['result']} |" for r in rows]
    out.append("")
    out.append("**Verdict:** " + ("regressed: " + "; ".join(problems) if problems else "no regressions"))
    if notes:
        out += [""] + [f"- {n}" for n in notes]
    return "\n".join(out) + "\n"


def compare(args):
    snaps = []
    for p in (args.before, args.after):
        try:
            s = json.loads(Path(p).read_text())
        except OSError as e:
            print(f"cannot read {p}: {e}", file=sys.stderr)
            return 2
        except json.JSONDecodeError as e:
            print(f"{p} is not valid JSON: {e}", file=sys.stderr)
            return 2
        if not isinstance(s, dict) or s.get("version") != VERSION or "commands" not in s:
            print(f"{p} is not an evidence snapshot (version {VERSION})", file=sys.stderr)
            return 2
        snaps.append(s)
    before, after = snaps
    rows, problems, notes = compare_snaps(before, after, args)
    md = markdown(before, after, rows, problems, notes)
    if args.md:
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text(md)
    if args.json:
        print(json.dumps({"rows": rows, "problems": problems, "notes": notes,
                          "verdict": "regressed" if problems else "pass"}, indent=2))
    else:
        print(md, end="")
    return 1 if problems else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("snapshot", help="run configured checks and record the evidence")
    s.add_argument("--label", required=True, help="e.g. baseline, wave-1, after")
    s.add_argument("--out", default=".review/evidence", help="directory, relative to --root")
    s.add_argument("--root", default=".", help="repository root (default: current directory)")
    s.add_argument("--config", default=".claude/sdd/config.json", help="relative to --root")
    s.add_argument("--only", help="comma-separated subset of: " + ",".join(CHECKS))
    s.add_argument("--paths", nargs="*", default=[], help="area paths: fills {changed_files}, measures size")
    s.add_argument("--metric-cmd", action="append", default=[], metavar="CMD",
                   help="extra command run only for its METRIC lines (repeatable)")
    s.add_argument("--bench-runs", type=int, default=5)
    s.add_argument("--timeout", type=int, default=1800, help="seconds per command run")
    s.add_argument("--json", action="store_true")

    c = sub.add_parser("compare", help="diff two snapshots; exit 1 on regression")
    c.add_argument("before")
    c.add_argument("after")
    c.add_argument("--max-coverage-drop", type=float, default=0.5, help="percentage points (default 0.5)")
    c.add_argument("--max-mutation-drop", type=float, default=1.0, help="percentage points (default 1.0)")
    c.add_argument("--max-bench-regression", type=float, default=10.0, help="percent slower (default 10)")
    c.add_argument("--allow-fewer-tests", action="store_true",
                   help="do not fail when fewer tests pass (tests deliberately removed; say why in the PR)")
    c.add_argument("--lower-is-better", nargs="*", default=[], metavar="NAME")
    c.add_argument("--higher-is-better", nargs="*", default=[], metavar="NAME")
    c.add_argument("--max-metric-regression", type=float, default=5.0, help="percent (default 5)")
    c.add_argument("--md", help="also write the Markdown table to this file")
    c.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)
    if args.cmd == "snapshot":
        if args.bench_runs < 1:
            ap.error("--bench-runs must be at least 1")
        return snapshot(args)
    return compare(args)


if __name__ == "__main__":
    sys.exit(main())
