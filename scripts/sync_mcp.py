#!/usr/bin/env python3
"""Sync .mcp.json into a managed Codex MCP block; --check detects drift.

Python 3.11+, standard library only. No connections, credentials or role generation.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path

try:
    import tomllib
except ImportError:
    tomllib = None

BLOCK_START = "# >>> sdd-harness mcp (generated from .mcp.json; do not edit) >>>"
BLOCK_END = "# <<< sdd-harness mcp <<<"
ENV = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def literal(value):
    return json.dumps(value, ensure_ascii=False)


def string(value):
    if not isinstance(value, str) or "${" in value:
        raise ValueError("expected a string without interpolation")
    return value


def mapping(value):
    if not isinstance(value, dict):
        raise ValueError("expected an object")
    return value


def inline(values):
    return "{ " + ", ".join(f"{literal(k)} = {literal(v)}" for k, v in sorted(values.items())) + " }"


def server_table(name, config):
    mapping(config)
    url = config.get("url", config.get("serverUrl"))
    kind = config.get("type", "http" if url else "stdio")
    allowed = {"type", "url", "serverUrl", "headers"} if url else {"type", "command", "args", "env"}
    if set(config) - allowed:
        raise ValueError("unsupported fields: " + ", ".join(sorted(set(config) - allowed)))
    lines = [f"[mcp_servers.{literal(name)}]"]
    if url:
        if kind != "http":
            raise ValueError("only Streamable HTTP and stdio transports are supported")
        if config.get("url") and config.get("serverUrl") and config["url"] != config["serverUrl"]:
            raise ValueError("url and serverUrl disagree")
        lines.append("url = " + literal(string(url)))
        static, forwarded = {}, {}
        for key, value in mapping(config.get("headers", {})).items():
            bearer = re.fullmatch(r"Bearer \$\{([A-Za-z_][A-Za-z0-9_]*)\}", value) if isinstance(value, str) else None
            whole = ENV.fullmatch(value) if isinstance(value, str) else None
            if key.lower() == "authorization" and bearer:
                lines.append("bearer_token_env_var = " + literal(bearer.group(1)))
            elif whole:
                forwarded[key] = whole.group(1)
            else:
                static[key] = string(value)
        if static:
            lines.append("http_headers = " + inline(static))
        if forwarded:
            lines.append("env_http_headers = " + inline(forwarded))
    else:
        if kind != "stdio" or not config.get("command"):
            raise ValueError("stdio requires a command")
        lines.append("command = " + literal(string(config["command"])))
        args = config.get("args", [])
        if not isinstance(args, list):
            raise ValueError("args must be an array of strings")
        if args:
            lines.append("args = " + literal([string(arg) for arg in args]))
        static, forwarded = {}, []
        for key, value in mapping(config.get("env", {})).items():
            whole = ENV.fullmatch(value) if isinstance(value, str) else None
            if whole and whole.group(1) == key:
                forwarded.append(key)
            else:
                static[key] = string(value)
        if static:
            lines.append("env = " + inline(static))
        if forwarded:
            lines.append("env_vars = " + literal(sorted(forwarded)))
    return "\n".join(lines)


def plan(target):
    """Validate everything and return (destination, previous bytes, desired bytes)."""
    if tomllib is None:
        raise ValueError("MCP sync requires Python 3.11+ (for TOML validation)")
    source = target / ".mcp.json"
    destination = target / ".codex/config.toml"
    if source.is_symlink() or destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError("MCP source and Codex destination must be local files, not symlinks")
    servers = mapping(mapping(json.loads(source.read_text(encoding="utf-8"))).get("mcpServers", {})) if source.exists() else {}
    previous = destination.read_bytes() if destination.exists() else b""
    existing = previous.decode("utf-8")
    lines = existing.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == BLOCK_START]
    ends = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == BLOCK_END]
    if starts or ends:
        if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
            raise ValueError("invalid or duplicate generated MCP block markers")
        prefix = "".join(lines[:starts[0]])
        suffix = "".join(lines[ends[0] + 1:])
        # This separator belongs to the generator; preserve all other bytes.
        if prefix.endswith("\n\n"):
            prefix = prefix[:-1]
        rest = prefix + suffix
    else:
        rest = existing
    manual = tomllib.loads(rest)
    configured = manual.get("mcp_servers", {})
    if not isinstance(configured, dict):
        raise ValueError("manual mcp_servers must be a table")
    collisions = set(servers) & set(configured)
    if collisions:
        raise ValueError("manual Codex MCP entries conflict with .mcp.json: " + ", ".join(sorted(collisions)) +
                         "; reconcile them into .mcp.json before syncing")
    tables = []
    for name, config in sorted(servers.items()):
        try:
            tables.append(server_table(name, config))
        except ValueError as error:
            raise ValueError(f"server {name}: {error}") from error
    if tables:
        # Put tables at the end so following root keys cannot inherit their scope.
        separator = "\n" if rest.endswith("\n") else "\n\n" if rest else ""
        desired = rest + separator + BLOCK_START + "\n" + "\n\n".join(tables) + "\n" + BLOCK_END + "\n"
    else:
        desired = rest
    tomllib.loads(desired)
    return destination, previous, desired.encode("utf-8")


def sync(target, check=False):
    destination, previous, desired = plan(target)
    if previous == desired:
        print("MCP configuration is in sync.")
        return 0
    if check:
        print("MCP configuration is out of sync; run .claude/sdd/sync_mcp.py.", file=sys.stderr)
        return 1
    if not desired:
        destination.unlink()
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        # Atomic replacement avoids leaving a partial config if writing fails.
        descriptor, temporary = tempfile.mkstemp(prefix=".mcp-sync-", dir=destination.parent)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(desired)
            if destination.exists():
                os.chmod(temporary, destination.stat().st_mode & 0o777)
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    print("Synced MCP configuration from .mcp.json.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, default=Path.cwd(), help="project root (default: current directory)")
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    args = parser.parse_args()
    if not args.target.is_dir():
        parser.error("target must be an existing directory")
    try:
        return sync(args.target.resolve(), args.check)
    except (ValueError, OSError) as error:
        # Do not echo malformed JSON/TOML contents or credential values.
        print(f"MCP sync failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
