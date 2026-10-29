"""Guard the optional exploratory QA stage in /sdd:ship: off by default, opt in per run or per repo."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/sdd"


class ShipExploreTests(unittest.TestCase):
    def test_config_flag_exists_and_defaults_to_false(self):
        schema = json.loads((PLUGIN / "config/config.schema.json").read_text())
        explore = schema["properties"]["pipeline"]["properties"]["explore"]
        self.assertEqual(explore["type"], "boolean")
        self.assertIs(explore["default"], False)

    def test_ship_skill_offers_the_flag_and_passes_it_on(self):
        ship = (PLUGIN / "skills/ship/SKILL.md").read_text()
        self.assertIn("/sdd:ship <feature-description> [--autonomous] [--explore | --no-explore]", ship)
        self.assertIn("pipeline.explore", ship)
        self.assertIn("off by default", ship)

    def test_runbook_runs_explore_once_before_publish_and_only_when_on(self):
        runbook = (PLUGIN / "standards/ship-runbook.md").read_text()
        self.assertIn("## Stage 4b: Explore (optional)", runbook)
        self.assertIn("qa-engineer", runbook)
        self.assertIn("EXPLORING", runbook)
        stage = runbook.split("## Stage 4b: Explore (optional)", 1)[1].split("\n## Stage 5", 1)[0]
        self.assertIn("Skip this stage", stage)
        self.assertIn("critic", stage)
        self.assertLess(runbook.index("## Stage 4b"), runbook.index("## Stage 5: Publish"))

    def test_pipeline_standard_documents_the_stage(self):
        pipeline = (PLUGIN / "standards/agent-pipeline.md").read_text()
        self.assertIn("Stage 4b — Explore", pipeline)
        self.assertIn("--explore", pipeline)

    def test_state_machine_keeps_qa_failures_under_qa(self):
        runbook = (PLUGIN / "standards/ship-runbook.md").read_text()
        machine = runbook.split("## State Machine", 1)[1].split("## Context Engineering Rules", 1)[0]
        qa = machine.split("\nQA ", 1)[1].split("\n\n", 1)[0]
        self.assertIn("FAIL (cycle < 3)", qa)
        self.assertIn("FAIL (cycle == 3)", qa)
        exploring = machine.split("\nEXPLORING ", 1)[1].split("\n\n", 1)[0]
        self.assertNotIn("FAIL (cycle", exploring)

    def test_context_rules_cover_stage_4b(self):
        runbook = (PLUGIN / "standards/ship-runbook.md").read_text()
        rules = runbook.split("## Context Engineering Rules", 1)[1].split("\n## ", 1)[0]
        self.assertIn("| qa-engineer (Stage 4b) |", rules)
        self.assertIn("| critic (code, Stage 4b) |", rules)
        self.assertIn("| publisher |", rules)

    def test_rejected_bugs_lose_both_test_and_fix_commits(self):
        runbook = (PLUGIN / "standards/ship-runbook.md").read_text()
        stage = runbook.split("## Stage 4b: Explore (optional)", 1)[1].split("\n## Stage 5", 1)[0]
        self.assertIn("both its `test:` and `fix:` commits", stage)

    def test_harness_and_architect_skill_know_about_stage_4b(self):
        harness = (PLUGIN / "standards/harness.md").read_text()
        self.assertNotIn("`/sdd:ship` never routes QA to `qa-engineer`", harness)
        skill = (PLUGIN / "skills/architect/SKILL.md").read_text()
        self.assertIn("4b — Explore", skill)
        self.assertIn("--explore", skill)


if __name__ == "__main__":
    unittest.main()
