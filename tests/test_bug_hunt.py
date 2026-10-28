"""Guard the bug-hunt skill: static audit + runtime pass, triage report, gate, fixes, one PR."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/sdd"
SKILL = PLUGIN / "skills/bug-hunt/SKILL.md"


class BugHuntTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text()

    def test_usage_and_flags(self):
        self.assertIn("/sdd:bug-hunt <area | --all> [--report-only] [--autonomous]", self.skill)

    def test_reuses_existing_roles_instead_of_new_ones(self):
        for role in ["agents/critic.md", "agents/qa-engineer.md"]:
            self.assertIn("${CLAUDE_PLUGIN_ROOT}/" + role, self.skill)
        self.assertFalse((PLUGIN / "agents/bug-hunter.md").exists())

    def test_critic_has_a_read_only_bugs_context(self):
        critic = (PLUGIN / "agents/critic.md").read_text()
        self.assertIn("### `bugs` — Static bug audit", critic)
        self.assertIn("requirements | design | code | bugs", critic)
        self.assertIn("tools: [Read, Grep, Glob]", critic)

    def test_qa_engineer_can_fix_a_given_list(self):
        qa = (PLUGIN / "agents/qa-engineer.md").read_text()
        self.assertIn("--fix-list", qa)

    def test_human_gate_report_and_publish(self):
        for needle in ["Human gate", ".review/bug-hunt/", "--autonomous", "/sdd:create-pr",
                       "P0", "P3", "Never stand up infrastructure"]:
            with self.subTest(needle=needle):
                self.assertIn(needle, self.skill)

    def test_no_zenith_specifics(self):
        for word in ["supabase", "Supabase", "build-status.md", "zenith-", "companion", "npm test"]:
            with self.subTest(word=word):
                self.assertNotIn(word, self.skill)

    def test_registered_as_strict_with_evals(self):
        cfg = json.loads((ROOT / "scripts/checks/harness-config.json").read_text())
        self.assertIn("bug-hunt", cfg["strict_skills"])
        self.assertIn("bug-hunt", cfg["evals_required"])
        evals = json.loads((PLUGIN / "skills/bug-hunt/evaluations/baseline-evals.json").read_text())
        self.assertEqual(len(evals["scenarios"]), 3)


if __name__ == "__main__":
    unittest.main()
