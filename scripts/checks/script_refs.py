#!/usr/bin/env python3
"""Gate: every script a skill or agent tells the reader to run exists.

`markdown_links` resolves markdown links; it cannot see inline-code paths, which
is how skills invoke helpers. A skill pointing at a script that was renamed or
never shipped fails at run time, in someone else's session.

Resolution is per reference, because the same text means different roots:

  * `${CLAUDE_PLUGIN_ROOT}/x`  resolves against the plugin that owns the file.
  * a bare `scripts/x`         resolves against the skill's own directory, the
                               owning plugin, or the repository root; any hit
                               passes (skills ship helpers in their own dir, and
                               repo-side skills like sdd-init run the repo's).
  * consumer-side paths        a reference that is correct only in the consuming
                               project (e.g. a project's own model generator) is
                               listed in `script_refs_project_side` in
                               harness-config.json instead of being exempted here.

References containing other placeholders ({x}, <x>, $VAR) are templates and are
skipped, as in markdown_links.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Report, agent_files, config, repo_root, skill_files

EXTS = r"(?:py|sh|ts|js|mjs|rb)"
REF = re.compile(r"(?<![\w./-])((?:\$\{CLAUDE_PLUGIN_ROOT\}/)?(?:[\w.-]+/)*scripts/[\w./-]*\.%s)\b" % EXTS)
PLUGIN_VAR = "${CLAUDE_PLUGIN_ROOT}/"


def plugin_root(path, root):
    """plugins/<name> owning this file, or None for a non-plugin layout."""
    rel = path.resolve().relative_to(Path(root).resolve())
    if len(rel.parts) >= 2 and rel.parts[0] == "plugins":
        return Path(root).resolve() / "plugins" / rel.parts[1]
    return None


def candidates(ref, path, root):
    owner = plugin_root(path, root)
    if ref.startswith(PLUGIN_VAR):
        rest = ref[len(PLUGIN_VAR):]
        return [(owner or Path(root)) / rest]
    out = [path.parent / ref]
    if owner:
        out.append(owner / ref)
    out.append(Path(root) / ref)
    return out


def main():
    root = repo_root()
    cfg = config(root)
    project_side = set(cfg.get("script_refs_project_side", []))
    r = Report("script_refs")
    checked = 0
    for path in skill_files(root, cfg) + agent_files(root, cfg):
        rel = path.relative_to(root)
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for ref in REF.findall(line):
                if ref in project_side or ref.removeprefix(PLUGIN_VAR) in project_side:
                    continue
                checked += 1
                if not any(c.exists() for c in candidates(ref, path, root)):
                    r.fail(f"{rel}:{lineno}", f"script '{ref}' does not exist "
                           "(if it is correct only in a consuming project, list it in "
                           "'script_refs_project_side' in harness-config.json)")
    print(f"  checked {checked} script reference(s)")
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
