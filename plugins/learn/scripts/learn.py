#!/usr/bin/env python3
"""learn.py: the learn plugin's command line. Python standard library only
(Sigma grading runs pySigma through uv; see sigma_convert.py).

State lives in $LEARN_HOME, or ./.learn when unset. Run `learn.py --help`.
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import grade as grading  # noqa: E402
import model  # noqa: E402

DATA_TYPES = {"hunt", "sql-detect", "sigma"}


def _store(args):
    return model.Store(model.home_dir(args.home))


def _pack(store, args=None):
    pack_id = getattr(args, "pack", None) or store.learner()["pack"]
    return model.load_pack(pack_id)


def _out(args, obj, text):
    print(json.dumps(obj, indent=2) if getattr(args, "json", False) else text)


def _next_variant(evidence, item_id):
    """Retries stay on the same dataset; a success or a reveal moves the item to fresh data."""
    return 1 + sum(1 for e in evidence if e["item"] == item_id
                   and (e["kind"] == "reveal" or (e["kind"] != "exposure" and e["score"] >= 0.8)))


# ---------------------------------------------------------------- commands

def cmd_init(args):
    store = _store(args)
    model.load_pack(args.pack)
    data = store.learner() if store.exists else {"created": model.now_utc().isoformat(timespec="seconds")}
    data["pack"] = args.pack
    prefs = data.setdefault("prefs", {})
    prefs["session_minutes"] = args.session_minutes
    prefs["weekly_minutes"] = args.weekly_minutes
    prefs["desired_retention"] = args.retention
    store.save_learner(data)
    print(f"Learner ready at {store.home} with pack {args.pack}.")


def cmd_goal(args):
    store = _store(args)
    pack = _pack(store)
    goals = store.goals()
    if args.action == "list":
        _out(args, goals, "\n".join(f"- {g['statement']} (by {g.get('target_date') or 'no date'}, "
                                    f"{len(g['concepts'])} concepts, {g['status']})" for g in goals)
             or "No goals yet.")
        return
    concepts = list(pack["_concepts"]) if args.concepts in (None, "all") else args.concepts.split(",")
    unknown = [c for c in concepts if c not in pack["_concepts"]]
    if unknown:
        raise SystemExit(f"unknown concepts: {', '.join(unknown)}")
    if args.target_date:
        date.fromisoformat(args.target_date)
    for g in goals:
        if g["status"] == "active" and args.replace:
            g["status"] = "replaced"
    goals.append({"id": f"g{len(goals) + 1}", "statement": args.statement, "concepts": concepts,
                  "target_date": args.target_date, "why": args.why, "success_test": args.success_test,
                  "status": "active", "created": model.now_utc().isoformat(timespec="seconds")})
    store.save_goals(goals)
    print(f"Goal saved: {args.statement} ({len(concepts)} concepts).")


def cmd_status(args):
    store = _store(args)
    pack = _pack(store)
    evidence = store.evidence()
    state, _ = model.replay(pack, evidence)
    in_scope = model.scope(pack, store.goals())
    rows = [state[c] for c in model.topo_order(pack) if c in in_scope]
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in ("mastered", "fading", "learning", "new")}
    lines = [f"{counts['mastered']} kept, {counts['fading']} fading, {counts['learning']} learning, "
             f"{counts['new']} not started ({len(evidence)} evidence records)", ""]
    for r in rows:
        rr = "-" if r["retrievability"] is None else f"{r['retrievability']:.2f}"
        flags = []
        if r["check_prereqs"]:
            flags.append("check prerequisites")
        flags += [f"misconception {t}: {s}" for t, s in r["misconceptions"].items() if s != "resolved"]
        lines.append(f"{r['status']:9} P(known) {r['p_known']:.2f}  recall {rr:>4}  {r['concept']}  "
                     f"{r['title']}" + (f"  [{'; '.join(flags)}]" if flags else ""))
    _out(args, {"counts": counts, "concepts": rows}, "\n".join(lines))


def cmd_plan(args):
    store = _store(args)
    pack = _pack(store)
    p = model.plan(pack, store, minutes=args.minutes)
    lines = [f"Session plan, about {sum(s['minutes'] for s in p['steps'])} of {p['minutes']} minutes:"]
    for i, s in enumerate(p["steps"], 1):
        lines.append(f"{i}. {s['kind']:6} {s['concept']} ({s['title']}): item {s['item']}")
    if not p["steps"]:
        lines.append("Nothing due and no new concept is ready. Check `status`, or set a wider goal.")
    _out(args, p, "\n".join(lines))


def cmd_diagnose(args):
    store = _store(args)
    pack = _pack(store)
    item = model.diagnose_next(pack, store, limit=args.limit)
    if item is None:
        _out(args, {"done": True}, "Placement done. Run `status` to see the frontier.")
    else:
        _out(args, {"done": False, "item": item["id"]}, f"Next placement item: {item['id']}")


def _schema_text(db):
    cols, rows = grading.run_query(db, "SELECT name, sql FROM sqlite_master WHERE type = 'table'")
    out = []
    for name, _ in rows:
        c, n = grading.run_query(db, f"SELECT COUNT(*) FROM {name}")
        pc, _ = grading.run_query(db, f"SELECT * FROM {name} LIMIT 0")
        out.append(f"table {name} ({n[0][0]} rows): {', '.join(pc)}")
    return "\n".join(out)


def cmd_item(args):
    store = _store(args)
    pack = _pack(store)
    item = pack["_items"].get(args.item_id)
    if item is None:
        raise SystemExit(f"unknown item {args.item_id!r}")
    evidence = store.evidence()
    variant = args.variant or _next_variant(evidence, item["id"])
    lines = [f"Item {item['id']} ({item['type']}, concept {model.primary_concept(item)}, variant {variant})",
             "", item["prompt"]]
    if item["type"] == "choice":
        lines += [""] + [f"{grading.LETTERS[i]}. {o}" for i, o in enumerate(item["options"])]
        lines.append("\nAnswer with one letter.")
    if item["type"] == "order":
        lines += [""] + [f"{s['key']}. {s['text']}" for s in item["steps"]]
    if item["type"] in DATA_TYPES:
        db, data = grading.build_dataset(store.home, item["scenario"], variant)
        lines += ["", f"Database: {db}", _schema_text(db),
                  f"Explore with: learn.py query --item {item['id']} --variant {variant} \"SELECT ...\""]
        if item["type"] == "sigma":
            lines.append("Answer with a Sigma rule in YAML (save it to a file and pass --answer-file).")
    if args.tutor:
        lines += ["", "=== TUTOR ONLY: do not show the learner ===",
                  "Hint ladder: " + " | ".join(f"{i}. {h}" for i, h in enumerate(item.get("hints", []), 1))]
        if item["type"] == "choice":
            lines.append(f"Answer: {grading.LETTERS[item['answer']]}")
        if "reference" in item:
            lines.append("Reference:\n" + item["reference"])
        if item["type"] in DATA_TYPES:
            lines.append("Ground truth for this variant: " + json.dumps(
                {k: data[k] for k in ("answers", "entities")}))
        lines.append("Why: " + item.get("explanation", ""))
    print("\n".join(lines))


def cmd_query(args):
    store = _store(args)
    if args.db:
        db = Path(args.db)
    else:
        pack = _pack(store)
        item = pack["_items"][args.item]
        variant = args.variant or _next_variant(store.evidence(), item["id"])
        db, _ = grading.build_dataset(store.home, item["scenario"], variant)
    try:
        cols, rows = grading.run_query(db, args.sql)
    except grading.GradeError as exc:
        raise SystemExit(str(exc))
    print(grading.format_rows(cols, rows))


def _answer(args):
    if args.answer_file:
        return Path(args.answer_file).read_text()
    if args.answer is None:
        raise SystemExit("give --answer or --answer-file")
    return args.answer


def cmd_grade(args):
    store = _store(args)
    pack = _pack(store)
    item = pack["_items"].get(args.item_id)
    if item is None:
        raise SystemExit(f"unknown item {args.item_id!r}")
    evidence = store.evidence()
    variant = args.variant or _next_variant(evidence, item["id"])
    try:
        result = grading.grade(item, _answer(args), home=store.home, variant=variant)
    except grading.GradeError as exc:
        # A malformed answer is feedback, not evidence: nothing is recorded.
        _out(args, {"recorded": False, "error": str(exc)}, f"Not graded: {exc}")
        return
    rec = model.make_evidence(pack, item["id"], result["score"], result["grader"], kind=args.kind,
                              hints=args.hints, seconds=args.seconds,
                              confidence_before=args.confidence, error_tag=result.get("error_tag"),
                              variant=variant, session=args.session, skill=args.skill,
                              detail=result.get("detail"))
    store.append(rec)
    text = f"{'Correct' if result['correct'] else 'Not yet'} (score {result['score']:.2f})."
    if result["feedback"] not in ("Correct.", ""):
        text += f" {result['feedback']}"
    if result["correct"] and item.get("explanation"):
        text += f"\nWhy: {item['explanation']}"
    _out(args, {"recorded": True, "evidence_id": rec["id"], **result}, text)


def cmd_record(args):
    store = _store(args)
    pack = _pack(store)
    rec = model.make_evidence(pack, args.item_id, args.score, args.grader, kind=args.kind,
                              hints=args.hints, grader_confidence=args.grader_confidence,
                              confidence_before=args.confidence, error_tag=args.error_tag,
                              session=args.session, skill=args.skill,
                              detail={"note": args.note} if args.note else None)
    store.append(rec)
    print(f"Recorded {rec['kind']} on {rec['item']}: score {rec['score']}, "
          f"grader {rec['grader']} (confidence {rec['grader_confidence']}).")


def cmd_reveal(args):
    store = _store(args)
    pack = _pack(store)
    item = pack["_items"][args.item_id]
    rec = model.make_evidence(pack, item["id"], 0, "self", kind="reveal", skill=args.skill)
    store.append(rec)
    lines = [f"Revealed {item['id']}. It no longer counts as an unseen item for this learner."]
    if item["type"] == "choice":
        lines.append(f"Answer: {grading.LETTERS[item['answer']]}. {item['options'][item['answer']]}")
    if "reference" in item:
        lines.append(item["reference"])
    lines.append(item.get("explanation", ""))
    print("\n".join(lines))


def cmd_report(args):
    store = _store(args)
    pack = _pack(store)
    state, _ = model.replay(pack, store.evidence())
    goals = [g for g in store.goals() if g["status"] == "active"]
    lines = []
    for g in goals or [{"statement": "Whole pack", "concepts": list(pack["_concepts"]), "target_date": None}]:
        cs = [state[c] for c in g["concepts"]]
        kept = [c for c in cs if c["status"] == "mastered"]
        fading = [c for c in cs if c["status"] == "fading"]
        lines.append(f"{g['statement']}: {len(kept)} of {len(cs)} concepts kept"
                     + (f", {len(fading)} fading" if fading else "")
                     + (f", target {g['target_date']}" if g.get("target_date") else ""))
        if fading:
            lines.append("  Review soon: " + ", ".join(c["title"] for c in fading))
    in_scope = model.scope(pack, store.goals())
    nxt = model.frontier(pack, state, in_scope)[:3]
    if nxt:
        lines.append("Next up: " + ", ".join(pack["_concepts"][c]["title"] for c in nxt))
    print("\n".join(lines))


def cmd_pack(args):
    if args.action == "list":
        for p in model.list_packs():
            pk = model.load_pack(p)
            print(f"{p}: {pk['title']} ({len(pk['concepts'])} concepts, {len(pk['items'])} items)")
        return
    import pack_check
    problems = pack_check.check(model.load_pack(args.pack_id), sigma=not args.no_sigma)
    if problems:
        print("\n".join(f"FAIL {p}" for p in problems))
        raise SystemExit(1)
    print(f"Pack {args.pack_id} passes the content gate.")


# ---------------------------------------------------------------- parser

def build_parser():
    ap = argparse.ArgumentParser(prog="learn.py", description=__doc__.split("\n")[0])
    ap.add_argument("--home", help="learner directory (default $LEARN_HOME or ./.learn)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create or update the learner")
    p.add_argument("--pack", required=True)
    p.add_argument("--session-minutes", type=int, default=30)
    p.add_argument("--weekly-minutes", type=int, default=150)
    p.add_argument("--retention", type=float, default=0.9)
    p.set_defaults(fn=cmd_init)

    p = sub.add_parser("goal", help="set or list goals")
    p.add_argument("action", choices=["set", "list"])
    p.add_argument("--statement")
    p.add_argument("--concepts", help="comma-separated concept ids, or 'all'")
    p.add_argument("--target-date")
    p.add_argument("--why")
    p.add_argument("--success-test")
    p.add_argument("--replace", action="store_true", help="retire the current active goals")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_goal)

    for name, fn, hlp in (("status", cmd_status, "mastery per concept, replayed from evidence"),
                          ("report", cmd_report, "honest progress against goals")):
        p = sub.add_parser(name, help=hlp)
        p.add_argument("--json", action="store_true")
        p.set_defaults(fn=fn)

    p = sub.add_parser("plan", help="the next session: due reviews, then frontier concepts")
    p.add_argument("--minutes", type=int)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("diagnose", help="the next placement item, or done")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_diagnose)

    p = sub.add_parser("item", help="show an item (add --tutor for the hint ladder and reference)")
    p.add_argument("item_id")
    p.add_argument("--variant", type=int)
    p.add_argument("--tutor", action="store_true")
    p.set_defaults(fn=cmd_item)

    p = sub.add_parser("query", help="run a read-only SELECT against an item's dataset")
    p.add_argument("sql")
    p.add_argument("--item")
    p.add_argument("--variant", type=int)
    p.add_argument("--db")
    p.set_defaults(fn=cmd_query)

    p = sub.add_parser("grade", help="grade an answer objectively and record the evidence")
    p.add_argument("item_id")
    p.add_argument("--answer")
    p.add_argument("--answer-file")
    p.add_argument("--variant", type=int)
    p.add_argument("--kind", default="attempt", choices=["attempt", "diagnostic", "project"])
    p.add_argument("--hints", type=int, default=0)
    p.add_argument("--confidence", type=float, help="learner's confidence before answering, 0-1")
    p.add_argument("--seconds", type=int)
    p.add_argument("--session")
    p.add_argument("--skill")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_grade)

    p = sub.add_parser("record", help="record evidence graded outside learn.py (rubric, human, self)")
    p.add_argument("item_id")
    p.add_argument("--score", type=float, required=True)
    p.add_argument("--grader", required=True, choices=["rubric-llm", "human", "self"])
    p.add_argument("--kind", default="attempt", choices=sorted(model.KINDS - {"reveal"}))
    p.add_argument("--grader-confidence", type=float)
    p.add_argument("--hints", type=int, default=0)
    p.add_argument("--confidence", type=float)
    p.add_argument("--error-tag")
    p.add_argument("--note")
    p.add_argument("--session")
    p.add_argument("--skill")
    p.set_defaults(fn=cmd_record)

    p = sub.add_parser("reveal", help="show the answer; logged, and the item stops counting as unseen")
    p.add_argument("item_id")
    p.add_argument("--skill")
    p.set_defaults(fn=cmd_reveal)

    p = sub.add_parser("pack", help="list packs, or run the content gate on one")
    p.add_argument("action", choices=["list", "check"])
    p.add_argument("pack_id", nargs="?")
    p.add_argument("--no-sigma", action="store_true", help="skip Sigma references (no uv available)")
    p.set_defaults(fn=cmd_pack)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "goal" and args.action == "set" and not args.statement:
        raise SystemExit("goal set needs --statement")
    if args.cmd == "pack" and args.action == "check" and not args.pack_id:
        raise SystemExit("pack check needs a pack id")
    args.fn(args)


if __name__ == "__main__":
    main()
