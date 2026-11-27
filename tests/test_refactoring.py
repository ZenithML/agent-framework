"""Guard the productionize and migrate skills, the refactoring standard and the executor modes."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/sdd"
STANDARD = PLUGIN / "standards/refactoring.md"


def skill(name):
    """The skill's text with whitespace collapsed, so wrapped lines still match."""
    return " ".join((PLUGIN / f"skills/{name}/SKILL.md").read_text().split())


class RefactoringStandardTests(unittest.TestCase):
    def setUp(self):
        self.std = STANDARD.read_text()

    def test_rules_labels_and_rubric(self):
        for needle in ["Safety net first", "Two hats, never at once", "Small, reversible steps",
                       "Tests are not proof of equivalence", "Mechanical before generative",
                       "Stop when the plan is wrong", "`[characterize]`", "`[tidy]`", "`[change]`",
                       "### Behaviour-preservation criteria", "| R1 |", "| R10 |",
                       "Expand and contract", "Strangler fig", "Branch by abstraction", "Parallel run"]:
            with self.subTest(needle=needle):
                self.assertIn(needle, self.std)

    def test_evidence_script_is_named_and_exists(self):
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/scripts/evidence.py", self.std)
        self.assertTrue((PLUGIN / "scripts/evidence.py").exists())


class SkillTests(unittest.TestCase):
    def test_usage_lines(self):
        self.assertIn("/sdd:productionize <area | --all> [--report-only] [--autonomous] [--profile standard|strict]",
                      skill("productionize"))
        self.assertIn("/sdd:migrate <from> <to> [--area <path>] [--report-only] [--autonomous]", skill("migrate"))

    def test_both_read_the_standard_and_reuse_roles(self):
        for name in ["productionize", "migrate"]:
            text = skill(name)
            with self.subTest(skill=name):
                self.assertIn("${CLAUDE_PLUGIN_ROOT}/standards/refactoring.md", text)
                self.assertIn("${CLAUDE_PLUGIN_ROOT}/agents/critic.md", text)
                self.assertIn("${CLAUDE_PLUGIN_ROOT}/agents/executor.md", text)
                self.assertIn("evidence.py snapshot --label baseline", text)
                self.assertIn("evidence.py compare", text)
                self.assertIn("mode: characterize", text)
                self.assertIn("mode: tidy", text)
                self.assertIn("Human gate", text)
                self.assertIn("If `--report-only`", text)
                self.assertIn("the critic cannot", text)
        for agent in ["refactorer.md", "migrator.md"]:
            self.assertFalse((PLUGIN / "agents" / agent).exists())

    def test_baseline_comes_before_any_change(self):
        p = skill("productionize")
        self.assertLess(p.index("## Step 2: Baseline evidence"), p.index("## Step 5: Build"))
        m = skill("migrate")
        self.assertLess(m.index("evidence.py snapshot --label baseline"), m.index("## Step 5: Pilot"))
        self.assertIn("A red baseline stops the migration", m)

    def test_productionize_wraps_ship_and_gates_on_evidence(self):
        p = skill("productionize")
        for needle in ["standards/ship-runbook.md", "productionize-<slug>", "## Readiness", "## Evidence",
                       "do not publish", "Never install a tool"]:
            with self.subTest(needle=needle):
                self.assertIn(needle, p)

    def test_migrate_safety(self):
        m = skill("migrate")
        for needle in ["METRIC old_usages", "git revert --no-edit", "Never start the next wave on a red tree",
                       "cannot be restored", "branching.featurePrefix", "Start clean.", "/sdd:create-pr",
                       "never prompt under `--autonomous`", "needs the user's approval"]:
            with self.subTest(needle=needle):
                self.assertIn(needle, m)

    def test_no_project_specifics(self):
        for name in ["productionize", "migrate"]:
            for word in ["supabase", "Supabase", "zenith-", "Mimir", "npm test"]:
                with self.subTest(skill=name, word=word):
                    self.assertNotIn(word, skill(name))

    def test_registered_as_strict_with_evals(self):
        cfg = json.loads((ROOT / "scripts/checks/harness-config.json").read_text())
        for name in ["productionize", "migrate"]:
            with self.subTest(skill=name):
                self.assertIn(name, cfg["strict_skills"])
                self.assertIn(name, cfg["evals_required"])
                evals = json.loads((PLUGIN / f"skills/{name}/evaluations/baseline-evals.json").read_text())
                self.assertEqual(len(evals["scenarios"]), 3)


class ExecutorModeTests(unittest.TestCase):
    def test_modes_and_handoff(self):
        ex = (PLUGIN / "agents/executor.md").read_text()
        for needle in ["| `characterize` |", "| `tidy` |", "### Characterize mode", "### Tidy mode",
                       "BEHAVIOUR_CHANGE", "they **must pass** on the unchanged code", "Never change product code"]:
            with self.subTest(needle=needle):
                self.assertIn(needle, ex)


class RoutingTests(unittest.TestCase):
    def test_docs_and_routing_name_both_skills(self):
        files = ["AGENTS.md", "docs/plugins.md", "plugins/sdd/templates/agent-routing.md",
                 "plugins/sdd/skills/sdd-init/SKILL.md", "plugins/sdd/standards/agent-pipeline.md",
                 "plugins/sdd/skills/lint-harness/SKILL.md"]
        for f in files:
            text = (ROOT / f).read_text()
            for name in ["productionize", "migrate"]:
                with self.subTest(file=f, skill=name):
                    self.assertIn(name, text)

    def test_schema_has_optional_evidence_commands(self):
        schema = json.loads((PLUGIN / "config/config.schema.json").read_text())
        props = schema["properties"]["commands"]["properties"]
        for key in ["typecheck", "coverage", "bench", "mutate"]:
            with self.subTest(key=key):
                self.assertIn(key, props)


if __name__ == "__main__":
    unittest.main()
