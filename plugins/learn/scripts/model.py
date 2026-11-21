"""The learner model: stored records, and the views replayed from them.

Stored (append-only, except goals and preferences, which the learner owns):
  <home>/learner.json     preferences and the installed pack
  <home>/goals.json       goals
  <home>/evidence.jsonl   one graded record per line, idempotent on its id

Derived (recomputed on every call, never stored): per-concept mastery, the
frontier, due reviews and misconceptions. See standards/learner-model.md.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fsrs

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PACKS_DIR = PLUGIN_ROOT / "packs"

# How far each grader can be trusted. AI judgement and self-report never carry
# the weight of an objective check (principle: mastery comes from evidence).
GRADER_CAP = {"exact": 1.0, "choice": 1.0, "sql": 1.0, "sigma": 1.0, "order": 1.0,
              "human": 0.9, "rubric-llm": 0.6, "self": 0.3}
KINDS = {"attempt", "diagnostic", "teach-back", "project", "self-report", "reveal", "exposure"}

# Prerequisites at or above this count as in place for the frontier; one clean
# success (Laplace prior 0.5 -> 0.67) is enough.
P_PLACED = 0.65
P_MASTERED = 0.8
R_KEPT = 0.85      # retrievability below this turns "mastered" into "fading"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
INFERRED = 0.5     # weight of a diagnostic inference on related concepts


def now_utc():
    return datetime.now(timezone.utc)


def to_days(ts):
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    return ts.timestamp() / 86400


def home_dir(explicit=None):
    return Path(explicit or os.environ.get("LEARN_HOME") or ".learn").resolve()


# ---------------------------------------------------------------- packs

def load_pack(pack_id):
    path = PACKS_DIR / pack_id / "pack.json"
    if not path.exists():
        raise SystemExit(f"unknown pack {pack_id!r}; packs: {', '.join(list_packs())}")
    pack = json.loads(path.read_text(encoding="utf-8"))
    pack["_concepts"] = {c["id"]: c for c in pack["concepts"]}
    pack["_items"] = {i["id"]: i for i in pack["items"]}
    return pack


def list_packs():
    return sorted(p.parent.name for p in PACKS_DIR.glob("*/pack.json"))


def topo_order(pack):
    seen, out = set(), []

    def visit(cid, stack=()):
        if cid in stack:
            raise ValueError(f"prerequisite cycle through {cid}")
        if cid in seen:
            return
        for p in pack["_concepts"][cid].get("prereqs", []):
            visit(p, stack + (cid,))
        seen.add(cid)
        out.append(cid)

    for c in pack["concepts"]:
        visit(c["id"])
    return out


def ancestors(pack, cid):
    out, todo = set(), list(pack["_concepts"][cid].get("prereqs", []))
    while todo:
        p = todo.pop()
        if p not in out:
            out.add(p)
            todo.extend(pack["_concepts"][p].get("prereqs", []))
    return out


def descendants(pack, cid):
    return {c for c in pack["_concepts"] if cid in ancestors(pack, c)}


def depth(pack, cid):
    pre = pack["_concepts"][cid].get("prereqs", [])
    return 0 if not pre else 1 + max(depth(pack, p) for p in pre)


def primary_concept(item):
    return next(c for c, w in item["concepts"].items() if w >= 1)


# ---------------------------------------------------------------- store

class Store:
    def __init__(self, home):
        self.home = Path(home)

    @property
    def exists(self):
        return (self.home / "learner.json").exists()

    def learner(self):
        if not self.exists:
            raise SystemExit(f"no learner at {self.home}; run `learn.py init --pack <pack>` first")
        return json.loads((self.home / "learner.json").read_text(encoding="utf-8"))

    def save_learner(self, data):
        self.home.mkdir(parents=True, exist_ok=True)
        (self.home / "learner.json").write_text(json.dumps(data, indent=2) + "\n",
                                                encoding="utf-8")

    def goals(self):
        p = self.home / "goals.json"
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

    def save_goals(self, goals):
        (self.home / "goals.json").write_text(json.dumps(goals, indent=2) + "\n",
                                              encoding="utf-8")

    def evidence(self):
        p = self.home / "evidence.jsonl"
        if not p.exists():
            return []
        seen, out = set(), []
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            if e["id"] in seen:  # idempotent: a re-sent record counts once
                continue
            seen.add(e["id"])
            out.append(e)
        out.sort(key=lambda e: e["at"])
        return out

    def append(self, record):
        self.home.mkdir(parents=True, exist_ok=True)
        with open(self.home / "evidence.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True) + "\n")


def make_evidence(pack, item_id, score, grader, kind="attempt", hints=0, grader_confidence=None,
                  seconds=None, confidence_before=None, error_tag=None, variant=None,
                  session=None, skill=None, detail=None, at=None, evidence_id=None):
    if kind not in KINDS:
        raise SystemExit(f"kind must be one of {sorted(KINDS)}")
    if grader not in GRADER_CAP:
        raise SystemExit(f"grader must be one of {sorted(GRADER_CAP)}")
    item = pack["_items"].get(item_id)
    if item is None:
        raise SystemExit(f"unknown item {item_id!r}")
    if not 0 <= float(score) <= 1:
        raise SystemExit("score must be between 0 and 1")
    cap = GRADER_CAP[grader]
    conf = cap if grader_confidence is None else min(float(grader_confidence), cap)
    return {
        "id": evidence_id or str(uuid.uuid4()),
        "at": at or now_utc().isoformat(timespec="seconds"),
        "item": item_id,
        "variant": variant,
        "concepts": item["concepts"],
        "kind": kind,
        "score": round(float(score), 3),
        "grader": grader,
        "grader_confidence": conf,
        "hints": int(hints),
        "seconds": seconds,
        "confidence_before": confidence_before,
        "error_tag": error_tag,
        "session": session,
        "skill": skill,
        "detail": detail or {},
    }


# ---------------------------------------------------------------- replay

def _grade_from(score, hints):
    if score >= 0.9 and hints == 0:
        return fsrs.GOOD
    if score >= 0.6:
        return fsrs.HARD
    return fsrs.AGAIN


def replay(pack, evidence, now=None):
    """Fold the evidence log into per-concept state. Pure: same log, same result."""
    now_d = to_days(now or now_utc())
    st = {cid: {"succ": 0.0, "fail": 0.0, "n_direct": 0, "memory": None, "transfer": False,
                "implicit": 0, "suspect_prereqs": 0, "errors": {}, "last_success": None}
          for cid in pack["_concepts"]}
    seen_items = set()

    for e in evidence:
        item = pack["_items"].get(e["item"])
        if item is None or e["kind"] == "exposure":
            continue
        if e["kind"] == "reveal":
            seen_items.add(e["item"])
            continue
        t = to_days(e["at"])
        score, hints = float(e["score"]), int(e.get("hints") or 0)
        conf = min(float(e.get("grader_confidence") or 0), GRADER_CAP.get(e["grader"], 0))
        hint_factor = max(0.25, 1 - 0.25 * hints)
        unseen = e["item"] not in seen_items

        for cid, wc in e["concepts"].items():
            if cid not in st:
                continue
            s = st[cid]
            w = wc * conf * hint_factor
            s["succ"] += w * score
            s["fail"] += w * (1 - score)
            if wc < 1:
                continue
            s["n_direct"] += 1
            if conf >= 0.6:  # self-report never moves the schedule
                s["memory"] = fsrs.review(s["memory"], _grade_from(score, hints), t)
            if score >= 0.8:
                s["last_success"] = e["at"]
                if hints == 0 and unseen and e["kind"] in ("attempt", "diagnostic", "project"):
                    s["transfer"] = True
                # Partial credit downward: practising a concept exercises its prerequisites.
                for p in pack["_concepts"][cid].get("prereqs", []):
                    pm = st[p]["memory"]
                    if pm is not None and pm.retrievability(t) < 0.9:
                        st[p]["memory"] = fsrs.review(pm, fsrs.GOOD, t)
                        st[p]["implicit"] += 1
            elif score < 0.5:
                for p in pack["_concepts"][cid].get("prereqs", []):
                    st[p]["suspect_prereqs"] += 1
            if e.get("error_tag"):
                err = s["errors"].setdefault(e["error_tag"], {"count": 0, "last": None})
                err["count"] += 1
                err["last"] = e["at"]

            if e["kind"] == "diagnostic":  # placement inference, weaker than direct evidence
                if score >= 0.8:
                    for a in ancestors(pack, cid):
                        st[a]["succ"] += INFERRED
                elif score < 0.5:
                    for d in descendants(pack, cid):
                        st[d]["fail"] += INFERRED
        seen_items.add(e["item"])

    out = {}
    for cid, s in st.items():
        p_known = (1 + s["succ"]) / (2 + s["succ"] + s["fail"])
        mem = s["memory"]
        r = mem.retrievability(now_d) if mem else None
        criteria = p_known >= P_MASTERED and s["n_direct"] >= 2 and s["transfer"]
        if s["n_direct"] == 0 and s["succ"] + s["fail"] == 0:
            status = "new"
        elif criteria and r is not None and r >= R_KEPT:
            status = "mastered"
        elif criteria:
            status = "fading"
        else:
            status = "learning"
        misconceptions = {}
        for tag, err in s["errors"].items():
            resolved = s["last_success"] is not None and s["last_success"] > err["last"]
            misconceptions[tag] = ("resolved" if resolved else
                                   "confirmed" if err["count"] >= 2 else "suspected")
        out[cid] = {
            "concept": cid,
            "title": pack["_concepts"][cid]["title"],
            "status": status,
            "p_known": round(p_known, 3),
            "n_direct": s["n_direct"],
            "transfer": s["transfer"],
            "retrievability": None if r is None else round(r, 3),
            "stability_days": None if mem is None else round(mem.stability, 2),
            "due_at": None if mem is None else (EPOCH + timedelta(days=mem.due_days())).isoformat(
                timespec="minutes"),
            "implicit_reviews": s["implicit"],
            "check_prereqs": s["suspect_prereqs"] >= 2,
            "misconceptions": misconceptions,
        }
    return out, seen_items


def scope(pack, goals):
    """Concepts in play: every active goal's concepts and their prerequisites."""
    active = [g for g in goals if g.get("status", "active") == "active"]
    if not active:
        return set(pack["_concepts"])
    out = set()
    for g in active:
        for c in g["concepts"]:
            out |= {c} | ancestors(pack, c)
    return out


