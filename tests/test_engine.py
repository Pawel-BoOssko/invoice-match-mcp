from decimal import Decimal
from pathlib import Path

from invoice_match.engine import APPROVE, HOLD_DUPLICATE, HOLD_PRICE, load_po_lines, match_invoice

POS = load_po_lines(Path(__file__).resolve().parents[1] / "data" / "purchase_orders.csv")


def inv(**kw):
    base = {"invoice_number": "T-1", "supplier": "Nordic Tyres", "po_number": "PO-1002", "currency": "EUR",
            "lines": [{"sku": "TYR-205", "qty": 200, "unit_price": 64.90}]}
    base.update(kw)
    return base


def test_exact_match_approves():
    assert match_invoice(inv(), POS).status == APPROVE


def test_price_tolerance_boundary():
    limit = Decimal("64.90") * Decimal("1.02")  # exactly 2 %
    ok = inv(lines=[{"sku": "TYR-205", "qty": 200, "unit_price": float(limit)}])
    assert match_invoice(ok, POS).status == APPROVE
    over = inv(lines=[{"sku": "TYR-205", "qty": 200, "unit_price": float(limit) + 0.05}])
    assert match_invoice(over, POS).status == HOLD_PRICE


def test_duplicate_is_flagged_before_anything_else():
    seen = {("Nordic Tyres", "T-1")}
    assert match_invoice(inv(), POS, seen).status == HOLD_DUPLICATE


def test_engine_is_pure():
    seen: set = set()
    match_invoice(inv(), POS, seen)
    assert seen == set()