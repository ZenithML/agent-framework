"""Guard who coordinates /sdd:ship: inline by default, the architect subagent on request."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/sdd"


def read(rel):
    return (PLUGIN / rel).read_text()


class ShipOrchestrationTests(unittest.TestCase):
    def test_config_defaults_to_inline(self):
        schema = json.loads(read("config/config.schema.json"))
        orchestrator = schema["properties"]["pipeline"]["properties"]["orchestrator"]
        self.assertEqual(orchestrator["type"], "string")
        self.assertEqual(orchestrator["enum"], ["inline", "architect"])
        self.assertEqual(orchestrator["default"], "inline")

    def test_ship_skill_offers_both_modes(self):
        ship = read("skills/ship/SKILL.md")
        self.assertIn("[--inline | --architect]", ship)
        self.assertIn("pipeline.orchestrator", ship)
        self.assertIn("inline by default", ship)
        self.assertIn("standards/ship-runbook.md", ship)
        self.assertIn("in full", ship)
        self.assertIn("writes no product code", ship)
        self.assertIn("AWAITING_SPEC_APPROVAL", ship)
        self.assertIn("run_in_background", ship)
        self.assertIn('isolation: "worktree"', ship)
        self.assertIn("--resume <domain>", ship)
        self.assertIn("If both `--inline` and\n`--architect` are given, stop and ask", ship)
        self.assertIn("**without**\n  `isolation: \"worktree\"`", ship)
        self.assertIn("--foreground", ship)
        self.assertIn("git worktree remove", ship)
        self.assertIn("Never remove it yourself", ship)

    def test_runbook_holds_the_whole_procedure(self):
        runbook = read("standards/ship-runbook.md")
        for heading in ["## Stage 1: Spec", "## Stage 2: Plan", "## Stage 3: Implement",
                        "## Code Critique", "## Stage 4: QA", "## Stage 4b: Explore (optional)",
                        "## Stage 5: Publish", "## State Machine", "## Context Engineering Rules",
                        "## Resume", "## Spec gate"]:
            self.assertIn(heading, runbook)
        resume = runbook.split("## Resume", 1)[1].split("\n## ", 1)[0]
        self.assertIn("first matching row", resume)
        self.assertIn("Cycle counts restart at zero", resume)
        rows = re.findall(r"(?m)^\| (R\d+b?) \|", resume)
        self.assertEqual(rows, ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R7b", "R8"])
        self.assertIn("- `workhorse`: architect", runbook)
        gate = runbook.split("## Spec gate", 1)[1].split("\n## ", 1)[0]
        self.assertIn("Inline", gate)
        self.assertIn("Architect", gate)

    def test_architect_follows_the_runbook_in_its_own_worktree(self):
        text = read("agents/architect.md")
        header = text.split("---", 2)[1]
        self.assertRegex(header, r"(?m)^tier: workhorse$")
        self.assertRegex(header, r"(?m)^model: sonnet$")
        for required in ["standards/ship-runbook.md", "--resume", "--worktree", "worktree_path",
                         "AWAITING_SPEC_APPROVAL", "git worktree add", "--approved",
                         "info/exclude", "permission denied"]:
            self.assertIn(required, text)
        escalation = text.split("## Final and escalation handoffs", 1)[1]
        self.assertIn('"worktree_path"', escalation)
        self.assertIn('"branch"', escalation)
        self.assertIn("ESCALATION", escalation)
        # The procedure lives in the runbook only, so the two modes cannot drift.
        self.assertNotIn("## State Machine", text)

    def test_tier_table_lists_the_architect_as_workhorse(self):
        pipeline = read("standards/agent-pipeline.md")
        self.assertRegex(pipeline, r"(?m)^\| workhorse \| architect,")
        self.assertNotRegex(pipeline, r"(?m)^\| frontier \| architect")

    def test_flat_install_points_at_the_installed_runbook(self):
        with tempfile.TemporaryDirectory(prefix="ship orchestration ") as tmp:
            target = Path(tmp) / "consumer"
            target.mkdir()
            binary = Path(tmp) / "bin"
            binary.mkdir()
            (binary / "python3").symlink_to(sys.executable)
            env = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ["PATH"])
            result = subprocess.run(["bash", str(ROOT / "scripts/install-skills.sh"),
                                     "--harness", "claude,codex", str(target)],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((target / ".claude/standards/ship-runbook.md").is_file())
            for rel in [".claude/skills/ship/SKILL.md", ".claude/agents/architect.md"]:
                text = (target / rel).read_text()
                self.assertIn(".claude/standards/ship-runbook.md", text, rel)
                self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", text, rel)


if __name__ == "__main__":
    unittest.main()
