"""Guard the canonical role model catalog and dispatch instructions (no provider calls)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/sdd"
DEFAULTS = {
    "frontier": ("opus", "gpt-6-astra", "gemini-4-argon-high"),
    "workhorse": ("sonnet", "gpt-6.1-sol", "gemini-4-argon-medium"),
    "fast": ("haiku", "gpt-6-luna", "gemini-3.8-flash-high"),
}
ROLES = {
    "architect": "frontier", "planner": "workhorse", "executor": "fast",
    "critic": "workhorse", "tester": "fast", "archivist": "workhorse", "publisher": "workhorse",
}


class AgentTierTests(unittest.TestCase):
    def test_every_role_declares_complete_provider_defaults_and_legacy_model(self):
        self.assertEqual({p.stem for p in (PLUGIN / "agents").glob("*.md")}, set(ROLES))
        for role, tier in ROLES.items():
            with self.subTest(role=role):
                header = (PLUGIN / f"agents/{role}.md").read_text().split("---", 2)[1]
                self.assertRegex(header, rf"(?m)^tier: {tier}$")
                expected = dict(zip(("anthropic", "openai", "google"), DEFAULTS[tier]))
                block = re.search(r"(?m)^provider_defaults:\n((?:  [^\n]+\n)+)", header)
                self.assertIsNotNone(block)
                actual = dict(line.strip().split(": ", 1) for line in block[1].splitlines())
                self.assertEqual(actual, expected)
                self.assertRegex(header, rf"(?m)^model: {expected['anthropic']}$")

    def test_direct_dispatchers_resolve_models_and_preserve_fallback(self):
        dispatchers = ["ship", "architect", "spec", "plan", "tasks", "implement",
                       "critique", "qa", "publish", "audit"]
        for name in dispatchers:
            with self.subTest(skill=name):
                text = (PLUGIN / f"skills/{name}/SKILL.md").read_text()
                for required in ["provider_defaults", "active host provider", "inherit",
                                 "omit the Codex model override", "retry once", "scoped inputs"]:
                    self.assertIn(required, text)

    def test_nested_dispatchers_resolve_target_role_models(self):
        for role in ["architect", "planner", "publisher"]:
            with self.subTest(role=role):
                text = (PLUGIN / f"agents/{role}.md").read_text()
                for required in ["target role's `tier`", "provider_defaults", "openai",
                                 "omit the model override", "retry once", "no inherited conversation"]:
                    self.assertIn(required, text)
                self.assertNotIn("Inherit the session model and map", text)


if __name__ == "__main__":
    unittest.main()
