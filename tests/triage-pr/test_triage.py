"""Tests for plugins/sdd/skills/triage-pr/scripts/triage.py (scenarios T1-T19).

Standard-library unittest only. The script is imported by path and also run
through its command line.
"""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = ROOT / "plugins/sdd/skills/triage-pr/scripts/triage.py"
FIXTURES = HERE / "fixtures"

_spec = importlib.util.spec_from_file_location("triage", SCRIPT)
T = importlib.util.module_from_spec(_spec)
sys.modules["triage"] = T
_spec.loader.exec_module(T)


# --- diff builders ---------------------------------------------------------

def hunk(lines, old_start=1, new_start=None):
    new_start = old_start if new_start is None else new_start
    old_n = sum(1 for x in lines if x[:1] in (" ", "-"))
    new_n = sum(1 for x in lines if x[:1] in (" ", "+"))
    head = "@@ -%d,%d +%d,%d @@\n" % (old_start, old_n, new_start, new_n)
    return head + "".join(x + "\n" for x in lines)


def moddiff(path, *hunks):
    return ("diff --git a/%s b/%s\nindex 111..222 100644\n--- a/%s\n+++ b/%s\n"
            % (path, path, path, path)) + "".join(hunks)


def adddiff(path, lines):
    return ("diff --git a/%s b/%s\nnew file mode 100644\nindex 000..222\n"
            "--- /dev/null\n+++ b/%s\n" % (path, path, path)) + hunk(
        ["+" + x for x in lines], 0, 1)


def deldiff(path, lines):
    return ("diff --git a/%s b/%s\ndeleted file mode 100644\nindex 111..000\n"
            "--- a/%s\n+++ /dev/null\n" % (path, path, path)) + hunk(
        ["-" + x for x in lines], 1, 0)


def renamediff(old, new, sim=100, *hunks):
    s = "diff --git a/%s b/%s\nsimilarity index %d%%\nrename from %s\nrename to %s\n" % (
        old, new, sim, old, new)
    if hunks:
        s += "index 111..222 100644\n--- a/%s\n+++ b/%s\n" % (old, new) + "".join(hunks)
    return s


def run(diff, rules=None, promote=None):
    files = T.parse_diff(diff)
    return T.triage(files, rules or T.load_rules(None), promote or [])


def tier(result, name):
    return [i for i in result["items"] if i["tier"] == name]


def reasons_of(diff, path=None, **kw):
    focus = tier(run(diff, **kw), "focus")
    if path:
        focus = [i for i in focus if i["file"] == path]
    out = []
    for i in focus:
        out.extend(i["reasons"])
    return out


def write_tmp(tc, name, content):
    d = Path(tempfile.mkdtemp())
    tc.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
    p = d / name
    p.write_text(content, encoding="utf-8")
    return p


def cli(*args, stdin=""):
    return subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin,
                          capture_output=True, text=True, encoding="utf-8")


MIXED = (FIXTURES / "mixed.diff").read_text(encoding="utf-8")


# --- T1 --------------------------------------------------------------------

