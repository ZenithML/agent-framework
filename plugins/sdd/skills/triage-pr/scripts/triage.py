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
  triage.py [--diff FILE] [--rules FILE] [--format markdown|json]
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
        # inside a hunk
        m = HUNK_RE.match(raw)
        if m:
            hunk = Hunk(raw.rstrip("\r"), int(m.group(1)), int(m.group(2)))
            cur.hunks.append(hunk)
        elif raw.startswith("+"):
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
    ("adds pipe-to-shell", [r"\b(curl|wget)\b[^|]*\|\s*(sh|bash|zsh)\b"]),
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
    return reasons


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
    for reason, regexes in CONTENT_RULES:
        if any(rx.search(line) for line in hunk.added for rx in regexes):
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
    return reasons


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
            out.append(line.rstrip() if significant else " ".join(line.split()))
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
            reasons = P + hunk_focus_reasons(f, h, rules)
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


def render_json(result):
    return json.dumps(result, indent=2, ensure_ascii=False) + "\n"


# --- CLI -------------------------------------------------------------------

def _read(path):
    with open(path, "rb") as fh:
        return fh.read().decode("utf-8", errors="replace")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="triage.py", description="Risk triage for a unified diff.")
    ap.add_argument("--diff", metavar="FILE", help="diff file (default: stdin)")
    ap.add_argument("--rules", metavar="FILE", help="repo rules JSON file")
    ap.add_argument("--format", choices=("markdown", "json"), default="markdown")
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
    out = render_json(result) if args.format == "json" else render_markdown(result, previous)
    sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
