from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ProductionRun(Base):
    __tablename__ = "production_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    bom_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("boms.id", ondelete="RESTRICT"), nullable=False
    )
    bom_version: Mapped[int] = mapped_column(Integer, nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    batches: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    expected_output: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    actual_good_packets: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    damaged_pouches: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0.0000"))
    wastage_qty: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0.0000"))
    actual_cartons_used: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0.0000"))

    yield_variance_qty: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    yield_variance_pct: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    yield_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tolerance_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("3.00"))

    labour_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    gas_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    power_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    other_overhead_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))

    raw_material_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    packaging_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    cost_per_packet: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0.0000"))

    batch_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="completed")
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    product = relationship("Product")
    bom = relationship("Bom")
    consumptions = relationship("ProductionConsumption", back_populates="production_run", cascade="all, delete-orphan")


class ProductionConsumption(Base):
    __tablename__ = "production_consumptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    production_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("production_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    material_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=False
    )
    material_type: Mapped[str] = mapped_column(String(24), nullable=False)  # raw / packaging
    planned_qty: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    actual_qty: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    variance_qty: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    variance_pct: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    is_flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    total_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    production_run = relationship("ProductionRun", back_populates="consumptions")
    material = relationship("Material")