class TestParsing(unittest.TestCase):
    def test_all_shapes(self):
        diff = (
            moddiff("a.txt", hunk([" c", "-old", "+new1", "+new2", "\\ No newline at end of file"], 3, 3))
            + adddiff("new.txt", ["x", "y"])
            + deldiff("gone.txt", ["z"])
            + renamediff("r/old.txt", "r/new.txt", 100)
            + renamediff("e/old.txt", "e/new.txt", 87, hunk(["-a", "+b"], 5, 6))
            + "diff --git a/img.png b/img.png\nindex 1..2 100644\n"
              "Binary files a/img.png and b/img.png differ\n"
            + "diff --git a/run.sh b/run.sh\nold mode 100644\nnew mode 100755\n"
            + 'diff --git "a/caf\\303\\251 \\"q\\".bin" "b/caf\\303\\251 \\"q\\".bin"\n'
              'index 1..2 100644\nBinary files "a/caf\\303\\251 \\"q\\".bin" and '
              '"b/caf\\303\\251 \\"q\\".bin" differ\n'
        )
        fs = {f.path: f for f in T.parse_diff(diff)}
        a = fs["a.txt"]
        self.assertEqual(a.status, "modified")
        self.assertEqual(len(a.hunks), 1)
        h = a.hunks[0]
        self.assertEqual((h.old_start, h.new_start), (3, 3))
        self.assertEqual((len(h.added), len(h.removed)), (2, 1))
        self.assertEqual(h.added, ["new1", "new2"])
        self.assertTrue(h.header.startswith("@@ -3,"))
        n = fs["new.txt"]
        self.assertEqual(n.status, "added")
        self.assertEqual(len(n.hunks[0].added), 2)
        g = fs["gone.txt"]
        self.assertEqual(g.status, "deleted")
        self.assertEqual(g.path, "gone.txt")
        r = fs["r/new.txt"]
        self.assertEqual((r.status, r.old_path, r.similarity, r.hunks), ("renamed", "r/old.txt", 100, []))
        e = fs["e/new.txt"]
        self.assertEqual((e.status, e.old_path, e.similarity), ("renamed", "e/old.txt", 87))
        self.assertEqual(e.hunks[0].new_start, 6)
        self.assertTrue(fs["img.png"].binary)
        self.assertEqual(fs["img.png"].hunks, [])
        m = fs["run.sh"]
        self.assertTrue(m.mode_changed)
        self.assertEqual(m.hunks, [])
        self.assertIn('café "q".bin', fs)
        self.assertTrue(fs['café "q".bin'].binary)

    def test_quoted_paths_via_rename_and_headers(self):
        f = T.parse_diff('diff --git "a/o\\tld" "b/n\\\\ew"\nsimilarity index 100%\n'
                         'rename from "o\\tld"\nrename to "n\\\\ew"\n')[0]
        self.assertEqual((f.status, f.old_path, f.new_path), ("renamed", "o\tld", "n\\ew"))
        diff = ('diff --git "a/t\\tb" "b/t\\tb"\nindex 1..2 100644\n'
                '--- "a/t\\tb"\n+++ "b/t\\\\b"\n' + hunk(["-x", "+y"]))
        f = T.parse_diff(diff)[0]
        self.assertEqual((f.old_path, f.new_path), ("t\tb", "t\\b"))

    def test_no_prefix_headers(self):
        diff = ("diff --git img.png img.png\nindex 1..2 100644\n"
                "Binary files img.png and img.png differ\n"
                "diff --git run.sh run.sh\nold mode 100644\nnew mode 100755\n")
        fs = T.parse_diff(diff)
        self.assertEqual([f.path for f in fs], ["img.png", "run.sh"])
        self.assertTrue(fs[0].binary)
        self.assertTrue(fs[1].mode_changed)
        res = cli(stdin=diff)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertNotIn("Traceback", res.stderr)

    def test_unparseable_header_exits_2(self):
        diff = "diff --git x y\nindex 1..2 100644\nBinary files x and y differ\n"
        with self.assertRaises(T.DiffError):
            T.parse_diff(diff)
        res = cli(stdin=diff)
        self.assertEqual(res.returncode, 2)
        self.assertNotIn("Traceback", res.stderr)
        self.assertIn("triage.py:", res.stderr)

    def test_plus_plus_header_not_counted(self):
        f = T.parse_diff(moddiff("a.txt", hunk(["-x", "+y"])))[0]
        self.assertEqual((len(f.hunks[0].added), len(f.hunks[0].removed)), (1, 1))

    def test_git_binary_patch(self):
        f = T.parse_diff("diff --git a/b.bin b/b.bin\nnew file mode 100644\n"
                         "index 0..1\nGIT binary patch\nliteral 3\nabc\n")[0]
        self.assertTrue(f.binary)
        self.assertEqual(f.status, "added")


# --- T2 / T3 ---------------------------------------------------------------

class TestLow(unittest.TestCase):
    def low_reason(self, diff):
        low = tier(run(diff), "low")
        self.assertEqual(len(low), 1, run(diff)["items"])
        return low[0]["reasons"]

    def test_lockfiles_and_generated(self):
        body = hunk(["-a", "+eval(b)"])
        for path in ["package-lock.json", "sub/yarn.lock", "go.sum"]:
            self.assertEqual(self.low_reason(moddiff(path, body)), ["lockfile"], path)
        self.assertEqual(self.low_reason(deldiff("uv.lock", ["x"])), ["lockfile"])
        for path in ["dist/a.js", "vendor/x/y.go", "app.min.js", "a/b.snap", "x.pb.go",
                     "x_pb2.py", "x_pb2_grpc.py", "api.generated.ts", "node_modules/q/i.js"]:
            self.assertEqual(self.low_reason(moddiff(path, body)), ["generated or vendored"], path)

    def test_low_not_content_scanned(self):
        r = run(moddiff("dist/a.js", hunk(["-a", "+eval(b)"])))
        self.assertEqual(tier(r, "focus"), [])

    def test_no_hunk_cases(self):
        self.assertEqual(self.low_reason(renamediff("a/x.py", "b/x.py")), ["pure rename"])
        pr = renamediff("a/x.py", "b/x.py") + ""
        pr = pr.replace("similarity index 100%\n", "old mode 100644\nnew mode 100755\nsimilarity index 100%\n")
        self.assertEqual(self.low_reason(pr), ["pure rename"])
        self.assertEqual(self.low_reason("diff --git a/run.sh b/run.sh\nold mode 100644\nnew mode 100755\n"),
                         ["mode change only"])
        self.assertEqual(self.low_reason("diff --git a/e.txt b/e.txt\nnew file mode 100644\nindex 0..e69\n"),
                         ["empty file"])


