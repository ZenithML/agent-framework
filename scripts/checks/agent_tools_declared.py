#!/usr/bin/env python3
"""Gate: every agent declares its role and its tool list.

An agent with no `tools:` key inherits everything the caller has, which
silently voids whatever context isolation the pipeline claims. An agent with
no `role:` cannot be checked against a contract at all.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Report, agent_files, read_doc, repo_root

ROLES_FILE = Path(__file__).resolve().parent / "agent_roles.json"


def main():
    root = repo_root()
    r = Report("agent_tools_declared")
    known_roles = set(json.loads(ROLES_FILE.read_text(encoding="utf-8"))["roles"])

    files = agent_files(root)
    if not files:
        print("  no agents in this repo yet - gate is in place for when there are")
        return 0

    for path in files:
        rel = path.relative_to(root)
        fm, _ = read_doc(path)
        if fm is None:
            r.fail(rel, "no YAML frontmatter block")
            continue
        if not fm.get("description"):
            r.fail(rel, "missing 'description'")
        if "tools" not in fm:
            r.fail(rel, "declares no 'tools:' - it would inherit every tool the caller has")
        elif not fm["tools"]:
            r.fail(rel, "'tools:' is empty")
        role = fm.get("role")
        if not role:
            r.fail(rel, f"declares no 'role:' - must be one of {sorted(known_roles)}")
        elif role not in known_roles:
            r.fail(rel, f"role '{role}' is not defined in agent_roles.json ({sorted(known_roles)})")

    print(f"  checked {len(files)} agent(s)")
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
