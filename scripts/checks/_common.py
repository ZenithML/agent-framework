"""Shared helpers for the repo's gate scripts. Python 3, stdlib only.

Discovery is driven by harness-config.json so the same gate code runs against
both this repo's plugin layout (plugins/*/skills) and a .claude/skills layout.

Deliberately not a general YAML parser: it reads the one flat frontmatter
shape this harness uses (plain scalars, folded/literal block scalars, and
inline flow sequences). Taking a PyYAML dependency would add an install step
to CI for no gain, and the gates must run locally with nothing installed.
"""

import json
import re
import sys
from pathlib import Path

TOP_LEVEL_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$")
BLOCK_INDICATORS = (">", "|", ">-", "|-", ">+", "|+", "")


def repo_root(argv=None):
    """Root to check. Defaults to the repo containing this file."""
    argv = sys.argv if argv is None else argv
    if len(argv) > 1:
        return Path(argv[1]).resolve()
    return Path(__file__).resolve().parents[2]


def split_frontmatter(text):
    """Return (frontmatter_text, body) or (None, text) when absent."""
    if not text.startswith("---\n"):
        return None, text
    end = text.find("\n---", 4)
    if end == -1:
        return None, text
    return text[4:end], text[end + 4:]


def parse_frontmatter(raw):
    """Parse the flat frontmatter shape into a dict of str -> str | list[str]."""
    lines = raw.split("\n")
    out = {}
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = TOP_LEVEL_KEY.match(line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            out[key] = [p.strip() for p in inner.split(",") if p.strip()] if inner else []
            i += 1
        elif val in BLOCK_INDICATORS:
            block, i = [], i + 1
            while i < n and (lines[i][:1] in (" ", "\t") or not lines[i].strip()):
                block.append(lines[i])
                i += 1
            kept = [l.strip() for l in block if l.strip()]
            # A folded scalar (">") folds line breaks into spaces; a literal ("|")
            # keeps them. Joining a folded block with newlines splits phrases that
            # happen to wrap, which made the "Does not trigger" check fail on
            # perfectly good descriptions - a false positive is as bad as a gate
            # that never fires, because it teaches people to bypass the gate.
            out[key] = ("\n" if val.startswith("|") else " ").join(kept)
        else:
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ("\"", "'"):
                val = val[1:-1]
            out[key] = val
            i += 1
    return out


def read_doc(path):
    """Return (frontmatter_dict_or_None, body) for a markdown file."""
    text = path.read_text(encoding="utf-8")
    raw, body = split_frontmatter(text)
    return (parse_frontmatter(raw) if raw is not None else None), body


CONFIG_FILE = Path(__file__).resolve().parent / "harness-config.json"

DEFAULT_LAYOUT = {
    "skill_globs": [".claude/skills/**/SKILL.md"],
    "agent_globs": [".claude/agents/*.md"],
}


CONFIG_REL = Path("scripts/checks/harness-config.json")


def config(root=None):
    """Gate configuration for the root being checked.

    Resolved relative to the root, not to this file, so a fixture directory can
    carry its own config and exercise a gate under settings that differ from the
    repo's. Without this, every fixture would inherit the repo's coverage lists
    and the gates whose behaviour depends on them would silently no-op - which
    is how a negative control stops being one.
    """
    for candidate in ([Path(root) / CONFIG_REL] if root else []) + [CONFIG_FILE]:
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {}


def _glob_all(root, patterns):
    seen, out = set(), []
    for pattern in patterns:
        for p in sorted(root.glob(pattern)):
            if p.name == "README.md" or p in seen:
                continue
            seen.add(p)
            out.append(p)
    return sorted(out)


def skill_files(root, cfg=None):
    """Every skill in the repo, including bundled examples.

    Bundled examples are included on purpose: a worked example an agent
    pattern-matches against is the highest-leverage file to keep correct,
    so it must not sit outside the gate.
    """
    cfg = config(root) if cfg is None else cfg
    layout = cfg.get("layout", DEFAULT_LAYOUT)
    return _glob_all(root, layout.get("skill_globs", DEFAULT_LAYOUT["skill_globs"]))


def agent_files(root, cfg=None):
    cfg = config(root) if cfg is None else cfg
    layout = cfg.get("layout", DEFAULT_LAYOUT)
    return _glob_all(root, layout.get("agent_globs", DEFAULT_LAYOUT["agent_globs"]))


def skill_name(path):
    """Directory name for a skill file (plugin and .claude layouts agree here)."""
    return path.parent.name


def merge_base_show(root, path):
    """File contents at the merge base with the default branch, or None.

    Used by the ratchet and version gates. Returns None when there is no
    usable base - a shallow clone, a detached run, or a fresh repo - so those
    gates skip rather than fail on infrastructure.
    """
    import subprocess

    for base in ("origin/main", "origin/master", "main", "master"):
        try:
            mb = subprocess.run(["git", "-C", str(root), "merge-base", "HEAD", base],
                                capture_output=True, text=True, timeout=20)
            if mb.returncode != 0:
                continue
            sha = mb.stdout.strip()
            show = subprocess.run(["git", "-C", str(root), "show", f"{sha}:{path}"],
                                  capture_output=True, text=True, timeout=20)
            if show.returncode == 0:
                return show.stdout
            return ""      # base exists, file did not
        except (OSError, subprocess.SubprocessError):
            continue
    return None


class Report:
    """Collects findings so a gate can report every problem, not just the first."""

    def __init__(self, name):
        self.name = name
        self.failures = []
        self.warnings = []

    def fail(self, where, message):
        self.failures.append(f"{where}: {message}")

    def warn(self, where, message):
        self.warnings.append(f"{where}: {message}")

    def finish(self):
        for w in self.warnings:
            print(f"  WARN  {w}")
        for f in self.failures:
            print(f"  FAIL  {f}")
        return 1 if self.failures else 0
