"""Exercise canonical MCP sync through its public, installed CLI."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import tomllib

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/sync_mcp.py"


class MCPSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="shared mcp ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / ".mcp.json"
        self.config = self.root / ".codex/config.toml"

    def source_servers(self, servers):
        self.source.write_text(json.dumps({"mcpServers": servers}))

    def run_sync(self, *flags, success=True):
        result = subprocess.run([sys.executable, str(SCRIPT), "--target", str(self.root), *flags],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def test_preserves_manual_settings_and_updates_only_managed_servers(self):
        self.config.parent.mkdir()
        manual = '# personal settings\nmodel = "example"\n[mcp_servers.manual]\nurl = "https://manual.test/mcp"\n'
        self.config.write_text(manual)
        self.source_servers({"atlassian": {"type": "http", "url": "https://mcp.atlassian.com/v1/mcp"}})
        before = self.source.read_bytes()
        self.run_sync("--check", success=False)
        self.assertEqual(self.config.read_text(), manual)
        self.run_sync()
        first = self.config.read_bytes()
        self.run_sync()
        self.assertEqual(first, self.config.read_bytes())
        self.run_sync("--check")
        data = tomllib.loads(self.config.read_text())
        self.assertEqual(data["model"], "example")
        self.assertIn("manual", data["mcp_servers"])
        self.assertIn("atlassian", data["mcp_servers"])
        self.source_servers({"gitlab": {"url": "https://gitlab.com/api/v4/mcp"}})
        self.run_sync()
        data = tomllib.loads(self.config.read_text())
        self.assertEqual(set(data["mcp_servers"]), {"manual", "gitlab"})
        self.source.unlink()
        self.run_sync("--check", success=False)
        self.run_sync()
        self.assertEqual(self.config.read_text(), manual)
        self.assertNotEqual(before, b"")

    def test_environment_references_are_translated_without_reading_secrets(self):
        self.source_servers({
            'http.with"quotes': {"url": "https://example.test/mcp", "headers": {
                "Authorization": "Bearer ${MCP_TOKEN}", "X-Key": "${API_KEY}", "X-Static": "hello"}},
            "stdio": {"command": "node", "args": ["server.mjs"],
                      "env": {"TOKEN": "${TOKEN}", "STATIC": "value"}},
        })
        self.run_sync()
        servers = tomllib.loads(self.config.read_text())["mcp_servers"]
        self.assertEqual(servers['http.with"quotes']["bearer_token_env_var"], "MCP_TOKEN")
        self.assertEqual(servers['http.with"quotes']["env_http_headers"], {"X-Key": "API_KEY"})
        self.assertEqual(servers["stdio"]["env_vars"], ["TOKEN"])
        self.assertEqual(servers["stdio"]["env"], {"STATIC": "value"})
        self.assertEqual(servers["stdio"]["args"], ["server.mjs"])

    def test_manual_name_collision_fails_without_writing(self):
        self.config.parent.mkdir()
        manual = '[mcp_servers."same.name"]\nurl = "https://manual.test"\n'
        self.config.write_text(manual)
        self.source_servers({"same.name": {"url": "https://incoming.test"}})
        self.run_sync(success=False)
        self.assertEqual(self.config.read_text(), manual)

    def test_invalid_input_keeps_previous_output(self):
        self.source_servers({"good": {"url": "https://good.test"}})
        self.run_sync()
        before = self.config.read_bytes()
        bad_servers = [
            {"bad": {}},
            {"bad": {"url": "https://a.test", "serverUrl": "https://b.test"}},
            {"bad": {"command": "node", "args": "not-a-list"}},
            {"bad": {"command": "node", "env": {"N": ["list"]}}},
            {"bad": "not an object"},
        ]
        for servers in bad_servers:
            with self.subTest(servers=servers):
                self.source_servers(servers)
                self.run_sync(success=False)
                self.assertEqual(self.config.read_bytes(), before)
        self.source.write_text("{broken")
        self.run_sync(success=False)
        self.assertEqual(self.config.read_bytes(), before)

    def test_servers_codex_cannot_express_are_skipped_with_a_warning(self):
        unsupported = [
            {"type": "sse", "url": "https://example.test/sse"},
            {"url": "https://example.test", "headersHelper": "echo secret"},
            {"command": "node", "env": {"TOKEN": "${OTHER_TOKEN}"}},
            {"url": "https://${HOST}/mcp"},
            {"url": "https://example.test", "headers": {"X-Key": "prefix ${TOKEN}"}},
            {"command": "node", "unknownOption": True},
        ]
        for config in unsupported:
            with self.subTest(config=config):
                self.config.unlink(missing_ok=True)
                self.source_servers({"good": {"url": "https://good.test"}, "skipped": config})
                result = self.run_sync()
                self.assertIn("skipped server skipped for Codex", result.stderr)
                self.assertNotIn("secret", result.stderr)
                self.assertNotIn("OTHER_TOKEN", result.stderr)
                servers = tomllib.loads(self.config.read_text())["mcp_servers"]
                self.assertEqual(set(servers), {"good"})
                self.run_sync("--check")

    def test_skipped_server_may_be_configured_by_hand(self):
        manual = '[mcp_servers.github]\nurl = "https://manual.test"\nbearer_token_env_var = "GH_TOKEN"\n'
        self.config.parent.mkdir()
        self.config.write_text(manual)
        self.source_servers({"github": {"url": "https://api.test", "headersHelper": "gh auth token"},
                             "good": {"url": "https://good.test"}})
        self.run_sync()
        servers = tomllib.loads(self.config.read_text())["mcp_servers"]
        self.assertEqual(servers["github"]["url"], "https://manual.test")
        self.assertEqual(servers["good"]["url"], "https://good.test")
        self.assertTrue(self.config.read_text().startswith(manual))
        self.run_sync("--check")

    def test_only_unsupported_servers_write_nothing(self):
        self.source_servers({"skipped": {"type": "sse", "url": "https://example.test/sse"}})
        result = self.run_sync()
        self.assertIn("skipped server skipped", result.stderr)
        self.assertFalse(self.config.exists())

    def test_missing_source_is_noop_and_empty_source_retires_managed_config(self):
        self.run_sync("--check")
        self.run_sync()
        self.assertFalse(self.config.parent.exists())
        self.source_servers({"one": {"url": "https://one.test"}})
        self.run_sync()
        self.source_servers({})
        self.run_sync()
        self.assertFalse(self.config.exists())

    def test_corrupt_markers_and_invalid_manual_toml_fail_without_writing(self):
        self.config.parent.mkdir()
        self.source_servers({"one": {"url": "https://one.test"}})
        for content in ('# >>> sdd-harness mcp (generated from .mcp.json; do not edit) >>>\n',
                        '[broken\n'):
            self.config.write_text(content)
            self.run_sync(success=False)
            self.assertEqual(self.config.read_text(), content)


if __name__ == "__main__":
    unittest.main()
