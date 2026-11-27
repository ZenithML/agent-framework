"""Guard how /sdd:ship runs: inline only, scaled by risk profile, backed by mechanical gate scripts."""
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
REMOVED = ["--architect", "--foreground", "--resume", "--inline", "AWAITING_SPEC_APPROVAL",
           "pipeline.orchestrator", ".claude/worktrees", "git worktree", "run_in_background"]


def read(rel):
    return (PLUGIN / rel).read_text()


def flat(text):
    """Collapse whitespace so prose assertions survive re-wrapping."""
    return " ".join(text.split())


class ShipOrchestrationTests(unittest.TestCase):
    def test_architect_mode_is_gone(self):
        self.assertFalse((PLUGIN / "agents/architect.md").exists())
        self.assertFalse((PLUGIN / "skills/architect").exists())
        for rel in ["skills/ship/SKILL.md", "standards/ship-runbook.md", "config/config.schema.json"]:
            text = read(rel)
            for gone in REMOVED:
                self.assertNotIn(gone, text, f"{rel} still mentions {gone}")
        self.assertNotRegex(read("standards/ship-runbook.md"), r"(?m)^\| R\d+b? \|")
        self.assertNotIn("## Resume", read("standards/ship-runbook.md"))
        schema = json.loads(read("config/config.schema.json"))
        self.assertNotIn("orchestrator", schema["properties"]["pipeline"]["properties"])

    def test_config_offers_profiles_defaulting_to_standard(self):
        schema = json.loads(read("config/config.schema.json"))
        profile = schema["properties"]["pipeline"]["properties"]["profile"]
        self.assertEqual(profile["type"], "string")
        self.assertEqual(profile["enum"], ["fast", "standard", "strict"])
        self.assertEqual(profile["default"], "standard")

    def test_ship_skill_resolves_profile_and_runs_inline(self):
        ship = read("skills/ship/SKILL.md")
        self.assertIn("[--profile fast|standard|strict]", ship)
        self.assertIn("pipeline.profile", ship)
        self.assertIn("standards/ship-runbook.md", ship)
        self.assertIn("in full", ship)
        self.assertIn("writes no product code", ship)
        self.assertIn("scripts/gate-design.py", ship)
        self.assertIn("scripts/gate-review.py", ship)
        for profile in ["`fast`", "`standard`", "`strict`"]:
            self.assertIn(profile, ship)

    def test_planning_and_publishing_are_done_by_the_session(self):
        ship = flat(read("skills/ship/SKILL.md"))
        self.assertIn("Do the planning stages (spec, plan, tasks) and publishing yourself", ship)
        self.assertIn("agents/planner.md", ship)
        self.assertIn("agents/publisher.md", ship)
        runbook = read("standards/ship-runbook.md")
        for heading, role in [("## Stage 1: Spec", "planner.md"), ("## Stage 2: Plan", "planner.md"),
                              ("## Stage 5: Publish", "publisher.md")]:
            stage = runbook.split(heading, 1)[1].split("\n## ", 1)[0]
            self.assertIn(f"${{CLAUDE_PLUGIN_ROOT}}/agents/{role}", stage, heading)
            self.assertIn("yourself", stage, heading)
        gate = runbook.split("## Spec gate", 1)[1]
        self.assertIn("revise requirements.md yourself", gate)
        # Independence stays where it matters: these are always separate agents.
        self.assertIn("critic, tester, qa-engineer) and the per-task executor are always separate agents",
                      flat(runbook))

    def test_runbook_holds_the_whole_procedure(self):
        runbook = read("standards/ship-runbook.md")
        for heading in ["## Profiles", "## Stage 1: Spec", "## Stage 2: Plan", "### Design Gate",
                        "## Stage 3: Implement", "## Code Critique", "## Stage 4: QA",
                        "## Stage 4b: Explore (optional)", "## Stage 4c: Review", "## Stage 5: Publish",
                        "## State Machine", "## Context Engineering Rules", "## Spec gate"]:
            self.assertIn(heading, runbook)
        self.assertLess(runbook.index("## Stage 4b"), runbook.index("## Stage 4c"))
        self.assertLess(runbook.index("## Stage 4c"), runbook.index("## Stage 5: Publish"))
        self.assertIn("- `workhorse`: planner, critic", runbook)

    def test_profile_table_scales_the_pipeline(self):
        runbook = read("standards/ship-runbook.md")
        table = runbook.split("## Profiles", 1)[1].split("\n---", 1)[0]
        rows = {}
        for line in table.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if line.startswith("|") and len(cells) == 4 and cells[0] not in ("Stage", "---"):
                rows[cells[0]] = cells[1:]
        self.assertEqual(rows["1 Spec + critic"][0], "-")
        self.assertEqual(rows["Design Gate"][0], "-")
        self.assertIn("full Failure Modes", rows["2 Plan + critic"][2])
        self.assertIn("Prosecutor", rows["3 Implement"][2])
        self.assertNotIn("Prosecutor", rows["3 Implement"][1])
        self.assertEqual(rows["Mutation Gate"][0], "-")
        self.assertTrue(rows["Mutation Gate"][2].startswith("yes"))
        self.assertTrue(rows["4b Explore"][1].startswith("yes"))
        self.assertTrue(rows["4b Explore"][2].startswith("yes"))
        for stage in ("4c Review", "5 Publish + CI"):
            self.assertEqual([c.split(",")[0] for c in rows[stage]], ["yes"] * 3)

    def test_runbook_wires_the_gate_scripts(self):
        runbook = read("standards/ship-runbook.md")
        self.assertIn("scripts/gate-design.py docs/specs/<domain>/design.md --profile <profile>", runbook)
        review = runbook.split("## Stage 4c: Review", 1)[1].split("\n## ", 1)[0]
        self.assertIn("scripts/gate-review.py .review/findings.json", review)
        self.assertIn("--previous .review/pass1.json --final", review)
        self.assertIn("no third pass", review)
        machine = runbook.split("## State Machine", 1)[1]
        for state in ["DESIGN_GATE", "REVIEWING"]:
            self.assertIn(state, machine)

    def test_gate_scripts_ship_and_are_executable(self):
        for name in ["gate-design.py", "gate-review.py"]:
            path = PLUGIN / "scripts" / name
            self.assertTrue(path.is_file(), name)
            self.assertTrue(os.access(path, os.X_OK), name)

    def test_tier_table_lists_no_architect(self):
        pipeline = read("standards/agent-pipeline.md")
        self.assertRegex(pipeline, r"(?m)^\| workhorse \| planner,")
        self.assertNotRegex(pipeline, r"(?m)^\| frontier \| architect")

    def test_flat_install_points_at_the_installed_runbook_and_gates(self):
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
            for name in ["gate-design.py", "gate-review.py"]:
                self.assertTrue(os.access(target / ".claude/scripts" / name, os.X_OK), name)
            self.assertFalse((target / ".claude/agents/architect.md").exists())
            for rel in [".claude/skills/sdd-ship/SKILL.md", ".claude/standards/ship-runbook.md"]:
                text = (target / rel).read_text()
                self.assertIn(".claude/scripts/gate-design.py", text, rel)
                self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", text, rel)
            ship = (target / ".claude/skills/sdd-ship/SKILL.md").read_text()
            self.assertIn(".claude/standards/ship-runbook.md", ship)


if __name__ == "__main__":
    unittest.main()
