#!/usr/bin/env python3
"""Gate: always-on files stay under a character ceiling.

AGENTS.md is injected into every turn, so each character is paid for on every
request. `always_on_budget` in harness-config.json maps a path to its ceiling.
It is a ratchet: lowering the ceiling is free; raising it relative to the
merge base fails, so growth cannot be waved through by editing the number in
the same change. Raising it on purpose means taking this gate out of the run
for that PR, which is a visible act. A listed file that does not exist fails,
so a rename cannot silently drop the budget.

The rule that pairs with it (see standards/harness.md): a line added to
always-on text pays for itself by removing one.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import CONFIG_REL, Report, config, merge_base_show, repo_root


def main():
    root = repo_root()
    cfg = config(root)
    budget = cfg.get("always_on_budget", {})
    r = Report("always_on_budget")
    if not budget:
        print("  no always_on_budget configured - gate does not apply")
        return 0

    base = {}
    base_text = merge_base_show(root, str(CONFIG_REL))
    if base_text:
        try:
            base = json.loads(base_text).get("always_on_budget", {})
        except json.JSONDecodeError:
            pass

    for rel, ceiling in sorted(budget.items()):
        path = Path(root) / rel
        if not path.exists():
            r.fail(rel, "is listed in always_on_budget but does not exist")
            continue
        size = len(path.read_text(encoding="utf-8"))
        print(f"  {rel}: {size}/{ceiling} characters")
        if size > ceiling:
            r.fail(rel, f"{size} characters exceeds the {ceiling} ceiling. Cut text elsewhere "
                   "to pay for the addition, or move guidance to a skill/script/hook "
                   "(standards/harness.md, cost order).")
        if rel in base and ceiling > base[rel]:
            r.fail(str(CONFIG_REL), f"ceiling for {rel} raised {base[rel]} -> {ceiling}; "
                   "raising an always-on budget must be justified explicitly in the PR "
                   "and may not be combined with growth you could have paid for.")
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
