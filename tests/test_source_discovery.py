"""Check Claude discovery in the source checkout without an installed marketplace."""
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SourceDiscoveryTests(unittest.TestCase):
    def probe_claude_startup(self, cwd, launcher=None):
        with tempfile.TemporaryDirectory(prefix="claude-source-startup-") as scratch:
            env = {"PATH": os.environ["PATH"], "HOME": scratch,
                   "CLAUDE_CONFIG_DIR": str(Path(scratch) / "config"),
                   "TMPDIR": scratch}
            result = subprocess.run(
                (launcher or [shutil.which("claude")]) +
                ["-p", "--verbose", "--output-format", "stream-json", "--max-turns", "0",
                 "--no-session-persistence", "--setting-sources", "project", "--strict-mcp-config",
                 "--mcp-config", '{"mcpServers":{}}', "--tools", "", "--", "Reply OK"],
                cwd=cwd, env=env, capture_output=True, text=True, timeout=30, check=False,
            )
        messages = []
        for line in result.stdout.splitlines():
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        startup = next((item for item in messages if item.get("subtype") == "init"), None)
        self.assertIsNotNone(startup, result.stdout + result.stderr)
        return startup

    def test_gates_count_symlink_aliases_once_and_keep_distinct_files(self):
        spec = importlib.util.spec_from_file_location("framework_gate_common", ROOT / "scripts/checks/_common.py")
        common = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(common)
        with tempfile.TemporaryDirectory(prefix="gate-aliases-") as scratch:
            root = Path(scratch)
            for name in ("first", "second"):
                path = root / "plugins/sdd/skills" / name / "SKILL.md"
                path.parent.mkdir(parents=True)
                path.write_text("same content; different physical files")
            (root / ".claude").mkdir()
            (root / ".claude/skills").symlink_to("../plugins/sdd/skills", target_is_directory=True)
            files = common._glob_all(root, [".claude/skills/**/SKILL.md", "plugins/*/skills/**/SKILL.md"])
            self.assertEqual(len(files), 2)
            self.assertEqual(len({path.resolve() for path in files}), 2)

    def test_claude_and_codex_share_canonical_source_files(self):
        for discovery in (".claude/skills", ".agents/skills"):
            self.assertEqual((ROOT / discovery).resolve(), ROOT / "plugins/sdd/skills")
            self.assertTrue((ROOT / discovery / "ship/SKILL.md").is_file())
        self.assertEqual((ROOT / ".claude/agents").resolve(), ROOT / "plugins/sdd/agents")
        settings = json.loads((ROOT / ".claude/settings.json").read_text())
        self.assertFalse(settings.get("enabledPlugins", {}).get("sdd@sdd-harness", False))

    @unittest.skipUnless(shutil.which("claude"), "Claude CLI is required for the real startup probe")
    def test_claude_startup_discovers_current_skills_and_roles_without_plugin_cache(self):
        # No user credentials, installed plugins, MCP servers, or model tools.
        # Startup metadata precedes the expected unauthenticated model result.
        startup = self.probe_claude_startup(ROOT)
        expected_skills = {path.parent.name for path in (ROOT / "plugins/sdd/skills").glob("*/SKILL.md")}
        self.assertTrue(expected_skills <= set(startup["skills"]),
                        f"Missing source skills: {sorted(expected_skills - set(startup['skills']))}")
        expected_roles = {path.stem for path in (ROOT / "plugins/sdd/agents").glob("*.md")}
        self.assertTrue(expected_roles <= set(startup["agents"]),
                        f"Missing source roles: {sorted(expected_roles - set(startup['agents']))}")
        self.assertFalse(any(plugin.get("name") == "sdd" for plugin in startup.get("plugins", [])),
                         "Source discovery must not depend on a cached SDD plugin")
        self.assertEqual(startup["mcp_servers"], [])
        self.assertEqual(startup["tools"], [])

    @unittest.skipUnless(shutil.which("claude"), "Claude CLI is required for the real startup probe")
    def test_existing_live_plugin_launcher_still_exposes_namespaced_skills_and_roles(self):
        with tempfile.TemporaryDirectory(prefix="claude-plugin-consumer-") as target:
            startup = self.probe_claude_startup(target, ["bash", str(ROOT / "scripts/dev.sh")])
        self.assertIn("sdd:ship", startup["skills"])
        self.assertIn("sdd:review-diff", startup["skills"])
        self.assertIn("sdd:triage-pr", startup["skills"])
        self.assertIn("sdd:planner", startup["agents"])
        plugin = next(item for item in startup["plugins"] if item.get("name") == "sdd")
        self.assertEqual(Path(plugin["path"]).resolve(), ROOT / "plugins/sdd")


if __name__ == "__main__":
    unittest.main()
