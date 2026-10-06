#!/usr/bin/env python3
"""Gate: every skill ships real baseline evaluations.

The three-scenario shape is not decoration - happy path proves the skill
works, the gate proves it refuses, and the signature-failure scenario names
the mistake this specific skill is most likely to make. A file of TODO
placeholders satisfies a file-exists check while asserting nothing, so the
content is checked too.
"""

import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Report, config, repo_root, skill_files, skill_name

REQUIRED_FIELDS = ["schema_version", "skill", "skill_version_at_eval_creation", "purpose", "scenarios"]
REQUIRED_SCENARIOS = 3
ID_SUFFIXES = ["-001-happy-path", "-002-gate", "-003-"]
PLACEHOLDER = re.compile(r"^\s*(todo|tbd|xxx+|placeholder|\.\.\.)\s*$", re.I)


def main():
    root = repo_root()
    r = Report("evals_present")
    files = skill_files(root)
    if not files:
        print("  no skills found")
        return 0

    required_skills = set(config(root).get("evals_required", [s.parent.name for s in files]))
    covered = [s for s in files if skill_name(s) in required_skills]
    if not covered:
        print(f"  no skills listed in evals_required yet (of {len(files)}) - "
              "the list is a ratchet, add names as evals land")
        return 0

    for skill_md in covered:
        name = skill_md.parent.name
        path = skill_md.parent / "evaluations" / "baseline-evals.json"
        rel = path.relative_to(root)
        if not path.exists():
            r.fail(skill_md.parent.relative_to(root), "evaluations/baseline-evals.json does not exist")
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            r.fail(rel, f"not valid JSON: {e}")
            continue

        for field in REQUIRED_FIELDS:
            if field not in data:
                r.fail(rel, f"missing field '{field}'")

        if data.get("skill") and data["skill"] != name:
            r.fail(rel, f"skill '{data['skill']}' does not match directory '{name}'")

        if PLACEHOLDER.match(str(data.get("purpose", ""))):
            r.fail(rel, "purpose is a placeholder")

        scenarios = data.get("scenarios") or []
        if len(scenarios) < REQUIRED_SCENARIOS:
            r.fail(rel, f"has {len(scenarios)} scenario(s), needs at least {REQUIRED_SCENARIOS}")

        for idx, sc in enumerate(scenarios):
            for field in ("id", "query", "expected_behavior"):
                if field not in sc:
                    r.fail(rel, f"scenario[{idx}] missing '{field}'")
            if PLACEHOLDER.match(str(sc.get("query", ""))):
                r.fail(rel, f"scenario[{idx}] '{sc.get('id','?')}' has a placeholder query")
            behaviours = sc.get("expected_behavior") or []
            if isinstance(behaviours, list) and not [b for b in behaviours if not PLACEHOLDER.match(str(b))]:
                r.fail(rel, f"scenario[{idx}] '{sc.get('id','?')}' has no real expected_behavior")

        for i, suffix in enumerate(ID_SUFFIXES):
            if i < len(scenarios):
                sid = str(scenarios[i].get("id", ""))
                if not sid.startswith(name) or suffix not in sid:
                    r.fail(rel, f"scenario[{i}] id '{sid}' should be '{name}{suffix}...'")

        if len(scenarios) >= 3:
            third = str(scenarios[2].get("id", ""))
            if third.endswith("-003-") or ("signature" not in third and third.count("-") < 3):
                r.warn(rel, f"scenario[2] id '{third}' should name the actual failure mode, not a generic label")

    print(f"  checked {len(covered)} of {len(files)} skill(s) (evals_required)")
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
