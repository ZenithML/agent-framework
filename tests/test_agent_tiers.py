"""Guard the shared model catalog and role/dispatcher integration (no provider calls)."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/sdd"
PROVIDERS = {"anthropic", "openai", "google"}
ROLES = {
    "architect": "workhorse", "planner": "workhorse", "executor": "fast",
    "critic": "workhorse", "tester": "fast", "archivist": "workhorse", "publisher": "workhorse",
    "qa-engineer": "workhorse",
}


class AgentTierTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((PLUGIN / "config/model-tiers.json").read_text())

    def test_catalog_defines_every_tier_and_provider(self):
        # frontier stays in the catalog with no shipped role, so a consumer can move a role
        # (for example the architect) back up by editing its tier.
        self.assertEqual(set(self.catalog), set(ROLES.values()) | {"frontier"})
        for tier, defaults in self.catalog.items():
            with self.subTest(tier=tier):
                self.assertEqual(set(defaults), PROVIDERS)
                for model in defaults.values():
                    self.assertIsInstance(model, str)
                    self.assertTrue(model.strip())
                    self.assertEqual(model, model.strip())
                    self.assertNotEqual(model, "inherit")

    def test_role_tiers_and_legacy_models_match_catalog_with_optional_overrides(self):
        self.assertEqual({p.stem for p in (PLUGIN / "agents").glob("*.md")}, set(ROLES))
        for role, tier in ROLES.items():
            with self.subTest(role=role):
                header = (PLUGIN / f"agents/{role}.md").read_text().split("---", 2)[1]
                self.assertRegex(header, rf"(?m)^tier: {tier}$")
                overrides = {}
                block = re.search(r"(?m)^provider_defaults:\n((?:[ \t]+[^\n]*\n|\n)+)", header)
                if "provider_defaults:" in header:
                    self.assertIsNotNone(block, "Overrides must be a nested provider mapping")
                    for line in block[1].splitlines():
                        entry = line.split("#", 1)[0].strip()
                        if not entry:
                            continue
                        key, separator, value = entry.partition(":")
                        self.assertEqual(separator, ":", f"Invalid override: {line}")
                        self.assertIn(key, PROVIDERS)
                        self.assertNotIn(key, overrides)
                        self.assertTrue(value.strip())
                        overrides[key] = value.strip()
                        self.assertNotEqual(overrides[key], self.catalog[tier][key],
                                            "Omit redundant overrides; edit the shared catalog")
                expected = overrides.get("anthropic", self.catalog[tier]["anthropic"])
                legacy = re.search(r"(?m)^model: (\S+)$", header)
                self.assertIsNotNone(legacy)
                self.assertEqual(legacy[1], expected)

    def test_direct_dispatchers_resolve_models_and_preserve_fallback(self):
        dispatchers = ["ship", "architect", "spec", "plan", "tasks", "implement",
                       "critique", "qa", "qa-explore", "publish", "audit"]
        for name in dispatchers:
            with self.subTest(skill=name):
                text = (PLUGIN / f"skills/{name}/SKILL.md").read_text()
                for required in ["config/model-tiers.json", "optional `provider_defaults.<provider>`",
                                 "otherwise use the catalog", "active host provider", "inherit",
                                 "omit the Codex model override", "retry once", "scoped inputs"]:
                    self.assertIn(required, text)

    def test_nested_dispatchers_resolve_target_role_models(self):
        for role in ["architect", "planner", "publisher"]:
            with self.subTest(role=role):
                text = (PLUGIN / f"agents/{role}.md").read_text()
                for required in ["target role's `tier`", "config/model-tiers.json",
                                 "optional", "provider_defaults", "otherwise use the catalog",
                                 "openai", "omit the model override", "retry once",
                                 "no inherited conversation"]:
                    self.assertIn(required, text)
                self.assertNotIn("Inherit the session model and map", text)

    def test_qa_engineer_is_an_author_with_browser_and_fix_tools(self):
        header, body = (PLUGIN / "agents/qa-engineer.md").read_text().split("---", 2)[1:]
        self.assertRegex(header, r"(?m)^role: author$")
        tools = re.search(r"(?m)^tools: \[(.*)\]$", header)
        self.assertIsNotNone(tools)
        declared = {t.strip() for t in tools[1].split(",")}
        for tool in ["Read", "Grep", "Glob", "Edit", "Write", "Bash",
                     "mcp__playwright__browser_navigate", "mcp__playwright__browser_console_messages",
                     "mcp__playwright__browser_network_requests", "mcp__playwright__browser_resize"]:
            self.assertIn(tool, declared)
        self.assertNotIn("Agent", declared)
        for required in ["devServer.url", "http://localhost:3000", "<DEV_HOST_CMD>",
                         "run_in_background", "<TEST_CMD>", "--report-only", "git stash",
                         "reproduce", "credentialEnv", "BUGS FOUND & FIXED", "FRICTION NOTED",
                         "NOT FIXED", "CLEAN"]:
            self.assertIn(required, body)
        for leaked in ["supabase", "e2e/companion", "testpassword", "@zenithml.com"]:
            self.assertNotIn(leaked, body.lower())

    def test_qa_and_qa_explore_name_each_other_as_boundaries(self):
        explore = (PLUGIN / "skills/qa-explore/SKILL.md").read_text()
        header = explore.split("---", 2)[1]
        self.assertIn("Does not trigger", header)
        self.assertIn("/sdd:qa ", header)
        self.assertIn("agents/qa-engineer.md", explore)
        self.assertIn("/sdd:qa-explore <feature-or-flow> [--report-only]", explore)
        self.assertIn("in full", explore)
        qa_header = (PLUGIN / "skills/qa/SKILL.md").read_text().split("---", 2)[1]
        self.assertIn("/sdd:qa-explore", qa_header)


if __name__ == "__main__":
    unittest.main()
