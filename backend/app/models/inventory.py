from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class StockBalance(Base):
    """
    Concurrency-lock and reconciliation snapshot table.
    Physical truth is ALWAYS SUM(stock_ledger.signed_quantity).
    Every stock movement locks this row with SELECT ... FOR UPDATE before inserting into stock_ledger.
    """

    __tablename__ = "stock_balances"
    __table_args__ = (
        CheckConstraint(
            "(material_id IS NOT NULL AND product_id IS NULL) OR (material_id IS NULL AND product_id IS NOT NULL)",
            name="ck_stock_balance_single_target",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    item_category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    material_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=Decimal("0.0000"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class StockLedger(Base):
    """Append-only stock ledger. Rows must never be updated or deleted."""

    __tablename__ = "stock_ledger"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_stock_ledger_qty_non_negative"),
        CheckConstraint("direction IN ('IN', 'OUT')", name="ck_stock_ledger_direction"),
        CheckConstraint(
            "(material_id IS NOT NULL AND product_id IS NULL) OR (material_id IS NULL AND product_id IS NOT NULL)",
            name="ck_stock_ledger_single_target",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    item_category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    material_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("materials.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    product_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    transaction_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    signed_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    unit: Mapped[str] = mapped_column(String(24), nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False, default=Decimal("0.000000"))
    total_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=Decimal("0.00"))
    batch_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    source_doc_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_doc_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_doc_ref: Mapped[str | None] = mapped_column(String(80), nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    material = relationship("Material")
    product = relationship("Product")
    user = relationship("User")


class StockReservation(Base):
    __tablename__ = "stock_reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    order_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    reserved_qty: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active", index=True)  # active, fulfilled, released
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