# --- T4 / T5 / T6 ----------------------------------------------------------

class TestPathFocus(unittest.TestCase):
    def test_sensitive_path_once(self):
        # matches "auth", "token" and "session" in the path
        diff = moddiff("src/auth/token_session.py", hunk(["-a", "+b"], 1), hunk(["-c", "+d"], 20))
        focus = tier(run(diff), "focus")
        self.assertEqual(len(focus), 2)
        for i in focus:
            self.assertEqual(i["reasons"], ["sensitive path: auth"])

    def test_other_path_reasons(self):
        h = hunk(["-a", "+b"])
        cases = {
            "db/migrations/001.py": "migration or schema",
            "q.sql": "migration or schema",
            "db/schema.rb": "migration or schema",
            ".github/workflows/ci.yml": "CI or deploy config",
            "Dockerfile": "CI or deploy config",
            "infra/main.tf": "CI or deploy config",
            ".env": "env file",
            "cfg/.env.local": "env file",
        }
        for path, reason in cases.items():
            self.assertIn(reason, reasons_of(moddiff(path, h)), path)

    def test_path_focus_beats_low(self):
        h = hunk(["-a", "+b"])
        self.assertEqual(tier(run(moddiff("vendor/auth/x.js", h)), "low"), [])
        self.assertEqual(len(tier(run(moddiff("vendor/auth/x.js", h)), "focus")), 1)
        rules = T.load_rules(self._rules({"low_paths": ["^src/auth/"]}))
        r = run(moddiff("src/auth/x.js", h), rules=rules)
        self.assertEqual(len(tier(r, "focus")), 1)
        self.assertEqual(tier(r, "low"), [])

    def _rules(self, obj):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(d, ignore_errors=True))
        p = d / "r.json"
        p.write_text(json.dumps(obj))
        return str(p)

    def test_rename_old_path_and_no_hunk(self):
        r = run(renamediff("auth/a.py", "util/a.py", 90, hunk(["-a", "+b"], 4)))
        focus = tier(r, "focus")
        self.assertEqual(len(focus), 1)
        self.assertEqual(focus[0]["reasons"], ["sensitive path: auth"])
        self.assertEqual(focus[0]["old_file"], "auth/a.py")
        r = run(renamediff("util/a.py", "auth/a.py"))
        focus = tier(r, "focus")
        self.assertEqual(len(focus), 1)
        self.assertIsNone(focus[0]["line"])
        md = T.render_markdown(r)
        self.assertIn("- [ ] `util/a.py` → `auth/a.py` (+0 −0) — sensitive path: auth", md)
        item_line = next(x for x in md.split("\n") if x.startswith("- [ ] `util/a.py`"))
        self.assertIsNone(re.search(r" L\d+", item_line), item_line)


# --- T7 / T8 ---------------------------------------------------------------

CONTENT = {
    "adds eval(": "x = eval(s)",
    "adds exec(": "exec(code)",
    "adds shell execution": "subprocess.run(c, shell=True)",
    "adds rm -rf": "rm -rf /tmp/x",
    "adds sudo": "sudo apt install x",
    "adds pipe-to-shell": "curl http://x.sh | bash",
    "adds destructive SQL": "DROP TABLE users;",
    "adds unsafe deserialisation": "d = pickle.loads(b)",
    "adds raw HTML injection": "el.innerHTML = v",
    "disables verification": "requests.get(u, verify=False)",
    "adds force flag": "git push --force",
    "widens CI permissions": "continue-on-error: true",
    "suppresses a check": "x = 1  # noqa",
}


