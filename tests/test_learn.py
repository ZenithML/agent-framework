"""Tests for the learn plugin: the learner model, the graders and the content gate."""
import contextlib
import io
import json
import random
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins/learn/scripts"))

import fsrs  # noqa: E402
import gen_logs  # noqa: E402
import grade  # noqa: E402
import learn  # noqa: E402
import model  # noqa: E402
import pack_check  # noqa: E402

PACK = model.load_pack("soc-foundations")
T0 = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)


def _has_sigma():
    try:
        import sigma.backends.sqlite  # noqa: F401
        return True
    except ImportError:
        return shutil.which("uv") is not None


def ev(item, score, minutes=0, **kw):
    return model.make_evidence(PACK, item, score, kw.pop("grader", "choice"),
                               at=(T0 + timedelta(minutes=minutes)).isoformat(), **kw)


def run_cli(home, *argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        learn.main(["--home", str(home), *argv])
    return buf.getvalue()


class FsrsTest(unittest.TestCase):
    def test_good_review_grows_stability_and_again_shrinks_it(self):
        m = fsrs.review(None, fsrs.GOOD, 0)
        later = fsrs.review(m, fsrs.GOOD, m.due_days())
        self.assertGreater(later.stability, m.stability)
        lapse = fsrs.review(later, fsrs.AGAIN, later.due_days())
        self.assertLess(lapse.stability, later.stability)

    def test_retrievability_is_ninety_percent_at_stability(self):
        m = fsrs.review(None, fsrs.GOOD, 0)
        self.assertAlmostEqual(m.retrievability(m.stability), 0.9, places=6)


class ReplayTest(unittest.TestCase):
    def test_replay_is_deterministic_and_order_independent(self):
        log = [ev("logon-1", 1, 0), ev("logon-2", 1, 60), ev("logon-3", 0, 120), ev("sources-1", 1, 5)]
        shuffled = log[:]
        random.Random(4).shuffle(shuffled)
        a, _ = model.replay(PACK, sorted(log, key=lambda e: e["at"]), now=T0 + timedelta(days=1))
        b, _ = model.replay(PACK, sorted(shuffled, key=lambda e: e["at"]), now=T0 + timedelta(days=1))
        self.assertEqual(a, b)

    def test_evidence_is_idempotent_on_its_id(self):
        with tempfile.TemporaryDirectory() as home:
            store = model.Store(home)
            rec = ev("logon-1", 1)
            store.append(rec)
            store.append(rec)
            self.assertEqual(len(store.evidence()), 1)

    def test_repeating_one_item_never_masters_a_concept(self):
        log = [ev("logon-1", 1, m) for m in (0, 60, 120, 180)]
        state, _ = model.replay(PACK, log, now=T0 + timedelta(hours=4))
        self.assertTrue(state["soc.logs.logon"]["transfer"])  # first try was unseen
        log = [ev("logon-1", 1, 0, hints=1)] + [ev("logon-1", 1, m) for m in (60, 120, 180)]
        state, _ = model.replay(PACK, log, now=T0 + timedelta(hours=4))
        self.assertFalse(state["soc.logs.logon"]["transfer"])
        self.assertNotEqual(state["soc.logs.logon"]["status"], "mastered")

    def test_success_on_an_unseen_item_masters_the_concept(self):
        log = [ev("logon-1", 1, 0, hints=1), ev("logon-1", 1, 60), ev("logon-2", 1, 120),
               ev("logon-3", 1, 180)]
        state, _ = model.replay(PACK, log, now=T0 + timedelta(hours=4))
        self.assertEqual(state["soc.logs.logon"]["status"], "mastered")

    def test_self_report_is_capped_and_never_schedules(self):
        rec = ev("logon-1", 1, grader="self", grader_confidence=1.0, kind="self-report")
        self.assertEqual(rec["grader_confidence"], 0.3)
        state, _ = model.replay(PACK, [rec], now=T0)
        self.assertIsNone(state["soc.logs.logon"]["retrievability"])
        self.assertLess(state["soc.logs.logon"]["p_known"], 0.65)

    def test_reveal_makes_an_item_seen(self):
        log = [ev("logon-2", 0, 0, grader="self", kind="reveal"), ev("logon-2", 1, 10)]
        state, seen = model.replay(PACK, log, now=T0)
        self.assertIn("logon-2", seen)
        self.assertFalse(state["soc.logs.logon"]["transfer"])

    def test_mastery_fades_and_comes_due(self):
        log = [ev("logon-1", 1, 0), ev("logon-2", 1, 60), ev("logon-3", 1, 120)]
        soon, _ = model.replay(PACK, log, now=T0 + timedelta(hours=3))
        late, _ = model.replay(PACK, log, now=T0 + timedelta(days=90))
        self.assertEqual(soon["soc.logs.logon"]["status"], "mastered")
        self.assertEqual(late["soc.logs.logon"]["status"], "fading")
        due = [s["concept"] for s in model.due(late, set(PACK["_concepts"]))]
        self.assertIn("soc.logs.logon", due)

    def test_practising_a_concept_credits_its_due_prerequisites(self):
        log = [ev("logon-1", 1, 0)]
        later = 60 * 24 * 30  # a month later the logon memory is due
        log.append(ev("spray-1", 1, later))
        state, _ = model.replay(PACK, log, now=T0 + timedelta(days=30, minutes=1))
        self.assertEqual(state["soc.logs.logon"]["implicit_reviews"], 1)
        self.assertGreater(state["soc.logs.logon"]["retrievability"], 0.95)

    def test_misconception_is_confirmed_then_resolved(self):
        log = [ev("logon-3", 0, 0, error_tag="status-codes-confused"),
               ev("logon-3", 0, 10, error_tag="status-codes-confused")]
        state, _ = model.replay(PACK, log, now=T0)
        self.assertEqual(state["soc.logs.logon"]["misconceptions"]["status-codes-confused"], "confirmed")
        log.append(ev("logon-1", 1, 20))
        state, _ = model.replay(PACK, log, now=T0)
        self.assertEqual(state["soc.logs.logon"]["misconceptions"]["status-codes-confused"], "resolved")


class DiagnoseAndPlanTest(unittest.TestCase):
    def _place(self, answers_correctly):
        with tempfile.TemporaryDirectory() as home:
            run_cli(home, "init", "--pack", "soc-foundations")
            store = model.Store(home)
            n = 0
            while True:
                item = model.diagnose_next(PACK, store)
                if item is None:
                    break
                store.append(model.make_evidence(PACK, item["id"], 1 if answers_correctly else 0,
                                                 "choice", kind="diagnostic"))
                n += 1
                self.assertLessEqual(n, 10)
            state, _ = model.replay(PACK, store.evidence())
            return n, model.frontier(PACK, state, set(PACK["_concepts"])), model.plan(PACK, store)

    def test_an_expert_is_placed_past_the_foundations(self):
        n, front, _ = self._place(True)
        self.assertLessEqual(n, 10)
        self.assertNotIn("soc.logs.sources", front[:1])

    def test_a_novice_starts_at_the_root(self):
        n, front, plan = self._place(False)
        self.assertLessEqual(n, 10)
        self.assertEqual(front, ["soc.logs.sources"])
        self.assertEqual(plan["steps"][0]["concept"], "soc.logs.sources")


class GradeTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.home)

    def test_generator_is_deterministic_and_varies_by_seed(self):
        self.assertEqual(gen_logs.generate("spray", 7), gen_logs.generate("spray", 7))
        self.assertNotEqual(gen_logs.generate("spray", 7)["answers"], gen_logs.generate("spray", 8)["answers"])

    def test_learner_database_holds_no_labels(self):
        db, data = grade.build_dataset(self.home, "beacon", 1)
        con = sqlite3.connect(db)
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        self.assertEqual(tables, ["conn"])
        cols = [r[1] for r in con.execute("PRAGMA table_info(conn)")]
        con.close()
        self.assertEqual(cols, gen_logs.CONN_COLS)

    def test_queries_are_read_only(self):
        db, _ = grade.build_dataset(self.home, "spray", 1)
        for sql in ("DELETE FROM auth", "SELECT 1; DROP TABLE auth", "ATTACH 'x' AS y"):
            with self.assertRaises(grade.GradeError):
                grade.run_query(db, sql)

    def test_over_broad_spray_detection_fails_on_false_positives(self):
        item = PACK["_items"]["spray-2"]
        broad = "SELECT IpAddress FROM auth WHERE EventID = 4625 GROUP BY IpAddress HAVING COUNT(*) > 5"
        res = grade.grade(item, broad, home=self.home, variant=1)
        self.assertFalse(res["correct"])
        self.assertEqual(res["detail"]["recall"], 1.0)
        self.assertGreater(res["detail"]["false_positives"], 0)
        self.assertTrue(grade.grade(item, item["reference"], home=self.home, variant=2)["correct"])

    def test_order_scores_key_constraints(self):
        item = PACK["_items"]["respond-1"]
        self.assertTrue(grade.grade(item, "A, B, E, C, D")["correct"])
        res = grade.grade(item, "D, A, B, C, E")
        self.assertFalse(res["correct"])
        self.assertLess(res["score"], 0.5)

    @unittest.skipUnless(_has_sigma(), "pySigma or uv not available")
    def test_sigma_reference_passes_and_match_all_rule_fails(self):
        item = PACK["_items"]["sigma-2"]
        self.assertTrue(grade.grade(item, item["reference"], home=self.home, variant=1)["correct"])
        broad = ("title: x\nlogsource:\n  category: process_creation\n  product: windows\n"
                 "detection:\n  sel:\n    Image|endswith: '\\powershell.exe'\n  condition: sel\n")
        res = grade.grade(item, broad, home=self.home, variant=1)
        self.assertFalse(res["correct"])
        self.assertGreater(res["detail"]["false_positives"], 0)


