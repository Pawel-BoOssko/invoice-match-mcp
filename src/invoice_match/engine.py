"""Deterministic three-way match (invoice vs purchase order vs goods received).

Why deterministic: an LLM may *call* these tools and explain the result, but the
decision itself must be reproducible and testable. The rules here are the
policy; the model is the interface.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Iterable

PRICE_TOLERANCE = Decimal("0.02")  # 2 % unit-price variance is accepted

APPROVE = "APPROVE"
HOLD_PRICE = "HOLD_PRICE"
HOLD_QTY = "HOLD_QTY"
HOLD_NO_PO = "HOLD_NO_PO"
HOLD_DUPLICATE = "HOLD_DUPLICATE"
HOLD_CURRENCY = "HOLD_CURRENCY"
REVIEW = "REVIEW"


@dataclass(frozen=True)
class POLine:
    po_number: str
    supplier: str
    sku: str
    qty_ordered: Decimal
    qty_received: Decimal
    unit_price: Decimal
    currency: str


@dataclass
class Decision:
    status: str
    reasons: list[str] = field(default_factory=list)
    po_number: str | None = None

    def to_dict(self) -> dict:
        return {"status": self.status, "reasons": self.reasons, "po_number": self.po_number}


def load_po_lines(path: str | Path) -> list[POLine]:
    with open(path, newline="", encoding="utf-8") as fh:
        return [
            POLine(
                po_number=r["po_number"].strip(),
                supplier=r["supplier"].strip(),
                sku=r["sku"].strip(),
                qty_ordered=Decimal(r["qty_ordered"]),
                qty_received=Decimal(r["qty_received"]),
                unit_price=Decimal(r["unit_price"]),
                currency=r["currency"].strip(),
            )
            for r in csv.DictReader(fh)
        ]


def _candidate_pos(invoice: dict, pos: Iterable[POLine]) -> set[str]:
    """Find POs for the supplier that contain every invoiced SKU."""
    skus = {line["sku"] for line in invoice["lines"]}
    by_po: dict[str, set[str]] = {}
    for p in pos:
        if p.supplier == invoice["supplier"]:
            by_po.setdefault(p.po_number, set()).add(p.sku)
    return {po for po, have in by_po.items() if skus <= have}


def match_invoice(
    invoice: dict,
    pos: list[POLine],
    seen_invoices: set[tuple[str, str]] | None = None,
) -> Decision:
    """Return a Decision for one invoice. Pure function: no I/O, no hidden state."""
    seen_invoices = seen_invoices or set()
    key = (invoice["supplier"], invoice["invoice_number"])
    if key in seen_invoices:
        return Decision(HOLD_DUPLICATE, [f"invoice {key[1]} from {key[0]} was already processed"])

    po_number = invoice.get("po_number")
    if not po_number:
        candidates = _candidate_pos(invoice, pos)
        if len(candidates) == 1:
            only = next(iter(candidates))
            return Decision(
                REVIEW,
                [f"no PO number on invoice; exactly one open PO matches supplier and SKUs: {only}"],
                only,
            )
        return Decision(HOLD_NO_PO, ["no PO number and no unique candidate PO"])

    po_lines = {p.sku: p for p in pos if p.po_number == po_number and p.supplier == invoice["supplier"]}
    if not po_lines:
        return Decision(HOLD_NO_PO, [f"PO {po_number} not found for supplier {invoice['supplier']}"], po_number)

    reasons: list[str] = []
    status = APPROVE
    for line in invoice["lines"]:
        p = po_lines.get(line["sku"])
        if p is None:
            reasons.append(f"SKU {line['sku']} is not on PO {po_number}")
            status = HOLD_QTY
            continue
        if invoice.get("currency", p.currency) != p.currency:
            return Decision(HOLD_CURRENCY, [f"invoice currency differs from PO currency {p.currency}"], po_number)
        qty = Decimal(str(line["qty"]))
        price = Decimal(str(line["unit_price"]))
        if qty > p.qty_received:
            reasons.append(f"SKU {p.sku}: invoiced {qty} but only {p.qty_received} received")
            status = HOLD_QTY
        drift = abs(price - p.unit_price) / p.unit_price
        if drift > PRICE_TOLERANCE:
            reasons.append(f"SKU {p.sku}: unit price {price} vs PO {p.unit_price} ({drift:.1%} off, limit {PRICE_TOLERANCE:.0%})")
            if status == APPROVE:
                status = HOLD_PRICE
    if status == APPROVE:
        reasons.append("quantities within received, prices within tolerance")
    return Decision(status, reasons, po_number)