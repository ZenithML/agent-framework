"""Graders. Each takes a pack item and the learner's answer and returns a result
dict with score (0-1), correct, grader and feedback. Feedback never contains the
reference answer or the labels: it says how close the answer was, not what the
answer is.
"""

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import gen_logs

HERE = Path(__file__).resolve().parent
SIGMA_PACKAGES = ["pysigma==2.1.0", "pysigma-backend-sqlite==2.1.1"]
LETTERS = "ABCDEFGH"
MAX_ROWS = 50


class GradeError(Exception):
    pass


# ---------------------------------------------------------------- datasets

def dataset_path(home, scenario, variant):
    return Path(home) / "work" / f"{scenario}-{variant}.db"


def build_dataset(home, scenario, variant):
    """Write the learner-visible tables for (scenario, variant). No labels."""
    path = dataset_path(home, scenario, variant)
    data = gen_logs.generate(scenario, variant)
    if path.exists():
        return path, data
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    for name, table in data["tables"].items():
        cols = table["columns"]
        con.execute(f"CREATE TABLE {name} ({', '.join(cols)})")
        con.executemany(f"INSERT INTO {name} VALUES ({', '.join('?' * len(cols))})", table["rows"])
    con.commit()
    con.close()
    os.replace(tmp, path)
    return path, data


def _readonly(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}

    def auth(action, *_):
        return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

    con.set_authorizer(auth)
    budget = [2_000_000]

    def progress():
        budget[0] -= 1000
        return 1 if budget[0] <= 0 else 0  # abort runaway queries

    con.set_progress_handler(progress, 1000)
    return con


def run_query(path, sql, extra_views=None):
    sql = sql.strip().rstrip(";")
    if ";" in sql:
        raise GradeError("one statement only")
    if not re.match(r"(?is)^\s*(select|with)\b", sql):
        raise GradeError("only SELECT queries are allowed")
    con = _readonly(path)
    try:
        if extra_views:
            con.set_authorizer(None)
            for name, body in extra_views.items():
                con.execute(f"CREATE TEMP VIEW {name} AS {body}")
            con.set_authorizer(lambda a, *_: sqlite3.SQLITE_OK if a in (
                sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION) else sqlite3.SQLITE_DENY)
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description or []]
        return cols, cur.fetchall()
    except sqlite3.Error as exc:
        raise GradeError(f"SQL error: {exc}") from exc
    finally:
        con.close()


def format_rows(cols, rows, limit=MAX_ROWS):
    lines = [" | ".join(cols)]
    for r in rows[:limit]:
        lines.append(" | ".join("" if v is None else str(v) for v in r))
    if len(rows) > limit:
        lines.append(f"... {len(rows) - limit} more rows")
    return "\n".join(lines)


# ---------------------------------------------------------------- graders

def _norm(text):
    text = str(text).strip().lower().strip("'\"`.")
    text = re.sub(r"^corp\\", "", text)
    return re.sub(r"\s+", " ", text)


def grade_choice(item, answer):
    raw = str(answer).strip().upper()
    if raw.isdigit():
        raw = LETTERS[int(raw)] if int(raw) < len(item["options"]) else raw
    letter = raw[:1]
    if letter not in LETTERS[:len(item["options"])]:
        raise GradeError(f"answer with one of {', '.join(LETTERS[:len(item['options'])])}")
    ok = LETTERS.index(letter) == item["answer"]
    return {"score": 1.0 if ok else 0.0, "correct": ok, "grader": "choice",
            "feedback": "Correct." if ok else "Not quite.", "detail": {"chosen": letter},
            "error_tag": None if ok else (item.get("distractor_tags") or {}).get(letter)}


def grade_exact(item, answer, expected=None):
    accepted = [expected] if expected is not None else item["accept"]
    ok = _norm(answer) in {_norm(a) for a in accepted}
    return {"score": 1.0 if ok else 0.0, "correct": ok, "grader": "exact",
            "feedback": "Correct." if ok else "That is not what the data shows.", "detail": {}}


def answers_match(item, given, expected):
    """Exact after normalising; numeric within the item's tolerance when it sets one."""
    if "tolerance" in item:
        try:
            return abs(float(str(given).strip()) - float(expected)) <= item["tolerance"]
        except ValueError:
            return False
    return _norm(given) == _norm(expected)


def grade_hunt(item, answer, data):
    ok = answers_match(item, answer, data["answers"][item["answer_key"]])
    return {"score": 1.0 if ok else 0.0, "correct": ok, "grader": "exact",
            "feedback": "Correct." if ok else "That is not what the data shows.", "detail": {}}


def _detection_score(recall, fp, cap, min_recall):
    score = recall * max(0.0, 1 - 0.25 * max(0, fp - cap))
    ok = recall >= min_recall and fp <= cap
    return round(score, 3), ok


