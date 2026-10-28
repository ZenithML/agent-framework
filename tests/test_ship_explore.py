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

    def test_architect_runs_explore_once_before_publish_and_only_when_on(self):
        architect = (PLUGIN / "agents/architect.md").read_text()
        self.assertIn("## Stage 4b: Explore (optional)", architect)
        self.assertIn("qa-engineer", architect)
        self.assertIn("EXPLORING", architect)
        stage = architect.split("## Stage 4b: Explore (optional)", 1)[1].split("\n## Stage 5", 1)[0]
        self.assertIn("Skip this stage", stage)
        self.assertIn("critic", stage)
        self.assertLess(architect.index("## Stage 4b"), architect.index("## Stage 5: Publish"))

    def test_pipeline_standard_documents_the_stage(self):
        pipeline = (PLUGIN / "standards/agent-pipeline.md").read_text()
        self.assertIn("Stage 4b — Explore", pipeline)
        self.assertIn("--explore", pipeline)


if __name__ == "__main__":
    unittest.main()