def frontier(pack, state, in_scope):
    out = []
    for cid in topo_order(pack):
        if cid not in in_scope or state[cid]["status"] in ("mastered", "fading"):
            continue
        if state[cid]["p_known"] >= P_MASTERED:  # probably known already: confirm, don't teach
            continue
        if all(state[p]["p_known"] >= P_PLACED for p in pack["_concepts"][cid].get("prereqs", [])):
            out.append(cid)
    return out


def due(state, in_scope, desired_retention=0.9):
    rows = [s for c, s in state.items() if c in in_scope and s["retrievability"] is not None
            and s["retrievability"] < desired_retention]
    return sorted(rows, key=lambda s: s["retrievability"])


def attempts_by_item(evidence):
    out = {}
    for e in evidence:
        if e["kind"] in ("attempt", "diagnostic", "project", "teach-back"):
            out.setdefault(e["item"], []).append(e)
    return out


def pick_item(pack, cid, seen_items, evidence, prefer=("choice", "exact", "hunt", "order",
                                                      "sql-detect", "sigma")):
    """An item for a concept: unseen first, easiest first; else the least recently tried."""
    items = [i for i in pack["items"] if primary_concept(i) == cid]
    unseen = [i for i in items if i["id"] not in seen_items]
    if unseen:
        return sorted(unseen, key=lambda i: (i.get("difficulty", 1), prefer.index(i["type"])))[0]
    last = {i["id"]: max((e["at"] for e in evidence if e["item"] == i["id"]), default="")
            for i in items}
    return sorted(items, key=lambda i: last[i["id"]])[0] if items else None