class TestContent(unittest.TestCase):
    def test_each_rule_fires_on_added_only(self):
        for reason, line in CONTENT.items():
            added = moddiff("src/app.py", hunk([" ctx", "+" + line]))
            self.assertIn(reason, reasons_of(added), reason)
            removed = moddiff("src/app.py", hunk([" ctx", "-" + line, "+safe = 1"]))
            self.assertNotIn(reason, reasons_of(removed), reason)
            context = moddiff("src/app.py", hunk([" " + line, "+safe = 1"]))
            self.assertNotIn(reason, reasons_of(context), reason)

    def test_extra_variants(self):
        for reason, line in [("adds shell execution", "os.system(c)"),
                             ("adds shell execution", "child_process.exec(c)"),
                             ("adds destructive SQL", "delete from t"),
                             ("adds destructive SQL", "ALTER TABLE t ADD c int"),
                             ("adds unsafe deserialisation", "yaml.load(f)"),
                             ("adds raw HTML injection", "<div dangerouslySetInnerHTML={x}/>"),
                             ("widens CI permissions", "on: pull_request_target"),
                             ("suppresses a check", "// eslint-disable-next-line"),
                             ("disables verification", "git commit --no-verify")]:
            self.assertIn(reason, reasons_of(moddiff("src/app.py", hunk(["+" + line]))), line)
        self.assertNotIn("adds unsafe deserialisation",
                         reasons_of(moddiff("src/app.py", hunk(["+yaml.load(f, Loader=SafeLoader)"]))))

    def test_pipe_to_shell_multi_pipe(self):
        for line in ["curl u | tee f | bash", "curl u | gpg -d | sh", "wget -qO- u | zsh",
                     "curl u|sh"]:
            self.assertIn("adds pipe-to-shell",
                          reasons_of(moddiff("src/app.py", hunk(["+" + line]))), line)
        for line in ["curl u | shellcheck -", "curl u -o f", "echo hi | bash"]:
            self.assertNotIn("adds pipe-to-shell",
                             reasons_of(moddiff("src/app.py", hunk(["+" + line]))), line)

    def test_multiline_statements_judged_whole(self):
        self.assertIn("adds pipe-to-shell", reasons_of(
            moddiff("src/app.sh", hunk(["+curl -fsSL u \\", "+  | bash"]))))
        self.assertNotIn("adds unsafe deserialisation", reasons_of(
            moddiff("src/app.py", hunk(["+yaml.load(", "+    f,", "+    Loader=SafeLoader)"]))))
        self.assertIn("adds unsafe deserialisation", reasons_of(
            moddiff("src/app.py", hunk(["+yaml.load(", "+    f)"]))))

    def test_crlf_lines_judged_like_lf(self):
        diff = moddiff("src/app.sh", hunk(["+curl -fsSL u \\", "+  | bash"])).replace("\n", "\r\n")
        self.assertIn("adds pipe-to-shell", reasons_of(diff))
        h = T.parse_diff(diff)[0].hunks[0]
        self.assertEqual(h.added, ["curl -fsSL u \\", "  | bash"])

    def test_reason_order_and_once(self):
        diff = moddiff("src/app.py", hunk(["+a = eval(1)", "+b = eval(2)", "+sudo ls"]))
        self.assertEqual(reasons_of(diff), ["adds eval(", "adds sudo"])


class TestTestWeakening(unittest.TestCase):
    def test_removed_asserts(self):
        d = moddiff("tests/test_cart.py", hunk(["-    assert a", "-    assert b", "+    pass"]))
        self.assertIn("removes assertions", reasons_of(d))
        d = moddiff("tests/test_cart.py", hunk(["-    assert a", "+    assert b"]))
        self.assertNotIn("removes assertions", reasons_of(d))
        d = moddiff("tests/test_cart.py", hunk(["+    assert a", "+    assert b"]))
        self.assertNotIn("removes assertions", reasons_of(d))
        d = moddiff("src/cart.py", hunk(["-    assert a", "-    assert b", "+    pass"]))
        self.assertNotIn("removes assertions", reasons_of(d))

    def test_skip_markers(self):
        for line in ["it.skip('x', f)", "@pytest.mark.skip", "@pytest.mark.xfail", "xit('x')",
                     "xdescribe('x')", "@Disabled", "@Ignore", "t.Skip()", "@unittest.skip('x')",
                     "describe.only('x')"]:
            d = moddiff("tests/test_cart.py", hunk(["+" + line]))
            self.assertIn("adds skip marker", reasons_of(d), line)

    def test_deleted_test_file(self):
        r = run(deldiff("tests/test_old.py", ["def test_a():", "    pass"]))
        focus = tier(r, "focus")
        self.assertEqual(len(focus), 1)
        self.assertIn("deletes test file", focus[0]["reasons"])
        self.assertEqual(focus[0]["line"], 1)
        self.assertEqual(tier(run(deldiff("src/old.py", ["x"])), "focus"), [])


# --- T9 --------------------------------------------------------------------

