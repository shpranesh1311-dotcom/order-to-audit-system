from decimal import Decimal
from app.utils.calculations import round_qty, to_decimal


UNIT_DIMENSIONS = {
    "kg": ("mass", Decimal("1000")),       # base: g
    "g": ("mass", Decimal("1")),
    "litre": ("volume", Decimal("1000")),  # base: ml
    "l": ("volume", Decimal("1000")),
    "ml": ("volume", Decimal("1")),
    "piece": ("count", Decimal("1")),
    "pieces": ("count", Decimal("1")),
    "pcs": ("count", Decimal("1")),
    "packet": ("packet", Decimal("1")),
    "packets": ("packet", Decimal("1")),
    "carton": ("carton", Decimal("1")),
    "cartons": ("carton", Decimal("1")),
}

CANONICAL_ALIASES = {
    "kg": "kg",
    "g": "g",
    "litre": "litre",
    "l": "litre",
    "litres": "litre",
    "ml": "ml",
    "piece": "piece",
    "pieces": "piece",
    "pcs": "piece",
    "packet": "packet",
    "packets": "packet",
    "carton": "carton",
    "cartons": "carton",
}


class UnitConversionError(ValueError):
    pass


def normalize_unit(unit: str) -> str:
    key = unit.strip().lower()
    if key not in CANONICAL_ALIASES:
        raise UnitConversionError(f"Unsupported unit: '{unit}'")
    return CANONICAL_ALIASES[key]


def convert_quantity(
    quantity: Decimal | int | float | str,
    from_unit: str,
    to_unit: str,
    *,
    carton_capacity: int | None = None,
    pack_size_g_or_ml: Decimal | None = None,
    density_kg_per_litre: Decimal | None = None,
) -> Decimal:
    """
    Convert compatible units strictly without crossing unrelated physical dimensions.
    - Mass: kg <-> g
    - Volume: litre <-> ml
    - Count: piece
    - Carton <-> Packet when carton_capacity is explicitly supplied
    - Mass <-> Volume ONLY when density_kg_per_litre is explicitly supplied and justified
    """
    qty = to_decimal(quantity)
    src = normalize_unit(from_unit)
    dst = normalize_unit(to_unit)

    if src == dst:
        return round_qty(qty)

    src_dim, src_factor = UNIT_DIMENSIONS[src]
    dst_dim, dst_factor = UNIT_DIMENSIONS[dst]

    if src_dim == dst_dim:
        base_val = qty * src_factor
        return round_qty(base_val / dst_factor)

    # Carton <-> Packet conversion
    if {src_dim, dst_dim} == {"carton", "packet"}:
        if not carton_capacity or carton_capacity <= 0:
            raise UnitConversionError("Carton capacity must be configured to convert between cartons and packets")
        cap = Decimal(str(carton_capacity))
        if src_dim == "carton":
            return round_qty(qty * cap)
        return round_qty(qty / cap)

    # Mass <-> Volume only with explicit material density (kg / litre)
    if {src_dim, dst_dim} == {"mass", "volume"}:
        if density_kg_per_litre is None or to_decimal(density_kg_per_litre) <= Decimal("0"):
            raise UnitConversionError(
                f"Cannot convert between mass ('{from_unit}') and volume ('{to_unit}') without configured material density"
            )
        density = to_decimal(density_kg_per_litre)
        if src_dim == "mass":
            kg_val = (qty * src_factor) / Decimal("1000")
            litres = kg_val / density
            ml_val = litres * Decimal("1000")
            return round_qty(ml_val / dst_factor)
        else:
            litres = (qty * src_factor) / Decimal("1000")
            kg_val = litres * density
            g_val = kg_val * Decimal("1000")
            return round_qty(g_val / dst_factor)

    raise UnitConversionError(
        f"Incompatible unit dimensions: cannot convert '{from_unit}' ({src_dim}) to '{to_unit}' ({dst_dim})"
    )
