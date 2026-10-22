#!/usr/bin/env python3
"""Risk triage for a unified diff.

Reads a git unified diff and cuts it into three tiers so a human reviewer
knows where to spend attention:

  focus     read closely   (sensitive paths, risky added code, weakened tests)
  standard  review normally (no rule fired -- which is not the same as safe)
  low       safe to skip   (lockfiles, generated files, renames, whitespace)

The script is deterministic and standard-library only. It prints an ordered
markdown review path with a checklist (default) or JSON. It can only be told
to promote a hunk into the focus tier (--promote); there is no way to demote.

Usage:
  triage.py [--diff FILE] [--rules FILE] [--format markdown|json|html]
            [--promote FILE:LINE=REASON ...] [--previous FILE]

Exit status: 0 on success, 2 on a usage error, a bad rules file, a bad
promotion, or input that is not a diff.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field


class DiffError(Exception):
    """The input is not a diff this script can read."""


class RulesError(Exception):
    """The repo rules file is unreadable or invalid."""


class PromoteError(Exception):
    """A --promote argument is malformed or matches no hunk."""


# --- Parsing ---------------------------------------------------------------

@dataclass
class Hunk:
    header: str
    old_start: int
    new_start: int
    added: list = field(default_factory=list)
    removed: list = field(default_factory=list)
    raw: list = field(default_factory=list)   # body lines with their +/-/space prefix


@dataclass
class FileDiff:
    old_path: str = None
    new_path: str = None
    status: str = "modified"
    similarity: int = None
    binary: bool = False
    mode_changed: bool = False
    hunks: list = field(default_factory=list)

    @property
    def path(self):
        """The file's path: the new path, or the old path for a deletion."""
        return self.new_path if self.new_path is not None else self.old_path


HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")
QUOTED_RE = re.compile(r'"(?:[^"\\]|\\.)*"')
SIMPLE_ESCAPES = {"a": 7, "b": 8, "f": 12, "n": 10, "r": 13, "t": 9, "v": 11,
                  '"': 34, "\\": 92, "'": 39}


def unquote(s):
    """Unquote a double-quoted git path using string-literal escape rules."""
    if not (len(s) >= 2 and s[0] == '"' and s[-1] == '"'):
        return s
    body = s[1:-1]
    out = bytearray()
    i = 0
    while i < len(body):
        c = body[i]
        if c != "\\" or i + 1 >= len(body):
            out += c.encode("utf-8")
            i += 1
            continue
        m = re.match(r"[0-7]{1,3}", body[i + 1:])
        if m:
            out.append(int(m.group(0), 8) & 0xFF)
            i += 1 + len(m.group(0))
            continue
        nxt = body[i + 1]
        if nxt in SIMPLE_ESCAPES:
            out.append(SIMPLE_ESCAPES[nxt])
        else:
            out += ("\\" + nxt).encode("utf-8")
        i += 2
    return out.decode("utf-8", errors="replace")


def _strip_prefix(path, prefix):
    return path[len(prefix):] if path.startswith(prefix) else path


def _header_path(raw, prefix):
    """Path from a `--- ` / `+++ ` line, or None for /dev/null."""
    raw = raw.split("\t")[0] if not raw.startswith('"') else raw
    raw = unquote(raw.strip())
    if raw == "/dev/null":
        return None
    return _strip_prefix(raw, prefix)


