#!/usr/bin/env python3
"""Gate: no two skill or agent descriptions are interchangeable.

The description is the only text a model sees before deciding what to load.
When a skill and the agent it dispatches carry the same string there is no
signal to choose between them, so selection becomes a coin flip. Substring
containment is treated the same way - a description wholly inside another
gives the model nothing to discriminate on either.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Report, read_doc, repo_root, skill_files, agent_files

MIN_COMPARE_LEN = 40


def normalise(text):
    return " ".join((text or "").lower().split()).rstrip(".")


def main():
    root = repo_root()
    r = Report("description_collision")

    entries = []
    for path in skill_files(root):
        fm, _ = read_doc(path)
        if fm and fm.get("description"):
            entries.append((f"skill:{path.parent.name}", path.relative_to(root), normalise(fm["description"])))
    for path in agent_files(root):
        fm, _ = read_doc(path)
        if fm and fm.get("description"):
            entries.append((f"agent:{path.stem}", path.relative_to(root), normalise(fm["description"])))

    if len(entries) < 2:
        print(f"  {len(entries)} description(s) - nothing to compare")
        return 0

    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            ka, pa, da = entries[i]
            kb, pb, db = entries[j]
            if not da or not db:
                continue
            if da == db:
                r.fail(pa, f"description is identical to {kb} ({pb})")
            elif len(da) >= MIN_COMPARE_LEN and len(db) >= MIN_COMPARE_LEN and (da in db or db in da):
                shorter, longer = (ka, kb) if len(da) < len(db) else (kb, ka)
                r.fail(pa if len(da) < len(db) else pb,
                       f"description of {shorter} is wholly contained in {longer} - "
                       "add a distinguishing trigger or boundary")

    print(f"  compared {len(entries)} descriptions")
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
