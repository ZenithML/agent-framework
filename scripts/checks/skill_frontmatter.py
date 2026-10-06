#!/usr/bin/env python3
"""Gate: every skill carries valid frontmatter, at the strictness it is held to.

Two tiers, from harness-config.json. `minimum_frontmatter` applies to every
skill in the repo. `strict_frontmatter` applies only to the skills named in
`strict_skills`, so a large existing harness can adopt the fuller schema one
skill at a time instead of in a single red-pipeline commit. coverage_ratchet.py
is what stops that list going backwards.

The "Does not trigger" clause is a FAIL for every skill at either tier, not a
warning: it is the boundary that disambiguates one skill from another, and a
warning does not bind.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Report, config, read_doc, repo_root, skill_files, skill_name

DESCRIPTION_MAX_CHARS = 1024
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def main():
    root = repo_root()
    r = Report("skill_frontmatter")
    files = skill_files(root)
    if not files:
        print("  no skills found")
        return 0

    cfg = config(root)
    minimum = cfg.get("minimum_frontmatter", ["name", "description"])
    strict = cfg.get("strict_frontmatter", minimum)
    strict_skills = set(cfg.get("strict_skills", []))
    strict_count = 0

    for path in files:
        rel = path.relative_to(root)
        fm, _ = read_doc(path)
        if fm is None:
            r.fail(rel, "no YAML frontmatter block (must start with '---')")
            continue

        name = skill_name(path)
        is_strict = name in strict_skills
        strict_count += is_strict
        required = strict if is_strict else minimum
        missing = [k for k in required if not fm.get(k)]
        if missing:
            tier = "strict" if is_strict else "minimum"
            r.fail(rel, f"missing {tier} frontmatter: {', '.join(missing)}")

        expected_name = path.parent.name
        if fm.get("name") and fm["name"] != expected_name:
            r.fail(rel, f"name '{fm['name']}' does not match directory '{expected_name}'")

        # Rule S1 named this gate but only the directory half was ever checked.
        pattern = cfg.get("name_pattern")
        if pattern and not re.match(pattern, expected_name):
            r.fail(rel, f"name '{expected_name}' does not match the required pattern {pattern}")

        desc = fm.get("description", "") or ""
        if len(desc) > DESCRIPTION_MAX_CHARS:
            r.fail(rel, f"description is {len(desc)} chars, over the {DESCRIPTION_MAX_CHARS} cap")
        if "<" in desc or ">" in desc:
            r.fail(rel, "description contains '<' or '>' - use {braces} for placeholders")
        if "does not trigger" not in desc.lower():
            r.fail(rel, "description has no 'Does not trigger' clause (the boundary is required)")

        version = fm.get("version", "")
        if version and not SEMVER.match(version):
            r.fail(rel, f"version '{version}' is not semver (x.y.z)")

        updated = fm.get("updated", "")
        if updated and not ISO_DATE.match(updated):
            r.fail(rel, f"updated '{updated}' is not an ISO date (YYYY-MM-DD)")

    print(f"  checked {len(files)} skill(s); {strict_count} held to the strict schema")
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
