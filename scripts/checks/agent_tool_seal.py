#!/usr/bin/env python3
"""Gate: an agent's declared tools satisfy its role's contract.

This is the gate that defends context isolation. The pipeline's isolation
claims live in prose that a model can exceed; the `tools:` list is the part
that actually binds, because an undeclared tool cannot be called. So the
list is what CI checks - and the verifier role is the one that matters most,
since a verifier able to read the code it grades is exactly the setup that
reports success while real behaviour regresses.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Report, agent_files, read_doc, repo_root

ROLES_FILE = Path(__file__).resolve().parent / "agent_roles.json"


def base_tool(name):
    """Compare on the bare tool name; MCP tools keep their full path."""
    return name.strip()


def main():
    root = repo_root()
    r = Report("agent_tool_seal")
    roles = json.loads(ROLES_FILE.read_text(encoding="utf-8"))["roles"]

    files = agent_files(root)
    if not files:
        print("  no agents in this repo yet - gate is in place for when there are")
        return 0

    for path in files:
        rel = path.relative_to(root)
        fm, _ = read_doc(path)
        if fm is None:
            continue
        role_name = fm.get("role")
        contract = roles.get(role_name) if role_name else None
        if not contract:
            continue  # agent_tools_declared.py owns that failure
        declared = {base_tool(t) for t in (fm.get("tools") or [])}

        for forbidden in contract.get("forbidden_tools", []):
            if forbidden in declared:
                r.fail(rel, f"role '{role_name}' forbids '{forbidden}' but the agent declares it "
                            f"- {contract['purpose']}")
        for required in contract.get("required_tools", []):
            if required not in declared:
                r.fail(rel, f"role '{role_name}' requires '{required}' but the agent does not declare it")

    print(f"  checked {len(files)} agent(s) against {len(roles)} role contract(s)")
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
