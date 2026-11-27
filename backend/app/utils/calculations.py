from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple


MONEY_QUANT = Decimal("0.01")
QTY_QUANT = Decimal("0.0001")
RATE_QUANT = Decimal("0.000001")
PCT_QUANT = Decimal("0.01")


def to_decimal(value: Decimal | int | float | str | None, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def round_money(value: Decimal | int | float | str) -> Decimal:
    return to_decimal(value).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def round_qty(value: Decimal | int | float | str) -> Decimal:
    return to_decimal(value).quantize(QTY_QUANT, rounding=ROUND_HALF_UP)


def round_rate(value: Decimal | int | float | str) -> Decimal:
    return to_decimal(value).quantize(RATE_QUANT, rounding=ROUND_HALF_UP)


def round_pct(value: Decimal | int | float | str) -> Decimal:
    return to_decimal(value).quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


def calc_weighted_avg_rate(
    old_qty: Decimal,
    old_avg_rate: Decimal,
    new_qty: Decimal,
    purchase_rate: Decimal,
) -> Decimal:
    old_q = to_decimal(old_qty)
    old_r = to_decimal(old_avg_rate)
    new_q = to_decimal(new_qty)
    new_r = to_decimal(purchase_rate)
    total_qty = old_q + new_q
    if total_qty <= Decimal("0"):
        return round_rate(new_r)
    total_value = (old_q * old_r) + (new_q * new_r)
    return round_rate(total_value / total_qty)


def calc_variance(
    planned: Decimal,
    actual: Decimal,
    tolerance_pct: Decimal = Decimal("3.00"),
) -> Tuple[Decimal, Decimal, bool]:
    """
    Returns (variance_qty, variance_pct, is_flagged).
    Positive variance_qty means actual > planned.
    Absolute variance_pct strictly greater than tolerance_pct is flagged.
    """
    p = to_decimal(planned)
    a = to_decimal(actual)
    tol = to_decimal(tolerance_pct)
    var_qty = round_qty(a - p)
    if p == Decimal("0"):
        var_pct = Decimal("0.00") if a == Decimal("0") else Decimal("100.00")
    else:
        var_pct = round_pct(((a - p) / p) * Decimal("100"))
    is_flagged = abs(var_pct) > tol
    return var_qty, var_pct, is_flagged


def calc_gst_breakdown(
    taxable_value: Decimal,
    gst_rate: Decimal,
    seller_state: str,
    place_of_supply: str,
) -> dict[str, Decimal | str]:
    taxable = round_money(taxable_value)
    rate = to_decimal(gst_rate)
    intra_state = seller_state.strip().lower() == place_of_supply.strip().lower()

    if intra_state:
        half_rate = rate / Decimal("2")
        cgst = round_money(taxable * half_rate / Decimal("100"))
        sgst = round_money(taxable * half_rate / Decimal("100"))
        igst = Decimal("0.00")
        total_tax = round_money(cgst + sgst)
        return {
            "tax_type": "CGST_SGST",
            "cgst_rate": round_pct(half_rate),
            "sgst_rate": round_pct(half_rate),
            "igst_rate": Decimal("0.00"),
            "cgst_amount": cgst,
            "sgst_amount": sgst,
            "igst_amount": igst,
            "total_tax": total_tax,
            "grand_total": round_money(taxable + total_tax),
        }
    igst = round_money(taxable * rate / Decimal("100"))
    return {
        "tax_type": "IGST",
        "cgst_rate": Decimal("0.00"),
        "sgst_rate": Decimal("0.00"),
        "igst_rate": round_pct(rate),
        "cgst_amount": Decimal("0.00"),
        "sgst_amount": Decimal("0.00"),
        "igst_amount": igst,
        "total_tax": igst,
        "grand_total": round_money(taxable + igst),
    }


def get_financial_year(target_date: date) -> str:
    """Indian Financial Year (April to March), e.g., 2026-27."""
    if target_date.month >= 4:
        start_year = target_date.year
    else:
        start_year = target_date.year - 1
    end_year_short = (start_year + 1) % 100
    return f"{start_year}-{end_year_short:02d}"
