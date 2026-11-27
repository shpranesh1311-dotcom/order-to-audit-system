from datetime import date
from decimal import Decimal
import pytest
from app.utils.calculations import (
    calc_gst_breakdown,
    calc_variance,
    calc_weighted_avg_rate,
    get_financial_year,
)
from app.utils.unit_conversion import UnitConversionError, convert_quantity


def test_unit_conversions():
    assert convert_quantity(Decimal("2.5"), "kg", "g") == Decimal("2500.0000")
    assert convert_quantity(Decimal("500"), "g", "kg") == Decimal("0.5000")
    assert convert_quantity(Decimal("1.5"), "litre", "ml") == Decimal("1500.0000")
    assert convert_quantity(Decimal("3"), "carton", "packet", carton_capacity=20) == Decimal("60.0000")
    assert convert_quantity(Decimal("60"), "packet", "carton", carton_capacity=20) == Decimal("3.0000")

    # Mass <-> Volume blocked without explicit density
    with pytest.raises(UnitConversionError):
        convert_quantity(Decimal("10"), "kg", "litre")

    # Allowed when explicit density is configured
    litres = convert_quantity(Decimal("9.1"), "kg", "litre", density_kg_per_litre=Decimal("0.91"))
    assert litres == Decimal("10.0000")


def test_financial_and_gst_calculations():
    avg = calc_weighted_avg_rate(Decimal("100"), Decimal("42"), Decimal("60"), Decimal("45"))
    assert avg == Decimal("43.125000")

    intra = calc_gst_breakdown(Decimal("7500.00"), Decimal("5.00"), "Tamil Nadu", "Tamil Nadu")
    assert intra["tax_type"] == "CGST_SGST"
    assert intra["cgst_amount"] == Decimal("187.50")
    assert intra["sgst_amount"] == Decimal("187.50")
    assert intra["igst_amount"] == Decimal("0.00")
    assert intra["grand_total"] == Decimal("7875.00")

    inter = calc_gst_breakdown(Decimal("7500.00"), Decimal("5.00"), "Tamil Nadu", "Karnataka")
    assert inter["tax_type"] == "IGST"
    assert inter["igst_amount"] == Decimal("375.00")
    assert inter["grand_total"] == Decimal("7875.00")

    assert get_financial_year(date(2026, 11, 26)) == "2026-27"
    assert get_financial_year(date(2027, 2, 15)) == "2026-27"

    qty, pct, flagged = calc_variance(Decimal("200"), Decimal("194"), Decimal("3.00"))
    assert pct == Decimal("-3.00")
    assert flagged is False

    qty2, pct2, flagged2 = calc_variance(Decimal("200"), Decimal("188"), Decimal("3.00"))
    assert pct2 == Decimal("-6.00")
    assert flagged2 is True