class TestWhitespace(unittest.TestCase):
    def test_js_reindent_low(self):
        r = run(moddiff("src/a.js", hunk(["-  foo();", "+    foo();"])))
        self.assertEqual(tier(r, "standard"), [])
        self.assertEqual(tier(r, "low")[0]["reasons"], ["whitespace only"])

    def test_inner_spacing_in_string_not_low(self):
        r = run(moddiff("src/a.js", hunk(['-x = "a   b";', '+x = "a b";'])))
        self.assertEqual(tier(r, "low"), [])
        self.assertEqual(len(tier(r, "standard")), 1)

    def test_py_reindent_not_low(self):
        r = run(moddiff("src/a.py", hunk(["-  foo()", "+    foo()"])))
        self.assertEqual(tier(r, "low"), [])
        self.assertEqual(len(tier(r, "standard")), 1)
        r = run(moddiff("src/a.py", hunk(["-x = 1  ", "+x = 1"])))
        self.assertEqual(len(tier(r, "low")), 1)

    def test_blank_lines_low(self):
        r = run(moddiff("src/a.js", hunk([" c", "+", "+"])))
        self.assertEqual(len(tier(r, "low")), 1)

    def test_reordered_not_low(self):
        r = run(moddiff("src/a.js", hunk(["-a();", "-b();", "+b();", "+a();"])))
        self.assertEqual(tier(r, "low"), [])

    def test_whitespace_beats_content_focus(self):
        r = run(moddiff("src/a.js", hunk(["-eval(x)", "+  eval(x)"])))
        self.assertEqual(tier(r, "focus"), [])
        self.assertEqual(len(tier(r, "low")), 1)
        r = run(moddiff("src/auth/a.js", hunk(["-foo()", "+  foo()"])))
        self.assertEqual(tier(r, "focus"), [])

    def test_file_splits_and_totals(self):
        diff = moddiff("src/a.js", hunk(["-  foo();", "+    foo();"], 1), hunk([" c", "+bar();"], 10))
        r = run(diff)
        self.assertEqual(len(tier(r, "standard")), 1)
        self.assertEqual(len(tier(r, "low")), 1)
        s = r["summary"]
        self.assertEqual(s["files"], 1)
        self.assertEqual(s["changed_lines"], 3)
        self.assertEqual(s["standard"]["lines"] + s["low"]["lines"] + s["focus"]["lines"], 3)


# --- T10 / T11 -------------------------------------------------------------

class TestBinaryAndOrdering(unittest.TestCase):
    def test_binary(self):
        diff = "diff --git a/i.png b/i.png\nindex 1..2 100644\nBinary files a/i.png and b/i.png differ\n"
        r = run(diff)
        std = tier(r, "standard")
        self.assertEqual(len(std), 1)
        self.assertEqual(std[0]["reasons"], ["binary"])
        self.assertIn("- `i.png` (binary)", T.render_markdown(r))

    def test_ordering(self):
        diff = (
            moddiff("a/token.py", hunk(["-a", "+b"], 30), hunk(["-a", "+b"], 5))
            + moddiff("z/auth/one.py", hunk(["+eval(1)"], 7))
            + moddiff("small.py", hunk(["+x"]))
            + moddiff("big.py", hunk(["+1", "+2", "+3", "+4", "+5"]))
            + moddiff("aaa.py", hunk(["+x"]))
            + moddiff("yarn.lock", hunk(["+x"]))
            + moddiff("a/package-lock.json", hunk(["+x"]))
        )
        r = run(diff)
        focus = [(i["file"], i["line"]) for i in tier(r, "focus")]
        self.assertEqual(focus, [("z/auth/one.py", 7), ("a/token.py", 5), ("a/token.py", 30)])
        self.assertEqual([i["file"] for i in tier(r, "standard")], ["big.py", "aaa.py", "small.py"])
        self.assertEqual([i["file"] for i in tier(r, "low")], ["a/package-lock.json", "yarn.lock"])
        self.assertEqual([i["tier"] for i in r["items"]],
                         ["focus"] * 3 + ["standard"] * 3 + ["low"] * 2)


# --- T12 -------------------------------------------------------------------

