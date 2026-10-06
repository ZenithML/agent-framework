#!/usr/bin/env python3
"""Gate: adoption coverage only ever grows.

`strict_skills` and `evals_required` in harness-config.json are how a harness
with nineteen existing skills adopts a stricter standard without a flag day:
raise the bar for one skill, add its name, move on. The failure mode of that
approach is obvious and it is why this gate exists - a red pipeline gets fixed
by quietly deleting the name.

So removals are refused. Adding a name is free; taking one back needs the list
edited deliberately with this gate switched off, which is a visible act rather
than a convenient one.

Skips when there is no merge base to compare against (shallow clone, fresh
repo): a gate that fails on missing infrastructure teaches people to ignore it.

That skip is why the negative-control fixture for this gate asserts the one
failure it can observe without git history - a config that does not parse. The
removal check itself is exercised by CI on every real merge request, where a
merge base exists.
"""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Report, merge_base_show, repo_root

CONFIG_REL = "scripts/checks/harness-config.json"
RATCHETED_KEYS = ["strict_skills", "evals_required"]


def main():
    root = repo_root()
    r = Report("coverage_ratchet")

    # The current config is validated first and unconditionally. A config that
    # does not parse is a failure now, not something to discover once a merge
    # base happens to be available - and it is the assertion the fixture rests on.
    path = Path(root) / CONFIG_REL
    if not path.exists():
        print(f"  no {CONFIG_REL} in this root - gate does not apply")
        return 0
    try:
        current = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        r.fail(CONFIG_REL, f"is not valid JSON: {e}")
        return r.finish()

    base_text = merge_base_show(root, CONFIG_REL)
    if base_text is None:
        print("  config parses; no merge base available - removal check skipped")
        return r.finish()
    if base_text == "":
        print("  config parses; new on this branch - nothing to ratchet against yet")
        return r.finish()

    try:
        base = json.loads(base_text)
    except json.JSONDecodeError as e:
        r.fail(CONFIG_REL, f"config at the merge base is not valid JSON: {e}")
        return r.finish()
    for key in RATCHETED_KEYS:
        was = set(base.get(key, []))
        now = set(current.get(key, []))
        dropped = sorted(was - now)
        added = sorted(now - was)
        if dropped:
            r.fail(CONFIG_REL,
                   f"'{key}' dropped {dropped} - coverage may grow but not shrink. "
                   "If a skill genuinely should not be held to this bar, say so in the "
                   "merge request and record why; do not delete the name to get green.")
        print(f"  {key}: {len(now)} covered" + (f", +{added}" if added else ""))

    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
