"""Guard the exploratory QA stage in /sdd:ship (on by default, --no-explore to opt out) and the upstream failure matrix."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/sdd"


class ShipExploreTests(unittest.TestCase):
    def test_config_flag_exists_and_defaults_to_true(self):
        schema = json.loads((PLUGIN / "config/config.schema.json").read_text())
        explore = schema["properties"]["pipeline"]["properties"]["explore"]
        self.assertEqual(explore["type"], "boolean")
        self.assertIs(explore["default"], True)
        self.assertIn("On by default", explore["description"])
        self.assertIn("--no-explore", explore["description"])

    def test_ship_skill_offers_the_flag_and_defaults_to_on(self):
        ship = (PLUGIN / "skills/ship/SKILL.md").read_text()
        self.assertIn("/sdd:ship <feature-description> [--autonomous] [--explore | --no-explore]", ship)
        self.assertIn("pipeline.explore", ship)
        self.assertIn("on by default", ship)
        self.assertIn("--no-explore", ship)

    def test_failure_modes_and_degradation_matrix_in_doc_structure_planner_and_critic(self):
        doc_structure = (PLUGIN / "standards/doc-structure.md").read_text()
        self.assertIn("Failure Modes & Degradation Matrix", doc_structure)
        for category in ["Transport/Network", "Concurrency/State", "Boundary & Payloads"]:
            self.assertIn(category, doc_structure)
        for field in ["Failure Condition", "Expected System Behavior", "Test Scenario"]:
            self.assertIn(field, doc_structure)

        planner = (PLUGIN / "agents/planner.md").read_text()
        self.assertIn("Failure Modes & Degradation Matrix", planner)

        critic = (PLUGIN / "agents/critic.md").read_text()
        design_section = critic.split("### `design`", 1)[1].split("### `code`", 1)[0]
        self.assertIn("Failure Modes & Degradation Matrix", design_section)
        self.assertIn("BDD", design_section)

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