class TestRules(unittest.TestCase):
    def rules(self, obj, raw=None):
        p = write_tmp(self, "rules.json", raw if raw is not None else json.dumps(obj))
        return str(p)

    def test_repo_rules(self):
        h = hunk(["-a", "+b"])
        rules = T.load_rules(self.rules({"focus_paths": ["^ledger/"]}))
        self.assertEqual(reasons_of(moddiff("ledger/rates.py", h), rules=rules),
                         ["repo rule: ^ledger/"])
        rules = T.load_rules(self.rules({"low_paths": ["^docs/api/"]}))
        self.assertEqual(tier(run(moddiff("docs/api/a.md", h), rules=rules), "low")[0]["reasons"],
                         ["repo rule: ^docs/api/"])
        rules = T.load_rules(self.rules({"focus_patterns": [r"\bfeature_flag\("]}))
        d = moddiff("src/a.py", hunk(["+feature_flag('x')"]))
        self.assertEqual(reasons_of(d, rules=rules), [r"repo rule: \bfeature_flag\("])

    def test_case_sensitivity(self):
        h = hunk(["-a", "+b"])
        rules = T.load_rules(self.rules({"focus_paths": ["^Ledger/"]}))
        self.assertEqual(tier(run(moddiff("ledger/x.py", h), rules=rules), "focus"), [])
        rules = T.load_rules(self.rules({"focus_paths": ["(?i)^Ledger/"]}))
        self.assertEqual(len(tier(run(moddiff("ledger/x.py", h), rules=rules), "focus")), 1)
        self.assertEqual(reasons_of(moddiff("src/AUTH/x.py", h)), ["sensitive path: auth"])
        self.assertIn("adds eval(", reasons_of(moddiff("src/x.py", hunk(["+EVAL(1)"]))))

    def test_duplicate_reasons_once(self):
        h = hunk(["+feature_flag('x')", "+feature_flag('y')"])
        rules = T.load_rules(self.rules({"focus_paths": ["^src/", "^src/"],
                                         "focus_patterns": [r"feature_flag\(", r"feature_flag\("]}))
        self.assertEqual(reasons_of(moddiff("src/auth/a.py", h), rules=rules),
                         ["sensitive path: auth", "repo rule: ^src/",
                          r"repo rule: feature_flag\("])
        # the same path reason on the file and the hunk is not repeated
        rules = T.load_rules(self.rules({"focus_paths": ["^src/"], "focus_patterns": ["^src/"]}))
        d = moddiff("src/a.py", hunk(["+x"]))
        got = reasons_of(d, rules=rules)
        self.assertEqual(len(got), len(set(got)), got)

    def test_bad_rules(self):
        cases = [
            (None, "{not json", "rules.json"),
            ({"nope": []}, None, "nope"),
            ({"focus_paths": "x"}, None, "focus_paths"),
            ({"low_paths": [1]}, None, "low_paths"),
            ({"focus_patterns": ["("]}, None, "focus_patterns"),
            ([], None, "rules.json"),
        ]
        for obj, raw, needle in cases:
            p = self.rules(obj, raw)
            with self.assertRaises(T.RulesError) as cm:
                T.load_rules(p)
            self.assertIn(needle, str(cm.exception))
            self.assertIn("rules.json", str(cm.exception))
            res = cli("--rules", p, stdin="")
            self.assertEqual(res.returncode, 2)
            self.assertIn(needle, res.stderr)


# --- T13 -------------------------------------------------------------------

class TestPromote(unittest.TestCase):
    DIFF = moddiff("src/app.js", hunk([" c", "+x"], 10), hunk([" c", "+y", "+z"], 30))

    def test_standard_hunk_moves(self):
        before = run(self.DIFF)
        r = run(self.DIFF, promote=[("src/app.js", 10, "changes pricing")])
        focus = tier(r, "focus")
        self.assertEqual(len(focus), 1)
        self.assertEqual(focus[0]["line"], 10)
        self.assertEqual(focus[0]["reasons"], ["promoted: changes pricing"])
        self.assertEqual(r["summary"]["focus"], {"items": 1, "lines": 1})
        self.assertEqual(r["summary"]["standard"], {"items": 1, "lines": 2})
        self.assertEqual(before["summary"]["standard"]["lines"], 3)
        self.assertEqual(r["summary"]["changed_lines"], 3)
        self.assertIn("promoted: changes pricing", T.render_json(r))

    def test_already_focus_gains_reason(self):
        d = moddiff("src/auth/a.js", hunk(["+x"], 4))
        r = run(d, promote=[("src/auth/a.js", 4, "why")])
        self.assertEqual(tier(r, "focus")[0]["reasons"], ["sensitive path: auth", "promoted: why"])

    def test_promote_twice_same_reason_once(self):
        d = moddiff("src/auth/a.js", hunk(["+x"], 4))
        r = run(d, promote=[("src/auth/a.js", 4, "why"), ("src/auth/a.js", 4, "why")])
        self.assertEqual(tier(r, "focus")[0]["reasons"], ["sensitive path: auth", "promoted: why"])
        r = run(self.DIFF, promote=[("src/app.js", 10, "why"), ("src/app.js", 10, "why")])
        self.assertEqual(tier(r, "focus")[0]["reasons"], ["promoted: why"])

    def test_lockfile_hunk_promoted(self):
        d = moddiff("yarn.lock", hunk(["+a", "+b"], 3), hunk(["-c", "+d"], 40))
        before = run(d)
        self.assertEqual(tier(before, "low")[0]["hunks"], 2)
        r = run(d, promote=[("yarn.lock", 3, "pins new registry")])
        focus = tier(r, "focus")
        self.assertEqual(len(focus), 1)
        self.assertEqual((focus[0]["line"], focus[0]["reasons"]), (3, ["promoted: pins new registry"]))
        low = tier(r, "low")
        self.assertEqual(len(low), 1)
        self.assertEqual((low[0]["hunks"], low[0]["added"], low[0]["removed"]), (1, 1, 1))
        self.assertEqual(low[0]["reasons"], ["lockfile"])
        self.assertEqual(r["summary"]["focus"], {"items": 1, "lines": 2})
        self.assertEqual(r["summary"]["low"], {"items": 1, "lines": 2})
        self.assertEqual(r["summary"]["changed_lines"], 4)

    def test_unknown_exits_2(self):
        with self.assertRaises(T.PromoteError):
            run(self.DIFF, promote=[("src/app.js", 99, "x")])
        p = write_tmp(self, "d.diff", self.DIFF)
        res = cli("--diff", str(p), "--promote", "src/app.js:99=x")
        self.assertEqual(res.returncode, 2)
        self.assertIn("src/app.js:99=x", res.stderr)
        res = cli("--diff", str(p), "--promote", "src/app.js:10=why", "--format", "json")
        self.assertEqual(res.returncode, 0)
        self.assertIn("promoted: why", res.stdout)


