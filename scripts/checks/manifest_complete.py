#!/usr/bin/env python3
"""Gate: the 'Files in this skill' manifest names everything the skill ships.

The manifest is the map a reader uses to know what else to open. When a
shipped file is missing from it, that file is invisible to anyone working
from the skill - which is how a validator sitting inside a skill folder goes
unnoticed and unrun.
"""

import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Report, config, repo_root, skill_files

MANIFEST_HEADING = re.compile(r"^#{2,3}\s+Files in this skill\s*$", re.I | re.M)
BACKTICKED = re.compile(r"`([^`]+)`")
IGNORE_NAMES = {".DS_Store"}
IGNORE_SUFFIXES = {".pyc"}


def shipped_files(skill_dir):
    out = []
    for p in sorted(skill_dir.rglob("*")):
        if not p.is_file():
            continue
        if p.name in IGNORE_NAMES or p.suffix in IGNORE_SUFFIXES:
            continue
        if "__pycache__" in p.parts:
            continue
        out.append(p.relative_to(skill_dir).as_posix())
    return out


def main():
    root = repo_root()
    r = Report("manifest_complete")
    files = skill_files(root)
    if not files:
        print("  no skills found")
        return 0

    cfg = config(root)
    # Coverage list, same ratchet as strict_skills. A repo adopting the manifest
    # convention across an existing set of skills does it one skill at a time;
    # `true` still means every skill, for a repo that starts with the convention.
    covered = cfg.get("manifest_skills", cfg.get("manifest_required", True))
    if covered is False:
        print("  manifest convention not adopted in this repo")
        return 0
    if covered is not True:
        names = set(covered)
        files = [f for f in files if f.parent.name in names]
        if not files:
            print("  no skills listed in manifest_skills yet - the list is a ratchet")
            return 0

    for skill_md in files:
        skill_dir = skill_md.parent
        rel = skill_md.relative_to(root)
        body = skill_md.read_text(encoding="utf-8")
        m = MANIFEST_HEADING.search(body)
        if not m:
            r.fail(rel, "no '## Files in this skill' manifest section")
            continue

        section = body[m.end():]
        nxt = re.search(r"^#{2,3}\s+\S", section, re.M)
        if nxt:
            section = section[: nxt.start()]
        named = set()
        for token in BACKTICKED.findall(section):
            named.add(token.strip().rstrip("/"))

        shipped = shipped_files(skill_dir)
        # both directions: nothing shipped is unnamed, nothing named is missing
        for entry in sorted(named):
            if entry in shipped or any(f.startswith(entry + "/") for f in shipped):
                continue
            if "/" not in entry and not entry.endswith((".md", ".json", ".sh", ".py", ".txt", ".yml")):
                continue  # a prose mention, not a path
            r.fail(rel, "manifest names " + repr(entry) + " which the skill does not ship")

        for file_path in shipped:
            if file_path in named:
                continue
            # a directory entry such as `examples/foo/` covers everything under it
            if any(file_path.startswith(n + "/") for n in named):
                continue
            r.fail(rel, f"manifest omits shipped file '{file_path}'")

    print(f"  checked {len(files)} manifest(s)")
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