def _git_header_paths(rest):
    """Old and new path from the text after `diff --git `."""
    if rest.startswith('"') or rest.endswith('"'):
        toks = QUOTED_RE.findall(rest)
        if len(toks) == 2:
            return (_strip_prefix(unquote(toks[0]), "a/"),
                    _strip_prefix(unquote(toks[1]), "b/"))
        plain = QUOTED_RE.sub("", rest).split()
        if len(toks) == 1 and len(plain) == 1:
            first_quoted = rest.startswith('"')
            q, p = unquote(toks[0]), plain[0]
            return ((_strip_prefix(q, "a/"), _strip_prefix(p, "b/")) if first_quoted
                    else (_strip_prefix(p, "a/"), _strip_prefix(q, "b/")))
    n = len(rest)
    if n % 2 == 1:
        left, right = rest[: n // 2], rest[n // 2 + 1:]
        if rest[n // 2] == " " and left[2:] == right[2:] and left.startswith("a/") \
                and right.startswith("b/"):
            return left[2:], right[2:]
    if n % 2 == 1 and rest[n // 2] == " " and rest[: n // 2] == rest[n // 2 + 1:]:
        return rest[: n // 2], rest[n // 2 + 1:]  # --no-prefix, same path twice
    idx = rest.find(" b/")
    if idx != -1:
        return _strip_prefix(rest[:idx], "a/"), rest[idx + 3:]
    return None, None


def parse_diff(text):
    """Parse a unified diff into a list of FileDiff. Raises DiffError."""
    if not text.strip():
        return []
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if not any(ln.startswith("diff --git ") for ln in lines):
        raise DiffError("input is not a git unified diff (no 'diff --git' header)")
    if any(ln.startswith(("diff --cc ", "diff --combined ")) for ln in lines):
        raise DiffError("combined diffs (merge commits) are not supported")

    files = []
    cur = None
    in_hunk = False
    hdr_old = hdr_new = None   # from ---/+++ lines
    seen_minus = seen_plus = False
    git_old = git_new = None
    rename_from = rename_to = None
    old_mode = new_mode = False
    hunk = None

    def finish():
        if cur is None:
            return
        if rename_from is not None:
            cur.old_path, cur.new_path = rename_from, rename_to
            cur.status = "renamed"
        elif seen_minus or seen_plus:
            cur.old_path, cur.new_path = hdr_old, hdr_new
        else:
            cur.old_path, cur.new_path = git_old, git_new
        if cur.status == "added":
            cur.old_path = None
            if cur.new_path is None:
                cur.new_path = git_new
        elif cur.status == "deleted":
            cur.new_path = None
            if cur.old_path is None:
                cur.old_path = git_old
        elif cur.status == "modified":
            if cur.old_path is None:
                cur.old_path = cur.new_path
            if cur.new_path is None:
                cur.new_path = cur.old_path
        cur.mode_changed = old_mode and new_mode
        if cur.path is None:
            raise DiffError("cannot read the file path from a 'diff --git' header")
        files.append(cur)

    for raw in lines:
        if raw.startswith("diff --git "):
            finish()
            cur = FileDiff()
            in_hunk = False
            hdr_old = hdr_new = None
            seen_minus = seen_plus = False
            rename_from = rename_to = None
            old_mode = new_mode = False
            hunk = None
            git_old, git_new = _git_header_paths(raw[len("diff --git "):].rstrip("\r"))
            continue
        if cur is None:
            continue
        if not in_hunk:
            ln = raw.rstrip("\r")
            m = HUNK_RE.match(ln)
            if m:
                in_hunk = True
                hunk = Hunk(ln, int(m.group(1)), int(m.group(2)))
                cur.hunks.append(hunk)
            elif ln.startswith("new file mode"):
                cur.status = "added"
            elif ln.startswith("deleted file mode"):
                cur.status = "deleted"
            elif ln.startswith("rename from "):
                rename_from = unquote(ln[len("rename from "):])
            elif ln.startswith("rename to "):
                rename_to = unquote(ln[len("rename to "):])
            elif ln.startswith("similarity index "):
                m2 = re.match(r"similarity index (\d+)%", ln)
                if m2:
                    cur.similarity = int(m2.group(1))
            elif ln.startswith("old mode "):
                old_mode = True
            elif ln.startswith("new mode "):
                new_mode = True
            elif ln.startswith("Binary files ") or ln.startswith("GIT binary patch"):
                cur.binary = True
            elif ln.startswith("--- "):
                seen_minus = True
                hdr_old = _header_path(ln[4:], "a/")
            elif ln.startswith("+++ "):
                seen_plus = True
                hdr_new = _header_path(ln[4:], "b/")
            continue
        # inside a hunk; a CRLF diff keeps "\r" on every line, so drop it once
        raw = raw.rstrip("\r")
        m = HUNK_RE.match(raw)
        if m:
            hunk = Hunk(raw, int(m.group(1)), int(m.group(2)))
            cur.hunks.append(hunk)
            continue
        hunk.raw.append(raw)
        if raw.startswith("+"):
            hunk.added.append(raw[1:])
        elif raw.startswith("-"):
            hunk.removed.append(raw[1:])
    finish()
    return files


# --- Rules -----------------------------------------------------------------

RULE_KEYS = ("focus_paths", "low_paths", "focus_patterns")


def load_rules(path):
    """Load the optional repo rules file. None gives empty rules."""
    rules = {k: [] for k in RULE_KEYS}
    if path is None:
        return rules
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as e:
        raise RulesError("%s: cannot read rules file: %s" % (path, e.strerror or e))
    except ValueError as e:
        raise RulesError("%s: invalid JSON: %s" % (path, e))
    if not isinstance(data, dict):
        raise RulesError("%s: rules must be a JSON object" % path)
    for key, value in data.items():
        if key not in RULE_KEYS:
            raise RulesError("%s: unknown key %r (allowed: %s)" % (path, key, ", ".join(RULE_KEYS)))
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise RulesError("%s: key %r must be a list of regex strings" % (path, key))
        for src in value:
            try:
                rules[key].append((src, re.compile(src)))
            except re.error as e:
                raise RulesError("%s: key %r has an invalid regex %r: %s" % (path, key, src, e))
    return rules


def _ci(pattern):
    return re.compile(pattern, re.IGNORECASE)


SENSITIVE_RE = _ci(r"(auth|login|session|passw|secret|token|credential|crypto|permission"
                   r"|acl|security|sanitiz|payment|billing)")
MIGRATION_RES = [_ci(p) for p in (r"(^|/)migrations?/", r"\.sql$", r"(^|/)schema\.[a-z]+$")]
CI_RES = [_ci(p) for p in (r"(^|/)\.github/workflows/", r"(^|/)Dockerfile", r"\.tf$",
                           r"(^|/)\.gitlab-ci\.yml$", r"(^|/)Jenkinsfile$")]
ENV_RE = _ci(r"(^|/)\.env(\.|$)")
TEST_DIR_RE = _ci(r"(^|/)(tests?|__tests__|spec)/")
TEST_BASE_RES = [_ci(p) for p in (r"^test_.*\.py$", r"_test\.(py|go)$", r"\.(test|spec)\.[a-z]+$")]
LOCKFILES = {n.lower() for n in (
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock",
    "Pipfile.lock", "Cargo.lock", "Gemfile.lock", "composer.lock", "go.sum",
    "bun.lockb", "flake.lock")}
GENERATED_RES = [_ci(p) for p in (
    r"(^|/)(dist|build|vendor|node_modules|third_party|__generated__|generated)/",
    r"\.min\.(js|css)$", r"\.snap$", r"\.pb\.go$", r"_pb2(_grpc)?\.py$", r"\.generated\.")]

CONTENT_RULES = [
    ("adds eval(", [r"\beval\("]),
    ("adds exec(", [r"\bexec\("]),
    ("adds shell execution", [r"shell\s*=\s*True", r"os\.system\(", r"child_process", r"subprocess\."]),
    ("adds rm -rf", [r"rm\s+-[a-z]*r[a-z]*f", r"rm\s+-[a-z]*f[a-z]*r"]),
    ("adds sudo", [r"\bsudo\b"]),
    ("adds pipe-to-shell", [r"\b(curl|wget)\b.*\|\s*(sh|bash|zsh)\b"]),
    ("adds destructive SQL", [r"\b(DROP|TRUNCATE)\s+(TABLE|DATABASE)\b", r"\bDELETE\s+FROM\b",
                              r"\bALTER\s+TABLE\b"]),
    ("adds unsafe deserialisation", [r"pickle\.loads?\(", r"yaml\.load\((?![^)]*SafeLoader)",
                                     r"\bunserialize\("]),
    ("adds raw HTML injection", [r"innerHTML\s*=", r"dangerouslySetInnerHTML"]),
    ("disables verification", [r"verify\s*=\s*False", r"--no-verify",
                               r"rejectUnauthorized\s*:\s*false", r"InsecureSkipVerify\s*:\s*true"]),
    ("adds force flag", [r"--force\b"]),
    ("widens CI permissions", [r"continue-on-error\s*:\s*true", r"permissions\s*:\s*write-all",
                               r"\bpull_request_target\b"]),
    ("suppresses a check", [r"#\s*noqa", r"eslint-disable", r"@ts-ignore", r"@ts-expect-error",
                            r"#\s*type:\s*ignore", r"//\s*nolint", r"pragma:\s*no\s*cover",
                            r"#\s*nosec"]),
]
CONTENT_RULES = [(reason, [_ci(p) for p in pats]) for reason, pats in CONTENT_RULES]

ASSERT_RE = _ci(r"\b(assert\w*|expect|should|verify)\b")
SKIP_RES = [_ci(p) for p in (r"\.(skip|only)\(", r"@pytest\.mark\.(skip|xfail)", r"\bxit\(",
                             r"\bxdescribe\(", r"@Disabled\b", r"@Ignore\b", r"\bt\.Skip\(",
                             r"unittest\.skip")]
INDENT_EXTS = (".py", ".yaml", ".yml", ".mk")


def _basename(path):
    return path.rsplit("/", 1)[-1]


def is_test_file(path):
    base = _basename(path)
    return bool(TEST_DIR_RE.search(path)) or any(r.search(base) for r in TEST_BASE_RES)


def _candidate_paths(f):
    """New path first, then the old path for a rename."""
    if f.status == "renamed":
        return [f.new_path, f.old_path]
    return [f.path]


def _dedup(reasons):
    """Drop repeated reasons, keeping the first occurrence of each."""
    return list(dict.fromkeys(reasons))


def path_focus_reasons(f, rules):
    """Focus reasons that come from the file's path."""
    paths = _candidate_paths(f)
    reasons = []
    for p in paths:
        m = SENSITIVE_RE.search(p)
        if m:
            reasons.append("sensitive path: " + m.group(1).lower())
            break
    if any(r.search(p) for p in paths for r in MIGRATION_RES):
        reasons.append("migration or schema")
    if any(r.search(p) for p in paths for r in CI_RES):
        reasons.append("CI or deploy config")
    if any(ENV_RE.search(p) for p in paths):
        reasons.append("env file")
    if f.status == "deleted" and is_test_file(f.path):
        reasons.append("deletes test file")
    for src, rx in rules["focus_paths"]:
        if any(rx.search(p) for p in paths):
            reasons.append("repo rule: " + src)
    return _dedup(reasons)


def file_low_reason(f, rules):
    """Reason the whole file is low-risk, or None. First match wins."""
    path = f.path
    if _basename(path).lower() in LOCKFILES:
        return "lockfile"
    if any(r.search(path) for r in GENERATED_RES):
        return "generated or vendored"
    for src, rx in rules["low_paths"]:
        if any(rx.search(p) for p in _candidate_paths(f)):
            return "repo rule: " + src
    if f.status == "renamed" and not f.hunks:
        return "pure rename"
    if f.mode_changed and not f.hunks and f.status != "renamed":
        return "mode change only"
    if f.status in ("added", "deleted") and not f.hunks and not f.binary:
        return "empty file"
    return None


def hunk_focus_reasons(f, hunk, rules):
    """Content and test-weakening reasons for one hunk."""
    reasons = []
    # Built-in rules see the added lines as one text, with backslash
    # continuations folded, so a statement split over lines is judged whole.
    added = re.sub(r"\\[ \t]*\n\s*", " ", "\n".join(hunk.added))
    for reason, regexes in CONTENT_RULES:
        if any(rx.search(added) for rx in regexes):
            reasons.append(reason)
    for src, rx in rules["focus_patterns"]:
        if any(rx.search(line) for line in hunk.added):
            reasons.append("repo rule: " + src)
    if is_test_file(f.path):
        gone = sum(1 for line in hunk.removed if ASSERT_RE.search(line))
        kept = sum(1 for line in hunk.added if ASSERT_RE.search(line))
        if gone > kept:
            reasons.append("removes assertions")
        if any(rx.search(line) for line in hunk.added for rx in SKIP_RES):
            reasons.append("adds skip marker")
    return _dedup(reasons)


def is_whitespace_only(f, hunk):
    """True when the hunk only changes whitespace (or blank lines)."""
    if not hunk.added and not hunk.removed:
        return False
    path = f.path
    base = _basename(path)
    significant = path.endswith(INDENT_EXTS) or base == "Makefile"

    def norm(lines):
        out = []
        for line in lines:
            if not line.strip():
                continue
            # Inner spaces can be inside a string literal, so only the edges go.
            out.append(line.rstrip() if significant else line.strip())
        return out

    return norm(hunk.removed) == norm(hunk.added)


# --- Tiering ---------------------------------------------------------------

def _hunk_key(f, hunk):
    return hunk.old_start if f.status == "deleted" else hunk.new_start


def _make_item(tier_name, f, line, hunks, reasons):
    item = {"tier": tier_name, "file": f.path}
    if f.status == "renamed":
        item["old_file"] = f.old_path
    item["line"] = line
    item["hunks"] = len(hunks)
    item["added"] = sum(len(h.added) for h in hunks)
    item["removed"] = sum(len(h.removed) for h in hunks)
    item["reasons"] = list(reasons)
    item["_hunks"] = [{"header": h.header, "lines": h.raw} for h in hunks]  # for --format html
    return item


def triage(files, rules, promotions):
    """Build the ordered items and the summary."""
    states = []
    for f in files:
        P = path_focus_reasons(f, rules)
        st = {"f": f, "focus": [], "std": [], "low": [], "low_reason": None, "bare": None}
        states.append(st)
        low = file_low_reason(f, rules)
        if not P and low:
            st["low"] = list(f.hunks)
            st["low_reason"] = low
            if not f.hunks:
                st["bare"] = _make_item("low", f, None, [], [low])
            continue
        if not f.hunks:
            if P:
                st["bare"] = _make_item("focus", f, None, [], P)
            elif f.binary:
                st["bare"] = _make_item("standard", f, None, [], ["binary"])
            else:
                st["bare"] = _make_item("standard", f, None, [], [])
            continue
        st["low_reason"] = "whitespace only"
        for h in f.hunks:
            if is_whitespace_only(f, h):
                st["low"].append(h)
                continue
            reasons = _dedup(P + hunk_focus_reasons(f, h, rules))
            if reasons:
                st["focus"].append((h, reasons))
            else:
                st["std"].append(h)

    for fname, line, reason in promotions:
        _promote(states, fname, line, reason)

    focus, standard, low = [], [], []
    for st in states:
        f = st["f"]
        if st["bare"]:
            {"focus": focus, "standard": standard, "low": low}[st["bare"]["tier"]].append(st["bare"])
            continue
        for h, reasons in st["focus"]:
            focus.append(_make_item("focus", f, _hunk_key(f, h), [h], reasons))
        if st["std"]:
            standard.append(_make_item("standard", f, None, st["std"], []))
        if st["low"]:
            low.append(_make_item("low", f, None, st["low"], [st["low_reason"]]))

    # Focus: grouped by file, groups by max reason count desc then path;
    # within a group by line, null first.
    best = {}
    for it in focus:
        best[it["file"]] = max(best.get(it["file"], 0), len(it["reasons"]))
    focus.sort(key=lambda it: (-best[it["file"]], it["file"],
                               it["line"] is not None, it["line"] or 0))
    standard.sort(key=lambda it: (-(it["added"] + it["removed"]), it["file"]))
    low.sort(key=lambda it: it["file"])

    def lines(items):
        return sum(i["added"] + i["removed"] for i in items)

    summary = {
        "files": len(files),
        "changed_lines": lines(focus) + lines(standard) + lines(low),
        "focus": {"items": len(focus), "lines": lines(focus)},
        "standard": {"items": len(standard), "lines": lines(standard)},
        "low": {"items": len(low), "lines": lines(low)},
    }
    return {"summary": summary, "items": focus + standard + low}


def _promote(states, fname, line, reason):
    label = "promoted: " + reason
    for st in states:
        f = st["f"]
        if f.path != fname:
            continue
        for entry in st["focus"]:
            if _hunk_key(f, entry[0]) == line:
                if label not in entry[1]:
                    entry[1].append(label)
                return
        for bucket in ("std", "low"):
            for h in st[bucket]:
                if _hunk_key(f, h) == line:
                    st[bucket].remove(h)
                    st["focus"].append((h, [label]))
                    return
    raise PromoteError("--promote %s:%d=%s matches no hunk" % (fname, line, reason))


def parse_promotion(arg):
    left, sep, reason = arg.partition("=")
    fname, sep2, line = left.rpartition(":")
    if not sep or not sep2 or not fname or not line.isdigit() or not reason.strip():
        raise PromoteError("bad --promote %r: expected FILE:LINE=REASON" % arg)
    return fname, int(line), reason.strip()


# --- Rendering -------------------------------------------------------------

MINUS = "−"
EMDASH = "—"
MARKER = "<!-- sdd:triage-pr -->"
COVERAGE = (
    "### Coverage\n"
    'Tiers come from path and content heuristics, not from understanding the code. "Review normally"\n'
    'is not "safe": nothing fired there, which is all the triage claims. Tick each item in section 1\n'
    "as you read it. An item still unticked when you approve was not reviewed " + EMDASH + " say so in the review\n"
    "instead of approving silently.\n"
)


def _names(item):
    if "old_file" in item:
        return "`%s` → `%s`" % (item["old_file"], item["file"])
    return "`%s`" % item["file"]


def _counts(item):
    return "+%d %s%d" % (item["added"], MINUS, item["removed"])


def _focus_text(item):
    loc = "" if item["line"] is None else " L%d" % item["line"]
    return "%s%s (%s) %s %s" % (_names(item), loc, _counts(item), EMDASH, "; ".join(item["reasons"]))


def _standard_text(item):
    if item["reasons"] == ["binary"]:
        return "%s (binary)" % _names(item)
    n = item["hunks"]
    return "%s (%s, %d %s)" % (_names(item), _counts(item), n, "hunk" if n == 1 else "hunks")


def _low_text(item):
    return "%s (%s) %s %s" % (_names(item), _counts(item), EMDASH, "; ".join(item["reasons"]))


def _ticked(previous):
    ticked = set()
    for ln in (previous or "").split("\n"):
        m = re.match(r"- \[[xX]\] (.*)$", ln.rstrip("\r"))
        if m:
            ticked.add(m.group(1).rstrip())
    return ticked


def render_markdown(result, previous=None):
    s = result["summary"]
    if s["files"] == 0:
        return "Nothing to triage: the diff is empty.\n"
    ticked = _ticked(previous)

    def section(tier_name, fmt, box=False):
        items = [i for i in result["items"] if i["tier"] == tier_name]
        if not items:
            return ["_None._"]
        out = []
        for i in items:
            text = fmt(i)
            if box:
                out.append("- [%s] %s" % ("x" if text in ticked else " ", text))
            else:
                out.append("- " + text)
        return out

    out = [MARKER, "## Review triage", "",
           "%d files, %d changed lines." % (s["files"], s["changed_lines"]),
           "**Read closely: %d hunks, %d lines.** Review normally: %d files, %d lines. "
           "Safe to skip: %d files, %d lines." % (
               s["focus"]["items"], s["focus"]["lines"],
               s["standard"]["items"], s["standard"]["lines"],
               s["low"]["items"], s["low"]["lines"]),
           "", "### 1. Read closely"]
    out += section("focus", _focus_text, box=True)
    out += ["", "### 2. Review normally"]
    out += section("standard", _standard_text)
    out += ["", "### 3. Safe to skip"]
    out += section("low", _low_text)
    out += [""]
    return "\n".join(out) + "\n" + COVERAGE


def _public(result):
    """The result without the private keys (those starting with '_')."""
    items = [{k: v for k, v in it.items() if not k.startswith("_")} for it in result["items"]]
    return {"summary": result["summary"], "items": items}


def render_json(result):
    return json.dumps(_public(result), indent=2, ensure_ascii=False) + "\n"


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Review triage</title>
<style>
:root{--bg:#f6f7f9;--fg:#1c2330;--mute:#5d6676;--line:#dde1e8;--card:#fff;--focus:#c2410c;--focus-bg:#fdeee4;--std:#2f5d8a;--std-bg:#e6eef6;--low:#4b7a5a;--low-bg:#e6f1ea;--add:#e3f4e8;--del:#fbe6e6;--mono:ui-monospace,Menlo,Consolas,monospace}
@media (prefers-color-scheme:dark){:root{--bg:#12161d;--fg:#e6e9ef;--mute:#9aa3b2;--line:#2a313d;--card:#1a1f28;--focus:#fb923c;--focus-bg:#33201a;--std:#7fb0e0;--std-bg:#1b2836;--low:#7fc296;--low-bg:#1b2a21;--add:#16301f;--del:#3a1c1f;color-scheme:dark}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
header{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:12px max(16px,env(safe-area-inset-left,0px))}
.wrap{max-width:980px;margin:0 auto}
h1{font-size:20px;margin:0 0 8px}
.bar{display:flex;height:10px;border-radius:5px;overflow:hidden;gap:2px;background:var(--line)}
.bar span{min-width:3px}
.cov{margin-top:8px;font-size:14px}.cov b{color:var(--focus)}
.tabs{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap}
.tabs button{font:inherit;font-size:13px;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:14px;padding:3px 12px;cursor:pointer}
.tabs button[aria-pressed=true]{border-color:var(--fg)}
main{padding:16px max(16px,env(safe-area-inset-left,0px)) 48px}
.list{display:flex;flex-direction:column;gap:10px}
.item{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--c);border-radius:6px;min-width:0}
.item[data-tier=focus]{--c:var(--focus)}.item[data-tier=standard]{--c:var(--std)}.item[data-tier=low]{--c:var(--low)}
.top{display:flex;gap:10px;padding:10px 12px;align-items:flex-start}
.top input{width:18px;height:18px;margin-top:3px;flex:none}
.head{flex:1;min-width:0}
.path{font:13px var(--mono);overflow-wrap:anywhere}
.meta{color:var(--mute);font-size:12px;font-variant-numeric:tabular-nums}
.tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:6px}
.tag{font-size:12px;padding:1px 8px;border-radius:10px;background:var(--focus-bg);color:var(--focus)}
.item[data-tier=low] .tag{background:var(--low-bg);color:var(--low)}
.item.done{opacity:.6}.item.done .path{text-decoration:line-through}
.tog{font:inherit;font-size:13px;background:none;border:0;color:var(--std);cursor:pointer;padding:0 4px}
.diff{overflow-x:auto;border-top:1px solid var(--line);font:12px/1.45 var(--mono)}
.diff .hh{padding:3px 12px;color:var(--mute);background:var(--std-bg)}
.diff .l{display:block;white-space:pre;padding:0 12px;min-width:max-content}
.diff .a{background:var(--add)}.diff .d{background:var(--del)}
:focus-visible{outline:2px solid var(--std);outline-offset:2px}
.note{color:var(--mute);font-size:13px}
</style></head><body>
<header><div class="wrap"><h1>Review triage</h1>
<div class="bar" id="bar"></div><div class="cov" id="cov"></div>
<div class="tabs" id="tabs"></div></div></header>
<main><div class="wrap"><p class="note">Ordered review path. Tick each item once you have read it; unticked "Read closely" items are counted as not reviewed. Ticks are kept in this browser only.</p><div class="list" id="list"></div></div></main>
<script>
const DATA=__DATA__;
const NAMES={focus:"Read closely",standard:"Review normally",low:"Safe to skip"};
const KEY="triage:"+location.pathname+":"+DATA.items.length+":"+DATA.summary.changed_lines;
let ticks={};try{ticks=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
let tab="all";
const $=id=>document.getElementById(id);
const id=i=>i.file+":"+(i.line==null?"":i.line)+":"+i.tier;
const n=i=>i.added+i.removed;
const by=t=>DATA.items.filter(i=>i.tier===t);
const sum=a=>a.reduce((x,i)=>x+n(i),0);
function head(){
  const tot=sum(DATA.items)||1;
  $("bar").innerHTML=["focus","standard","low"].map(t=>`<span style="flex:${sum(by(t))};background:var(--${t=="focus"?"focus":t=="standard"?"std":"low"})"></span>`).join("");
  const f=by("focus"),open=f.filter(i=>!ticks[id(i)]).length;
  $("cov").innerHTML=f.length?(open?`<b>${open} of ${f.length}</b> "Read closely" items not yet read (${sum(f.filter(i=>!ticks[id(i)])).toLocaleString()} lines). Approving now would skip them.`:`All ${f.length} "Read closely" items read.`):"Nothing needs close reading.";
  $("tabs").innerHTML=[["all","All ("+DATA.items.length+")"]].concat(["focus","standard","low"].map(t=>[t,NAMES[t]+" ("+by(t).length+")"])).map(([k,l])=>`<button aria-pressed="${tab===k}" data-k="${k}">${l}</button>`).join("");
  document.querySelectorAll(".tabs button").forEach(b=>b.onclick=()=>{tab=b.dataset.k;head();list()});
}
function list(){
  const root=$("list");root.textContent="";
  DATA.items.filter(i=>tab==="all"||i.tier===tab).forEach(i=>{
    const el=document.createElement("div");el.className="item"+(ticks[id(i)]?" done":"");el.dataset.tier=i.tier;
    const top=document.createElement("div");top.className="top";
    const cb=document.createElement("input");cb.type="checkbox";cb.checked=!!ticks[id(i)];cb.setAttribute("aria-label","Mark read: "+i.file);
    cb.onchange=()=>{ticks[id(i)]=cb.checked;try{localStorage.setItem(KEY,JSON.stringify(ticks))}catch(e){}el.classList.toggle("done",cb.checked);head()};
    const h=document.createElement("div");h.className="head";
    const p=document.createElement("div");p.className="path";p.textContent=i.file;
    const m=document.createElement("div");m.className="meta";
    m.textContent=NAMES[i.tier]+(i.line!=null?" \u00b7 line "+i.line:"")+" \u00b7 +"+i.added+" -"+i.removed;
    h.append(p,m);
    if(i.reasons.length){const t=document.createElement("div");t.className="tags";i.reasons.forEach(r=>{const s=document.createElement("span");s.className="tag";s.textContent=r;t.append(s)});h.append(t)}
    const tg=document.createElement("button");tg.className="tog";
    const dv=document.createElement("div");dv.className="diff";
    (i._hunks||[]).forEach(hk=>{const hh=document.createElement("div");hh.className="hh";hh.textContent=hk.header;dv.append(hh);
      hk.lines.forEach(l=>{const s=document.createElement("span");s.className="l"+(l[0]=="+"?" a":l[0]=="-"?" d":"");s.textContent=l||" ";dv.append(s)})});
    const show=i.tier==="focus";dv.hidden=!show;tg.textContent=show?"Hide diff":"Show diff";
    tg.onclick=()=>{dv.hidden=!dv.hidden;tg.textContent=dv.hidden?"Show diff":"Hide diff"};
    if(!i._hunks||!i._hunks.length)tg.hidden=true;
    top.append(cb,h,tg);el.append(top,dv);root.append(el);
  });
}
head();list();
</script></body></html>
"""


def render_html(result):
    """One self-contained page: the ordered review path with diffs and ticks."""
    data = json.dumps(result, ensure_ascii=False).replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__DATA__", data)


# --- CLI -------------------------------------------------------------------

def _read(path):
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8", errors="replace")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="triage.py", description="Risk triage for a unified diff.")
    ap.add_argument("--diff", metavar="FILE", help="diff file (default: stdin)")
    ap.add_argument("--rules", metavar="FILE", help="repo rules JSON file")
    ap.add_argument("--format", choices=("markdown", "json", "html"), default="markdown")
    ap.add_argument("--promote", action="append", default=[], metavar="FILE:LINE=REASON",
                    help="move a hunk into the focus tier (repeatable)")
    ap.add_argument("--previous", metavar="FILE",
                    help="earlier triage comment body, to carry ticks over")
    args = ap.parse_args(argv)  # exits 2 on a usage error

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        promotions = [parse_promotion(p) for p in args.promote]
        rules = load_rules(args.rules)
        if args.diff:
            text = _read(args.diff)
        else:
            if sys.stdin.isatty():
                ap.print_help(sys.stderr)
                return 2
            text = sys.stdin.buffer.read().decode("utf-8", errors="replace")
        previous = _read(args.previous) if args.previous else None
        files = parse_diff(text)
        result = triage(files, rules, promotions)
    except OSError as e:
        print("triage.py: %s: %s" % (e.filename, e.strerror), file=sys.stderr)
        return 2
    except (DiffError, RulesError, PromoteError) as e:
        print("triage.py: %s" % e, file=sys.stderr)
        return 2
    if args.format == "json":
        out = render_json(result)
    elif args.format == "html":
        out = render_html(result)
    else:
        out = render_markdown(result, previous)
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