# --- T14 -------------------------------------------------------------------

class TestPrevious(unittest.TestCase):
    def test_ticks_carry_over(self):
        d1 = moddiff("src/auth/a.js", hunk(["+x"], 4)) + moddiff("src/auth/b.js", hunk(["+y"], 8))
        md1 = T.render_markdown(run(d1))
        self.assertEqual(md1.count("- [ ] "), 2)
        lines = md1.split("\n")
        i = next(n for n, x in enumerate(lines) if x.startswith("- [ ] `src/auth/a.js"))
        lines[i] = lines[i].replace("- [ ]", "- [x]", 1)
        lines.insert(i + 1, "  check: is it right?")
        prev = "\n".join(lines)
        md2 = T.render_markdown(run(d1), previous=prev)
        self.assertIn("- [x] `src/auth/a.js` L4", md2)
        self.assertIn("- [ ] `src/auth/b.js` L8", md2)
        d2 = moddiff("src/auth/a.js", hunk(["+x", "+x2"], 4)) + moddiff("src/auth/b.js", hunk(["+y"], 8))
        md3 = T.render_markdown(run(d2), previous=prev)
        self.assertIn("- [ ] `src/auth/a.js` L4", md3)
        self.assertNotIn("- [x]", md3)
        prev_big = prev.replace("- [x]", "- [X]")
        self.assertIn("- [x] `src/auth/a.js` L4", T.render_markdown(run(d1), previous=prev_big))

    def test_cli_previous(self):
        d = write_tmp(self, "d.diff", MIXED)
        md = cli("--diff", str(d)).stdout
        prev = write_tmp(self, "prev.md", md.replace("- [ ] `src/auth/session.ts`", "- [x] `src/auth/session.ts`"))
        out = cli("--diff", str(d), "--previous", str(prev)).stdout
        self.assertIn("- [x] `src/auth/session.ts` L42", out)
        self.assertIn("- [ ] `src/old/x.py`", out)


# --- T15 -------------------------------------------------------------------

class TestHtml(unittest.TestCase):
    def test_html_page_embeds_ordered_items_and_diff(self):
        r = cli("--format", "html", stdin=MIXED)
        self.assertEqual(r.returncode, 0)
        self.assertTrue(r.stdout.startswith("<!doctype html>"))
        data = json.loads(re.search(r"const DATA=(.*?);\nconst NAMES", r.stdout, re.S).group(1))
        self.assertEqual([i["tier"] for i in data["items"]],
                         [i["tier"] for i in json.loads(cli("--format", "json", stdin=MIXED).stdout)["items"]])
        self.assertTrue(all(i["_hunks"] for i in data["items"] if i["hunks"]))

    def test_json_has_no_private_keys(self):
        out = json.loads(cli("--format", "json", stdin=MIXED).stdout)
        self.assertFalse(any(k.startswith("_") for i in out["items"] for k in i))

    def test_script_close_tag_in_diff_is_escaped(self):
        d = moddiff("src/a.js", hunk(["+x = '</script><b>'"]))
        self.assertEqual(cli("--format", "html", stdin=d).stdout.count("</script>"), 1)