def plan(pack, store, minutes=None, now=None):
    learner = store.learner()
    minutes = minutes or learner.get("prefs", {}).get("session_minutes", 30)
    evidence = store.evidence()
    state, seen = replay(pack, evidence, now)
    in_scope = scope(pack, store.goals())
    retention = learner.get("prefs", {}).get("desired_retention", 0.9)
    reviews = [s["concept"] for s in due(state, in_scope, retention)]
    new = [c for c in frontier(pack, state, in_scope) if c not in reviews]
    # Probably known (from placement or practice) but not yet shown on an unseen item.
    confirm = [c for c in topo_order(pack) if c in in_scope and c not in reviews
               and state[c]["status"] == "learning" and state[c]["p_known"] >= P_MASTERED]
    # Due reviews first, interleaved with new concepts, then confirmations, within the budget.
    steps, used = [], 0
    while True:
        took = False
        for queue, kind, cost in ((reviews, "review", 4), (new, "learn", 12), (confirm, "confirm", 4)):
            if queue and used + cost <= minutes:
                cid = queue.pop(0)
                item = pick_item(pack, cid, seen, evidence)
                steps.append({"kind": kind, "concept": cid, "title": pack["_concepts"][cid]["title"],
                              "item": item["id"] if item else None, "minutes": cost})
                used += cost
                took = True
        if not took:
            break
    return {"minutes": minutes, "steps": steps}


def diagnose_next(pack, store, limit=10):
    evidence = store.evidence()
    diag = [e for e in evidence if e["kind"] == "diagnostic"]
    if len(diag) >= limit:
        return None
    state, seen = replay(pack, evidence)
    in_scope = scope(pack, store.goals())
    uncertain = [c for c in topo_order(pack) if c in in_scope and state[c]["n_direct"] == 0
                 and 0.3 <= state[c]["p_known"] <= 0.7]
    if not uncertain:
        return None
    uncertain.sort(key=lambda c: depth(pack, c))
    cid = uncertain[len(uncertain) // 2]  # probe the middle of what is still unknown
    return pick_item(pack, cid, seen, evidence, prefer=("choice", "exact", "hunt", "order",
                                                        "sql-detect", "sigma"))