class NoLeakTest(unittest.TestCase):
    def test_learner_view_and_feedback_never_show_the_answer(self):
        with tempfile.TemporaryDirectory() as home:
            run_cli(home, "init", "--pack", "soc-foundations")
            for item in PACK["items"]:
                shown = run_cli(home, "item", item["id"], "--variant", "1")
                if "reference" in item:
                    self.assertNotIn(item["reference"], shown, item["id"])
                if item["type"] == "hunt":
                    answer = gen_logs.generate(item["scenario"], 1)["answers"][item["answer_key"]]
                    self.assertNotIn(f" {answer}\n", shown, item["id"])
                self.assertNotIn("TUTOR ONLY", shown)
            out = run_cli(home, "grade", "search-1", "--answer", "10.0.0.1", "--variant", "1")
            truth = gen_logs.generate("spray", 1)["answers"]["attacker_ip"]
            self.assertNotIn(truth, out)
            self.assertIn("TUTOR ONLY", run_cli(home, "item", "search-1", "--tutor"))


class ContentGateTest(unittest.TestCase):
    def test_pack_passes_the_content_gate(self):
        self.assertEqual(pack_check.check(PACK, sigma=_has_sigma()), [])

    def test_gate_catches_a_broken_reference(self):
        broken = json.loads(json.dumps({k: v for k, v in PACK.items() if not k.startswith("_")}))
        broken["items"][0]["answer"] = 9
        broken["_concepts"] = {c["id"]: c for c in broken["concepts"]}
        broken["_items"] = {i["id"]: i for i in broken["items"]}
        self.assertTrue(any("out of range" in p for p in pack_check.check(broken, sigma=False)))


if __name__ == "__main__":
    unittest.main()
