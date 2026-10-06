#!/usr/bin/env python3
"""Gate: touching the plugin bumps the version in both manifests.

This repo already states the rule - "version bumps are required whenever plugin
behaviour changes" - and nothing checked it. The consequence is quiet: the
release workflow skips when the tag already exists, so a changed plugin ships
under an unchanged version with no error anywhere.

Two assertions, both against the merge base:
  1. If any tracked file under the plugin changed, plugin.json's version differs
     from the base's, and is higher.
  2. marketplace.json agrees with each plugin's own manifest: the top-level
     version tracks the sdd plugin (the flagship listing), and every entry in
     `plugins[]` tracks its own `source` manifest — a second plugin is never
     required to share sdd's version number.

Assertion 2 runs unconditionally, because these version numbers must agree
whether or not this branch touched a plugin.
"""

import json
import subprocess
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Report, merge_base_show, repo_root

PLUGIN_DIR = "plugins/sdd/"
PLUGIN_MANIFEST = "plugins/sdd/.claude-plugin/plugin.json"
MARKETPLACE = ".claude-plugin/marketplace.json"


def semver(text):
    try:
        return tuple(int(p) for p in str(text).split("."))
    except (ValueError, AttributeError):
        return None


def changed_paths(root):
    for base in ("origin/main", "origin/master", "main", "master"):
        try:
            mb = subprocess.run(["git", "-C", str(root), "merge-base", "HEAD", base],
                                capture_output=True, text=True, timeout=20)
            if mb.returncode != 0:
                continue
            diff = subprocess.run(["git", "-C", str(root), "diff", "--name-only",
                                   mb.stdout.strip(), "HEAD"],
                                  capture_output=True, text=True, timeout=30)
            if diff.returncode == 0:
                return [l for l in diff.stdout.splitlines() if l.strip()]
        except (OSError, subprocess.SubprocessError):
            continue
    return None


def main():
    root = repo_root()
    r = Report("version_bump")

    pm = root / PLUGIN_MANIFEST
    mk = root / MARKETPLACE
    if not pm.exists() or not mk.exists():
        print("  no plugin manifests in this repo - gate does not apply")
        return 0

    plugin = json.loads(pm.read_text(encoding="utf-8"))
    market = json.loads(mk.read_text(encoding="utf-8"))
    pv = plugin.get("version")

    # 2a. the top-level marketplace version tracks the flagship (sdd) manifest
    mv = market.get("version")
    if mv != pv:
        r.fail(MARKETPLACE, f"declares version {mv} but {PLUGIN_MANIFEST} declares {pv}")

    # 2b. every listed plugin's version agrees with its own manifest, not sdd's
    for entry in market.get("plugins", []):
        source = entry.get("source")
        ev = entry.get("version")
        if not source or ev is None:
            continue
        other_manifest = root / source.removeprefix("./") / ".claude-plugin" / "plugin.json"
        if not other_manifest.exists():
            continue
        own_v = json.loads(other_manifest.read_text(encoding="utf-8")).get("version")
        if ev != own_v:
            rel = other_manifest.relative_to(root)
            r.fail(MARKETPLACE,
                   f"lists {entry.get('name')} at version {ev} but {rel} declares {own_v}")

    # 1. a plugin change requires a bump
    changed = changed_paths(root)
    if changed is None:
        print(f"  version {pv}; no merge base - bump check skipped")
        return r.finish()

    touched = [c for c in changed if c.startswith(PLUGIN_DIR)]
    if not touched:
        print(f"  version {pv}; plugin untouched on this branch ({len(changed)} other file(s) changed)")
        return r.finish()

    base_text = merge_base_show(root, PLUGIN_MANIFEST)
    base_v = json.loads(base_text).get("version") if base_text else None
    if base_v is None:
        print(f"  version {pv}; no base manifest to compare - bump check skipped")
        return r.finish()

    if pv == base_v:
        r.fail(PLUGIN_MANIFEST,
               f"{len(touched)} file(s) under {PLUGIN_DIR} changed but version is still {pv}. "
               "The release workflow skips when the tag already exists, so this ships changed "
               "behaviour under an unchanged version and reports nothing.")
    else:
        a, b = semver(base_v), semver(pv)
        if a and b and b <= a:
            r.fail(PLUGIN_MANIFEST, f"version went {base_v} -> {pv}, which is not an increase")
        else:
            print(f"  version {base_v} -> {pv} for {len(touched)} changed plugin file(s)")

    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
