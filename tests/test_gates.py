"""Fixture tests for the mechanical gate scripts: gate-design.py and gate-review.py."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins/sdd/scripts"

DESIGN = """# Design

## Failure Modes & Degradation Matrix

| Category | Failure Condition | Expected System Behavior | Test Scenario |
|---|---|---|---|
| Transport/Network | upstream times out | retry twice then return 503 | Upload survives a timeout |
| Concurrency/State | two uploads race | one wins, no duplicate | Concurrent uploads store once |
| Boundary & Payloads | empty file | rejected with 400 | Empty upload is rejected |

## Test Scenarios

### BDD Scenarios

- **Scenario:** Upload survives a timeout
- **Scenario:** Concurrent uploads store once
- **Scenario:** Empty upload is rejected

## Edge Cases & Error Handling
"""

HIGH = {"file": "a.py", "line": 3, "side": "new", "severity": "high", "category": "correctness",
        "summary": "Retries a POST.", "failure_scenario": "Stored twice.",
        "reproduction": "test('no retry', ...) // fails: 2"}
LOW = {"file": "a.py", "line": 9, "side": "new", "severity": "low", "category": "maintainability",
       "summary": "Long function.", "failure_scenario": "Hard to read."}


def findings(items, verdict=None, mode="audit", head="h1", base="b0"):
    if verdict is None:
        verdict = "revise" if any(i["severity"] == "high" for i in items) else "pass"
    return {"version": 1, "head": head, "base": base, "pass_mode": mode, "verdict": verdict,
            "summary": "One change.", "findings": items}


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def run_script(self, name, *args):
        r = subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)],
                           capture_output=True, text=True, encoding="utf-8")
        return r.returncode, r.stdout + r.stderr

    def write(self, name, content):
        path = self.dir / name
        path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        return path


class GateDesignTests(Base):
    def design(self, text):
        return self.write("design.md", text)

    def test_complete_matrix_passes_strict(self):
        code, out = self.run_script("gate-design.py", self.design(DESIGN), "--profile", "strict")
        self.assertEqual(code, 0, out)

    def test_fast_profile_skips(self):
        code, out = self.run_script("gate-design.py", self.design("# empty"), "--profile", "fast")
        self.assertEqual(code, 0, out)
        self.assertIn("SKIP", out)

    def test_strict_requires_the_matrix_but_standard_does_not(self):
        text = DESIGN.split("## Failure Modes")[0] + "## Test Scenarios\n\n- **Scenario:** Upload works\n"
        code, out = self.run_script("gate-design.py", self.design(text), "--profile", "strict")
        self.assertEqual(code, 1)
        self.assertIn("missing '## Failure Modes & Degradation Matrix'", out)
        code, out = self.run_script("gate-design.py", self.design(text), "--profile", "standard")
        self.assertEqual(code, 0, out)

    def test_standard_needs_a_bdd_scenario(self):
        code, out = self.run_script("gate-design.py", self.design("## Test Scenarios\n\n- a unit test\n"))
        self.assertEqual(code, 1)
        self.assertIn("no BDD scenario", out)

    def test_template_placeholder_scenario_is_not_a_scenario(self):
        text = "## Test Scenarios\n\n- **Scenario:** Given ... When ... Then ...\n"
        code, _ = self.run_script("gate-design.py", self.design(text))
        self.assertEqual(code, 1)

    def test_missing_category_fails_strict(self):
        text = DESIGN.replace("| Concurrency/State | two uploads race | one wins, no duplicate | Concurrent uploads store once |\n", "")
        code, out = self.run_script("gate-design.py", self.design(text), "--profile", "strict")
        self.assertEqual(code, 1)
        self.assertIn("concurrency/state", out)
        code, out = self.run_script("gate-design.py", self.design(text), "--profile", "standard")
        self.assertEqual(code, 0, out)

    def test_placeholder_cell_fails_even_in_standard(self):
        text = DESIGN.replace("retry twice then return 503", "<expected degradation/retry behavior>")
        code, out = self.run_script("gate-design.py", self.design(text))
        self.assertEqual(code, 1)
        self.assertIn("placeholder", out)

    def test_unmapped_test_scenario_fails(self):
        text = DESIGN.replace("| Empty upload is rejected |", "| Something nobody tests |")
        code, out = self.run_script("gate-design.py", self.design(text))
        self.assertEqual(code, 1)
        self.assertIn("does not match any scenario", out)

    def test_scenario_cell_may_contain_the_scenario_text(self):
        text = DESIGN.replace("| Empty upload is rejected |", "| BDD: Empty upload is rejected (400) |")
        code, out = self.run_script("gate-design.py", self.design(text), "--profile", "strict")
        self.assertEqual(code, 0, out)

    def test_hash_comment_in_code_fence_does_not_end_a_section(self):
        text = DESIGN.replace("- **Scenario:** Empty upload is rejected",
                              "```bash\n# not a heading\n```\n\n- **Scenario:** Empty upload is rejected")
        code, out = self.run_script("gate-design.py", self.design(text), "--profile", "strict")
        self.assertEqual(code, 0, out)

    def test_wrong_columns_and_short_rows_fail(self):
        code, out = self.run_script("gate-design.py", self.design(DESIGN.replace("| Category |", "| Kind |")))
        self.assertEqual(code, 1)
        self.assertIn("columns", out)

    def test_json_output_and_unreadable_file(self):
        code, out = self.run_script("gate-design.py", self.design(DESIGN), "--json")
        self.assertEqual(json.loads(out)["ok"], True)
        code, _ = self.run_script("gate-design.py", self.dir / "nope.md")
        self.assertEqual(code, 2)

    def test_template_design_fails_until_filled(self):
        template = ROOT / "plugins/sdd/templates/docs/design.md"
        code, _ = self.run_script("gate-design.py", template, "--profile", "strict")
        self.assertEqual(code, 1)


class GateReviewTests(Base):
    def gate(self, doc, *args):
        return self.run_script("gate-review.py", self.write("findings.json", doc), *args)

    def test_clean_and_proven_findings_pass(self):
        self.assertEqual(self.gate(findings([LOW]))[0], 0)
        self.assertEqual(self.gate(findings([HIGH, LOW]))[0], 0)

    def test_high_without_reproduction_fails(self):
        for repro in (None, "", "   ", "<failing test>", "short"):
            high = dict(HIGH)
            if repro is None:
                del high["reproduction"]
            else:
                high["reproduction"] = repro
            code, out = self.gate(findings([high]))
            self.assertEqual(code, 1, repro)
            self.assertIn("no proof of bug", out)

    def test_medium_needs_no_reproduction(self):
        medium = dict(LOW, severity="medium")
        self.assertEqual(self.gate(findings([medium]))[0], 0)

    def test_verdict_must_follow_findings(self):
        code, out = self.gate(findings([HIGH], verdict="pass"))
        self.assertEqual(code, 1)
        self.assertIn("contradicts", out)
        code, _ = self.gate(findings([LOW], verdict="revise"))
        self.assertEqual(code, 1)

    def test_shape_errors(self):
        bad = dict(LOW, line=0, category="style", side="middle")
        code, out = self.gate(findings([bad]))
        self.assertEqual(code, 1)
        for text in ("'line'", "'category'", "'side'"):
            self.assertIn(text, out)
        doc = findings([LOW])
        doc["version"] = 2
        self.assertEqual(self.gate(doc)[0], 1)

    def test_more_than_fifteen_findings_fail(self):
        self.assertEqual(self.gate(findings([LOW] * 16))[0], 1)
        self.assertEqual(self.gate(findings([LOW] * 15))[0], 0)

    def test_verification_lists_only_highs(self):
        code, out = self.gate(findings([HIGH, LOW], mode="verification", head="h2"))
        self.assertEqual(code, 1)
        self.assertIn("verification pass lists only", out)
        self.assertEqual(self.gate(findings([HIGH], mode="verification", head="h2"))[0], 0)

    def test_two_pass_chain(self):
        first = self.write("pass1.json", findings([HIGH]))
        second = findings([], mode="verification", head="h2")
        self.assertEqual(self.gate(second, "--previous", first, "--final")[0], 0)
        code, out = self.gate(findings([], mode="verification", head="h1"), "--previous", first)
        self.assertEqual((code, "head equals" in out), (1, True))
        code, out = self.gate(findings([], mode="audit", head="h2"), "--previous", first)
        self.assertIn("must have pass_mode 'verification'", out)
        code, out = self.gate(findings([], mode="verification", head="h2", base="other"), "--previous", first)
        self.assertIn("base differs", out)
        third = self.write("pass2.json", findings([], mode="verification", head="h2"))
        code, out = self.gate(findings([], mode="verification", head="h3"), "--previous", third)
        self.assertIn("at most two passes", out)

    def test_final_requires_pass(self):
        code, out = self.gate(findings([HIGH], mode="verification", head="h2"), "--final")
        self.assertEqual(code, 1)
        self.assertIn("final verdict", out)

    def test_unreadable_or_invalid_json_is_a_usage_error(self):
        self.assertEqual(self.run_script("gate-review.py", self.dir / "none.json")[0], 2)
        self.assertEqual(self.run_script("gate-review.py", self.write("bad.json", "{oops"))[0], 2)


if __name__ == "__main__":
    unittest.main()
