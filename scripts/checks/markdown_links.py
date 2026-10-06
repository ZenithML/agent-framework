#!/usr/bin/env python3
"""Gate: every relative markdown link resolves, and every #anchor exists.

Two exclusions matter, both learned the hard way:

  * Fenced code blocks are skipped. A skill that emits a document into a
    consumer's repository contains links that are correct *there* and
    unresolvable *here*; they live in fences.
  * Lines carrying a placeholder such as {braces} or an upper-case
    <PLACEHOLDER> are skipped for the same reason - the path is a template,
    not a link from this repo.
"""

import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import Report, repo_root

LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^\s*(```|~~~)")
PLACEHOLDER_LINE = re.compile(r"\{[A-Za-z0-9_.-]+\}|<[A-Z][A-Z0-9_]{2,}>")
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$")
SKIP_DIRS = {".git", "node_modules", "__pycache__", "tests"}


def slugify(heading):
    s = heading.strip().lower()
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"\s+", "-", s).strip("-")


def anchors_of(path):
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    out, in_fence = set(), False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING.match(line)
        if m:
            out.add(slugify(m.group(1)))
    return out


def markdown_files(root):
    for p in sorted(root.rglob("*.md")):
        if any(part in SKIP_DIRS for part in p.relative_to(root).parts):
            continue
        yield p


def main():
    root = repo_root()
    r = Report("markdown_links")
    checked = 0

    for path in markdown_files(root):
        rel = path.relative_to(root)
        in_fence = False
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence or PLACEHOLDER_LINE.search(line):
                continue
            for target in LINK.findall(line):
                if target.startswith(("http://", "https://", "mailto:", "tel:")):
                    continue
                checked += 1
                filepart, _, anchor = target.partition("#")
                if not filepart:
                    if anchor and slugify(anchor) not in anchors_of(path):
                        r.fail(f"{rel}:{lineno}", f"anchor '#{anchor}' has no matching heading in this file")
                    continue
                resolved = (path.parent / filepart).resolve()
                if not resolved.exists():
                    r.fail(f"{rel}:{lineno}", f"'{filepart}' does not exist")
                elif anchor and resolved.suffix == ".md":
                    if slugify(anchor) not in anchors_of(resolved):
                        r.fail(f"{rel}:{lineno}", f"'{filepart}' has no heading matching '#{anchor}'")

    print(f"  checked {checked} relative link(s)")
    return r.finish()


if __name__ == "__main__":
    sys.exit(main())
