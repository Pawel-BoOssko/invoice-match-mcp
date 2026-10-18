"""Eval runner: scores the engine against golden cases and prints a table.

    python evals/run_evals.py            # deterministic engine, exit code 1 on any miss
    python evals/run_evals.py --json     # machine-readable

The same golden cases can score an LLM agent: feed each invoice to the model with
the MCP server attached and compare its final answer with `expect`. Keep the
cases in one file so engine, tools and agent are all graded against one truth.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from invoice_match.engine import load_po_lines, match_invoice  # noqa: E402


def run() -> list[dict]:
    pos = load_po_lines(ROOT / "data" / "purchase_orders.csv")
    cases = json.loads((ROOT / "evals" / "golden_cases.json").read_text(encoding="utf-8"))
    results = []
    for c in cases:
        got = match_invoice(c["invoice"], pos).status
        results.append({"id": c["id"], "expect": c["expect"], "got": got, "ok": got == c["expect"]})
    return results


def main() -> int:
    results = run()
    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
    else:
        for r in results:
            print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['id']:<34} expect={r['expect']:<14} got={r['got']}")
        passed = sum(r["ok"] for r in results)
        print(f"\n{passed}/{len(results)} passed")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())