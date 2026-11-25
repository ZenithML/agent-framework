"""Content gate for a subject pack: structure, then every item against its own
reference answer, on several generated variants. Returns a list of problems."""

import tempfile

import gen_logs
import grade as grading
import model

TYPES = {"choice", "exact", "hunt", "order", "sql-detect", "sigma"}
VARIANTS = (1, 2, 3)


def check(pack, sigma=True):
    problems = []
    concepts = pack["_concepts"]
    try:
        model.topo_order(pack)
    except ValueError as exc:
        problems.append(str(exc))
    for c in pack["concepts"]:
        for p in c.get("prereqs", []):
            if p not in concepts:
                problems.append(f"{c['id']}: unknown prerequisite {p}")
        if not c.get("can_do"):
            problems.append(f"{c['id']}: no can-do statement")
        primary = [i for i in pack["items"] if i["concepts"].get(c["id"], 0) >= 1]
        if len(primary) < 2:
            problems.append(f"{c['id']}: needs at least 2 items so mastery can include an unseen one "
                            f"(has {len(primary)})")

    ids = set()
    for item in pack["items"]:
        iid = item.get("id", "?")
        if iid in ids:
            problems.append(f"{iid}: duplicate item id")
        ids.add(iid)
        if item.get("type") not in TYPES:
            problems.append(f"{iid}: unknown type {item.get('type')}")
            continue
        if sum(1 for w in item["concepts"].values() if w >= 1) != 1:
            problems.append(f"{iid}: needs exactly one primary concept (weight 1)")
        for c in item["concepts"]:
            if c not in concepts:
                problems.append(f"{iid}: unknown concept {c}")
        if len(item.get("hints", [])) < 2:
            problems.append(f"{iid}: needs a hint ladder of at least 2 hints")
        if not item.get("explanation"):
            problems.append(f"{iid}: no explanation")
        problems += _check_reference(item, sigma)
    return problems


def _check_reference(item, sigma):
    iid, t = item["id"], item["type"]
    out = []
    if t == "choice":
        if not 0 <= item["answer"] < len(item["options"]):
            out.append(f"{iid}: answer index out of range")
        return out
    if t == "exact":
        if not item.get("accept"):
            out.append(f"{iid}: no accepted answers")
        return out
    if t == "order":
        keys = {s["key"] for s in item["steps"]}
        if any(a not in keys or b not in keys for a, b in item["constraints"]):
            out.append(f"{iid}: constraint names an unknown step")
        return out
    if t == "sigma" and not sigma:
        return out
    with tempfile.TemporaryDirectory() as home:
        for v in VARIANTS:
            try:
                if t == "hunt":
                    data = gen_logs.generate(item["scenario"], v)
                    if item["answer_key"] not in data["answers"]:
                        out.append(f"{iid}: scenario has no answer {item['answer_key']}")
                        break
                    db, data = grading.build_dataset(home, item["scenario"], v)
                    cols, rows = grading.run_query(db, item["reference"])
                    got = rows[0][0] if rows else None
                    if got is None or not grading.answers_match(item, got, data["answers"][item["answer_key"]]):
                        out.append(f"{iid} variant {v}: reference query gives {got!r}, "
                                   f"not the scenario's answer")
                else:
                    res = grading.grade(item, item["reference"], home=home, variant=v)
                    if not res["correct"]:
                        out.append(f"{iid} variant {v}: reference answer fails its own grader "
                                   f"({res['feedback']})")
            except grading.GradeError as exc:
                out.append(f"{iid} variant {v}: {exc}")
    return out