class TestInputs(unittest.TestCase):
    def test_tty_stdin_prints_usage_instead_of_blocking(self):
        code = ("import sys, runpy; sys.stdin.isatty = lambda: True; "
                "sys.argv = ['triage.py']; runpy.run_path(%r, run_name='__main__')" % str(SCRIPT))
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                           timeout=10)
        self.assertEqual(r.returncode, 2)
        self.assertIn("usage", r.stderr.lower())

    def test_empty(self):
        self.assertEqual(T.parse_diff(""), [])
        res = cli(stdin="")
        self.assertEqual(res.returncode, 0)
        self.assertIn("Nothing to triage: the diff is empty.", res.stdout)
        res = cli("--format", "json", stdin="\n")
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertEqual(data["items"], [])
        self.assertEqual(data["summary"]["files"], 0)
        self.assertEqual(data["summary"]["changed_lines"], 0)
        for t in ("focus", "standard", "low"):
            self.assertEqual(data["summary"][t], {"items": 0, "lines": 0})

    def test_not_a_diff(self):
        with self.assertRaises(T.DiffError):
            T.parse_diff("hello world\nthis is text\n")
        self.assertEqual(cli(stdin="hello world\n").returncode, 2)

    def test_combined_diff(self):
        txt = "diff --cc f.txt\nindex 1,2..3\n--- a/f.txt\n+++ b/f.txt\n@@@ -1,1 -1,1 +1,1 @@@\n+x\n"
        with self.assertRaises(T.DiffError):
            T.parse_diff(txt)
        self.assertEqual(cli(stdin=txt).returncode, 2)
        with self.assertRaises(T.DiffError):
            T.parse_diff(moddiff("a", hunk(["+x"])) + "diff --combined f\n")


# --- T16-T19 ---------------------------------------------------------------

class TestOutput(unittest.TestCase):
    def test_golden_markdown(self):
        res = cli("--diff", str(FIXTURES / "mixed.diff"))
        self.assertEqual(res.returncode, 0, res.stderr)
        expected = (FIXTURES / "mixed.expected.md").read_text(encoding="utf-8")
        self.assertEqual(res.stdout, expected)

    def test_json_consistent(self):
        res = cli("--diff", str(FIXTURES / "mixed.diff"), "--format", "json")
        data = json.loads(res.stdout)
        s = data["summary"]
        self.assertEqual(sum(s[t]["lines"] for t in ("focus", "standard", "low")), s["changed_lines"])
        for t in ("focus", "standard", "low"):
            items = [i for i in data["items"] if i["tier"] == t]
            self.assertEqual(len(items), s[t]["items"])
            self.assertEqual(sum(i["added"] + i["removed"] for i in items), s[t]["lines"])
        first = data["items"][0]
        self.assertEqual(set(first), {"tier", "file", "line", "hunks", "added", "removed", "reasons"})
        self.assertEqual(first["line"], 42)
        rn = [i for i in data["items"] if i.get("old_file")]
        self.assertEqual(rn[0]["old_file"], "src/old/x.py")
        self.assertIsNone(rn[0]["line"])
        std = {i["file"]: i for i in data["items"] if i["tier"] == "standard"}
        self.assertEqual(std["assets/logo.png"]["reasons"], ["binary"])
        self.assertEqual(std["src/lib/cart.ts"]["reasons"], [])
        self.assertEqual(std["src/lib/cart.ts"]["hunks"], 2)

    def test_deterministic(self):
        a = cli("--diff", str(FIXTURES / "mixed.diff"))
        b = cli("--diff", str(FIXTURES / "mixed.diff"))
        self.assertEqual(a.stdout, b.stdout)
        self.assertEqual(T.render_json(run(MIXED)), T.render_json(run(MIXED)))

    def test_cli(self):
        res = cli(stdin=MIXED)
        self.assertEqual(res.returncode, 0)
        self.assertTrue(res.stdout.startswith("<!-- sdd:triage-pr -->\n## Review triage\n"))
        self.assertEqual(res.stdout, (FIXTURES / "mixed.expected.md").read_text(encoding="utf-8"))
        rules = write_tmp(self, "r.json", json.dumps({"focus_paths": ["^src/lib/"]}))
        out = cli("--diff", str(FIXTURES / "mixed.diff"), "--rules", str(rules), "--format", "json")
        self.assertEqual(out.returncode, 0)
        files = [i["file"] for i in json.loads(out.stdout)["items"] if i["tier"] == "focus"]
        self.assertIn("src/lib/cart.ts", files)
        bad = cli("--bogus")
        self.assertEqual(bad.returncode, 2)
        self.assertEqual(cli("--format", "xml", stdin="").returncode, 2)
        self.assertEqual(cli("--diff", str(HERE / "nope.diff")).returncode, 2)


if __name__ == "__main__":
    unittest.main()
