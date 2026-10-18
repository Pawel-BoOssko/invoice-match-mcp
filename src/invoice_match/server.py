"""MCP server exposing the matching engine to an AI model.

Run:  python -m invoice_match.server        (stdio transport)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from .engine import PRICE_TOLERANCE, load_po_lines, match_invoice

DATA = Path(os.environ.get("INVOICE_MATCH_PO_FILE", Path(__file__).resolve().parents[2] / "data" / "purchase_orders.csv"))

mcp = MCPServer("invoice-match")
_seen: set[tuple[str, str]] = set()


@mcp.tool()
def list_open_purchase_orders(supplier: str) -> list[dict]:
    """List PO lines for a supplier, with ordered/received quantities and agreed unit price."""
    return [
        {
            "po_number": p.po_number, "sku": p.sku, "qty_ordered": str(p.qty_ordered),
            "qty_received": str(p.qty_received), "unit_price": str(p.unit_price), "currency": p.currency,
        }
        for p in load_po_lines(DATA) if p.supplier == supplier
    ]


@mcp.tool()
def check_invoice(invoice_json: str, register: bool = False) -> dict:
    """Three-way match one invoice against the PO file.

    invoice_json: {"invoice_number": str, "supplier": str, "po_number": str|null,
                   "currency": "EUR", "lines": [{"sku": str, "qty": number, "unit_price": number}]}
    register: if true and the decision is APPROVE, remember the invoice so a resubmission is flagged as a duplicate.
    Returns status (APPROVE, HOLD_*, REVIEW), reasons and the PO used. It never pays or posts anything.
    """
    invoice = json.loads(invoice_json)
    decision = match_invoice(invoice, load_po_lines(DATA), _seen)
    if register and decision.status == "APPROVE":
        _seen.add((invoice["supplier"], invoice["invoice_number"]))
    return decision.to_dict()


@mcp.resource("policy://matching")
def matching_policy() -> str:
    """The matching policy the engine enforces."""
    return (
        f"Unit price may differ from the PO by at most {PRICE_TOLERANCE:.0%}. "
        "Invoiced quantity may not exceed received quantity. Currency must equal the PO currency. "
        "Same supplier + invoice number twice is a duplicate. "
        "Without a PO number, a unique supplier+SKU match yields REVIEW, never APPROVE."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()