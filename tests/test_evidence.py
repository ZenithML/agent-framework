"""Tests for plugins/sdd/scripts/evidence.py: output parsers, snapshot and compare."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/sdd/scripts/evidence.py"
spec = importlib.util.spec_from_file_location("evidence", SCRIPT)
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def py(code):
    """A shell command that runs a python3 one-liner, portable across shells."""
    return f'{sys.executable} -c "{code}"'


class ParserTests(unittest.TestCase):
    def test_test_counts_from_common_runners(self):
        cases = {
            "Tests:       1 failed, 10 passed, 11 total": (10, 1),            # Jest
            " Test Files  1 passed (1)\n      Tests  2 failed | 10 passed (12)": (10, 2),  # Vitest
            "===== 3 failed, 10 passed, 1 skipped in 0.52s =====": (10, 3),   # pytest
            "== 1 passed, 1 error in 0.1s ==": (1, 1),
            "# tests 4\n# pass 4\n# fail 0": (4, 0),                        # node --test
            "Ran 12 tests in 0.01s\n\nFAILED (failures=1, errors=2)": (9, 3),  # unittest
            "Ran 5 tests in 0.0s\n\nOK": (5, 0),
            "--- PASS: TestA (0.00s)\n--- FAIL: TestB (0.00s)": (1, 1),      # go test -v
        }
        for out, (p, f) in cases.items():
            with self.subTest(out=out):
                self.assertEqual(ev.parse_tests(out), {"passed": p, "failed": f})
        self.assertIsNone(ev.parse_tests("nothing to see"))

    def test_ansi_colour_is_ignored(self):
        self.assertEqual(ev.parse_tests("\x1b[32m      Tests  3 passed (3)\x1b[0m"), {"passed": 3, "failed": 0})

    def test_coverage_from_output(self):
        istanbul = "File      | % Stmts | % Branch | % Funcs | % Lines |\nAll files |   85.71 |    66.66 |     100 |   83.3 |"
        self.assertEqual(ev.coverage_from_output(istanbul), 83.3)
        self.assertEqual(ev.coverage_from_output("Name  Stmts  Miss  Cover\nTOTAL   120     12    90%"), 90.0)
        self.assertEqual(ev.coverage_from_output("ok  pkg  0.1s  coverage: 71.4% of statements"), 71.4)
        self.assertIsNone(ev.coverage_from_output("no coverage here"))

    def test_mutation_from_output(self):
        self.assertEqual(ev.mutation_from_output("Final mutation score of 75.00 is greater than"), 75.0)
        self.assertEqual(ev.mutation_from_output(">> Generated 10 mutations Killed 8 (80%)"), 80.0)
        self.assertEqual(ev.mutation_from_output("20 mutants tested in 3s: 5 missed, 15 caught"), 75.0)

    def test_metric_lines(self):
        out = "noise\nMETRIC p95_ms=120.5\n  METRIC bundle_kb = 300\nMETRIC bad=abc"
        self.assertEqual(ev.metrics_from_output(out), {"p95_ms": 120.5, "bundle_kb": 300.0})

    def test_coverage_and_mutation_report_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "coverage").mkdir()
            (root / "coverage/coverage-summary.json").write_text(json.dumps({"total": {"lines": {"pct": 64.2}}}))
            self.assertEqual(ev.coverage_from_files(root, 0), 64.2)
            (root / "reports/mutation").mkdir(parents=True)
            mutants = [{"status": s} for s in ["Killed", "Killed", "Timeout", "Survived", "NoCoverage", "Ignored"]]
            (root / "reports/mutation/mutation.json").write_text(json.dumps({"files": {"a.ts": {"mutants": mutants}}}))
            self.assertEqual(ev.mutation_from_files(root, 0), 60.0)
            # A report older than the run is stale and ignored.
            self.assertIsNone(ev.coverage_from_files(root, 10 ** 12))


class SnapshotCompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "src").mkdir()
        (self.root / "src/a.py").write_text("x = 1\n\ny = 2\n")
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules/skip.js").write_text("ignored\n")

    def tearDown(self):
        self.tmp.cleanup()

    def config(self, **commands):
        (self.root / ".claude/sdd").mkdir(parents=True, exist_ok=True)
        (self.root / ".claude/sdd/config.json").write_text(json.dumps({"commands": commands}))

    def snap(self, label, *extra):
        return subprocess.run([sys.executable, str(SCRIPT), "snapshot", "--label", label, "--root",
                               str(self.root), *extra], capture_output=True, text=True)

    def compare(self, *extra):
        d = self.root / ".review/evidence"
        return subprocess.run([sys.executable, str(SCRIPT), "compare", str(d / "baseline.json"),
                               str(d / "after.json"), *extra], capture_output=True, text=True)

    def test_snapshot_records_commands_metrics_and_size(self):
        self.config(test=py("print('Tests  4 passed (4)')"),
                    coverage=py("print('TOTAL 10 1 90%'); print('METRIC p95_ms=12')"),
                    lint=py("import sys; sys.exit(3)"),
                    mutate=py("print('mutation score: 70')") + " {changed_files}",
                    bench=py("pass"))
        r = self.snap("baseline", "--paths", "src", "--bench-runs", "3")
        self.assertEqual(r.returncode, 0, r.stderr)
        s = json.loads((self.root / ".review/evidence/baseline.json").read_text())
        self.assertEqual(s["tests"], {"passed": 4, "failed": 0})
        self.assertEqual(s["coverage"], 90.0)
        self.assertEqual(s["mutation"], 70.0)
        self.assertTrue(s["commands"]["mutate"]["cmd"].endswith(" src"))
        self.assertFalse(s["commands"]["lint"]["ok"])
        self.assertEqual(len(s["bench"]["runs"]), 3)
        self.assertEqual(s["metrics"], {"p95_ms": 12.0})
        self.assertEqual(s["size"], {"files": 1, "lines": 2})
        self.assertIn("build", s["skipped"])
        self.assertEqual((self.root / ".review/.gitignore").read_text(), "*\n")

    def test_mutate_without_paths_is_skipped(self):
        self.config(mutate="stryker run --mutate {changed_files}")
        self.snap("baseline", "--only", "mutate")
        s = json.loads((self.root / ".review/evidence/baseline.json").read_text())
        self.assertIn("mutate", s["skipped"])
        self.assertNotIn("mutate", s["commands"])

    def test_unknown_check_and_missing_config_are_usage_errors(self):
        self.assertEqual(self.snap("x").returncode, 2)
        self.config(test="true")
        self.assertEqual(self.snap("x", "--only", "deploy").returncode, 2)

    def test_identical_snapshots_pass(self):
        self.config(test=py("print('Tests  4 passed (4)')"), coverage=py("print('TOTAL 10 1 90%')"))
        self.snap("baseline")
        self.snap("after")
        r = self.compare()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("no regressions", r.stdout)
        self.assertIn("| line coverage % | 90 | 90 |", r.stdout)

    def test_regressions_fail(self):
        self.config(test=py("print('Tests  4 passed (4)')"), coverage=py("print('TOTAL 10 1 90%')"),
                    lint="true")
        self.snap("baseline")
        self.config(test=py("import sys; print('Tests  1 failed | 2 passed (3)'); sys.exit(1)"),
                    coverage=py("print('TOTAL 10 2 80%')"), lint="false")
        self.snap("after")
        r = self.compare("--json")
        self.assertEqual(r.returncode, 1)
        problems = " ".join(json.loads(r.stdout)["problems"])
        for needle in ["test:", "lint:", "failing tests", "passing tests", "line coverage"]:
            with self.subTest(needle=needle):
                self.assertIn(needle, problems)

    def test_fewer_tests_allowed_only_on_request(self):
        self.config(test=py("print('Tests  4 passed (4)')"))
        self.snap("baseline")
        self.config(test=py("print('Tests  3 passed (3)')"))
        self.snap("after")
        self.assertEqual(self.compare().returncode, 1)
        self.assertEqual(self.compare("--allow-fewer-tests").returncode, 0)

    def test_check_missing_after_is_a_regression(self):
        self.config(test="true", lint="true")
        self.snap("baseline")
        self.snap("after", "--only", "test")
        r = self.compare()
        self.assertEqual(r.returncode, 1)
        self.assertIn("not measured after", r.stdout)

    def test_coverage_tolerance(self):
        self.config(coverage=py("print('METRIC coverage=80')"))
        self.snap("baseline")
        self.config(coverage=py("print('METRIC coverage=79.7')"))
        self.snap("after")
        self.assertEqual(self.compare().returncode, 0)
        self.assertEqual(self.compare("--max-coverage-drop", "0.1").returncode, 1)

    def test_gated_metrics(self):
        self.config(test=py("print('METRIC p95_ms=100'); print('METRIC hits=10')"))
        self.snap("baseline")
        self.config(test=py("print('METRIC p95_ms=120'); print('METRIC hits=9')"))
        self.snap("after")
        self.assertEqual(self.compare().returncode, 0)  # ungated metrics are information
        self.assertEqual(self.compare("--lower-is-better", "p95_ms").returncode, 1)
        self.assertEqual(self.compare("--higher-is-better", "hits", "--max-metric-regression", "20").returncode, 0)
        self.assertEqual(self.compare("--higher-is-better", "hits").returncode, 1)

    def test_still_red_check_is_not_waved_through(self):
        self.config(lint="false")
        self.snap("baseline")
        self.snap("after")
        r = self.compare()
        self.assertEqual(r.returncode, 1)
        self.assertIn("failing", r.stdout)

    def test_command_over_the_timeout_is_recorded_as_failed(self):
        self.config(test=py("import time; time.sleep(5)"))
        self.snap("baseline", "--timeout", "1")
        s = json.loads((self.root / ".review/evidence/baseline.json").read_text())
        self.assertEqual(s["commands"]["test"]["exit"], 124)
        self.assertFalse(s["commands"]["test"]["ok"])

    def test_metric_cmd_feeds_gated_metrics(self):
        self.config(test="true")
        self.snap("baseline", "--metric-cmd", py("print('METRIC old_usages=12')"))
        self.snap("after", "--metric-cmd", py("print('METRIC old_usages=0')"))
        r = self.compare("--lower-is-better", "old_usages")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("| old_usages | 12 | 0 | -12 | improved |", r.stdout)
        self.assertEqual(self.snap("x", "--metric-cmd", py("print('no metric')")).returncode, 2)

    def test_md_output_and_bad_input(self):
        self.config(test="true")
        self.snap("baseline")
        self.snap("after")
        md = self.root / "out/evidence.md"
        self.assertEqual(self.compare("--md", str(md)).returncode, 0)
        self.assertIn("| Check | Before | After | Change | Result |", md.read_text())
        (self.root / ".review/evidence/after.json").write_text("{}")
        self.assertEqual(self.compare().returncode, 2)


if __name__ == "__main__":
    unittest.main()
