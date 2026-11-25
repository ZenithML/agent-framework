"""Convert one Sigma rule to SQLite SQL with SigmaHQ's pySigma and SQLite backend.

This is the only part of the learn plugin that needs packages outside the
Python standard library. grade.py runs it through `uv`, so nothing is
installed globally:

  uv run --no-project --with pysigma --with pysigma-backend-sqlite python sigma_convert.py RULE.yml

Prints JSON: {"queries": [...], "logsource": {...}} or {"error": "..."}.
"""

import json
import sys


def main():
    text = open(sys.argv[1], encoding="utf-8").read()
    try:
        from sigma.backends.sqlite import sqliteBackend
        from sigma.collection import SigmaCollection
    except ImportError as exc:
        print(json.dumps({"error": f"pySigma is not installed: {exc}"}))
        return 2
    try:
        coll = SigmaCollection.from_yaml(text)
        rules = list(coll.rules)
        if len(rules) != 1:
            raise ValueError(f"expected exactly one rule, found {len(rules)}")
        ls = rules[0].logsource
        queries = sqliteBackend().convert(coll)
    except Exception as exc:  # pySigma raises many types; the learner needs the message
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        return 1
    print(json.dumps({"queries": queries,
                      "logsource": {"category": ls.category, "product": ls.product,
                                    "service": ls.service}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