def grade_sql_detect(item, answer, db, data):
    cols, rows = run_query(db, answer)
    if not cols:
        raise GradeError("the query returned no columns")
    flagged = {str(r[0]) for r in rows if r and r[0] is not None}
    mal = set(data["entities"]["malicious"])
    recall = len(flagged & mal) / len(mal)
    fp = len(flagged - mal)
    cap, min_recall = item.get("fp_cap", 0), item.get("min_recall", 1.0)
    score, ok = _detection_score(recall, fp, cap, min_recall)
    feedback = (f"Caught {len(flagged & mal)} of {len(mal)} malicious {item['entity']}; "
                f"{fp} benign {item['entity']} flagged (allowed: {cap}).")
    return {"score": score, "correct": ok, "grader": "sql", "feedback": feedback,
            "detail": {"recall": round(recall, 3), "false_positives": fp}}


def sigma_to_sql(rule_text):
    """Convert with pySigma: in-process when installed, otherwise through uv."""
    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as f:
        f.write(rule_text)
        rule_path = f.name
    try:
        try:
            import sigma.backends.sqlite  # noqa: F401
            cmd = [sys.executable, str(HERE / "sigma_convert.py"), rule_path]
        except ImportError:
            uv = shutil.which("uv")
            if not uv:
                raise GradeError("grading Sigma needs pySigma; install uv (https://docs.astral.sh/uv/) "
                                 "or `pip install " + " ".join(SIGMA_PACKAGES) + "`")
            cmd = [uv, "run", "--no-project", "--quiet"]
            for p in SIGMA_PACKAGES:
                cmd += ["--with", p]
            cmd += ["python", str(HERE / "sigma_convert.py"), rule_path]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        try:
            out = json.loads(proc.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            raise GradeError(f"Sigma conversion failed: {proc.stderr.strip()[-400:]}")
        if "error" in out:
            raise GradeError(f"Sigma rule did not convert: {out['error']}")
        return out
    finally:
        os.unlink(rule_path)


def grade_sigma(item, answer, db, data):
    conv = sigma_to_sql(answer)
    want = item["logsource"]
    got = conv["logsource"]
    if any(want.get(k) and (got.get(k) or "").lower() != want[k] for k in want):
        return {"score": 0.0, "correct": False, "grader": "sigma",
                "feedback": f"The rule's logsource does not match these logs (expected {want}).",
                "detail": {"logsource": got}}
    if len(conv["queries"]) != 1:
        raise GradeError("expected one query from one rule")
    sql = conv["queries"][0]
    table = item["table"]
    cols, rows = run_query(db, sql, extra_views={"logs": f"SELECT * FROM {table}"})
    id_idx = cols.index("id")
    flagged = {r[id_idx] for r in rows}
    mal = set(data["malicious_rows"][table])
    recall = len(flagged & mal) / len(mal)
    fp = len(flagged - mal)
    cap, min_recall = item.get("fp_cap", 0), item.get("min_recall", 1.0)
    score, ok = _detection_score(recall, fp, cap, min_recall)
    feedback = (f"Rule matched {len(flagged)} events: {len(flagged & mal)} of {len(mal)} malicious, "
                f"{fp} benign (allowed: {cap}).")
    return {"score": score, "correct": ok, "grader": "sigma", "feedback": feedback,
            "detail": {"recall": round(recall, 3), "false_positives": fp, "sql": sql}}


def grade_order(item, answer):
    letters = [x for x in re.split(r"[\s,>-]+", str(answer).upper()) if x]
    keys = [s["key"] for s in item["steps"]]
    if sorted(letters) != sorted(keys):
        raise GradeError(f"give every step exactly once, e.g. {', '.join(keys)}")
    pos = {k: i for i, k in enumerate(letters)}
    met = [a for a, b in item["constraints"] if pos[a] < pos[b]]
    score = len(met) / len(item["constraints"])
    ok = score == 1.0
    return {"score": round(score, 3), "correct": ok, "grader": "order",
            "feedback": f"{len(met)} of {len(item['constraints'])} key orderings are right.",
            "detail": {"order": letters}}


def grade(item, answer, home=None, variant=None):
    t = item["type"]
    if t == "choice":
        return grade_choice(item, answer)
    if t == "exact":
        return grade_exact(item, answer)
    if t == "order":
        return grade_order(item, answer)
    db, data = build_dataset(home, item["scenario"], variant)
    if t == "hunt":
        return grade_hunt(item, answer, data)
    if t == "sql-detect":
        return grade_sql_detect(item, answer, db, data)
    if t == "sigma":
        return grade_sigma(item, answer, db, data)
    raise GradeError(f"unknown item type {t!r}")
