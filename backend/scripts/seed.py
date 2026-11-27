"""
Idempotent database seed script for the Order-to-Audit System.

Loads exact Section 15 benchmark master data, opening balances, BOMs,
customers, suppliers, and demo users (password: demo123).

Usage:
    python -m scripts.seed
    python -m scripts.seed --reset
"""

import argparse
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.bom import Bom, BomItem
from app.models.inventory import StockBalance, StockLedger
from app.models.master import Customer, Material, PriceList, Product, Supplier
from app.models.user import FactorySettings, User
from app.services.stock_service import record_stock_movement


def reset_database(db: Session) -> None:
    tables = [
        "audit_logs",
        "payments",
        "sales_returns",
        "credit_notes",
        "invoice_items",
        "invoices",
        "invoice_sequences",
        "stock_reservations",
        "order_items",
        "orders",
        "production_consumptions",
        "production_runs",
        "purchases",
        "stock_ledger",
        "stock_balances",
        "bom_items",
        "boms",
        "price_lists",
        "materials",
        "suppliers",
        "customers",
        "products",
        "factory_settings",
        "users",
    ]
    for table in tables:
        db.execute(text(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE"))
    db.commit()


def seed_data(db: Session) -> None:
    settings = get_settings()

    # 1. Factory Settings
    if db.execute(select(FactorySettings)).scalar_one_or_none() is None:
        db.add(
            FactorySettings(
                id=1,
                factory_name=settings.FACTORY_NAME,
                address=settings.FACTORY_ADDRESS,
                gstin=settings.FACTORY_GSTIN,
                state=settings.FACTORY_STATE,
                default_variance_tolerance_pct=Decimal("3.00"),
            )
        )
        db.flush()

    # 2. Demo Users (password: demo123)
    demo_pw = hash_password("demo123")
    demo_users = [
        ("salesman_a", "salesman_a@kavericrunch.in", "Salesman A (Arjun K.)", "salesman", "+91-9842100001"),
        ("salesman_b", "salesman_b@kavericrunch.in", "Salesman B (Karthik S.)", "salesman", "+91-9842100002"),
        ("admin", "admin@kavericrunch.in", "Factory Admin (Meenakshi R.)", "admin", "+91-9842100003"),
        ("production", "production@kavericrunch.in", "Production Supervisor (Senthil V.)", "production", "+91-9842100004"),
        ("accountant", "accountant@kavericrunch.in", "Accountant / Auditor (Lakshmi N.)", "accountant", "+91-9842100005"),
        ("owner", "owner@kavericrunch.in", "Owner (Subramanian P.)", "owner", "+91-9842100006"),
    ]
    users_by_username: dict[str, User] = {}
    for uname, email, full_name, role, phone in demo_users:
        user = db.execute(select(User).where(User.username == uname)).scalar_one_or_none()
        if user is None:
            user = User(
                username=uname,
                email=email,
                full_name=full_name,
                password_hash=demo_pw,
                role=role,
                phone=phone,
                is_active=True,
            )
            db.add(user)
            db.flush()
        users_by_username[uname] = user

    admin_user = users_by_username["admin"]
    salesman_a = users_by_username["salesman_a"]
    salesman_b = users_by_username["salesman_b"]

    # 3. Customers (Benchmark + realistic Tamil Nadu / Karnataka demo accounts)
    customers_spec = [
        {
            "name": "Retailer A",
            "customer_type": "retailer",
            "gstin": "33AAACR1234F1Z5",
            "state": "Tamil Nadu",
            "address": "42 Big Bazaar Street, Teppakulam, Tiruchirappalli, Tamil Nadu - 620002",
            "contact_number": "+91-9443111001",
            "email": "orders@retailera-trichy.in",
            "assigned_salesman_id": salesman_a.id,
            "credit_limit": Decimal("75000.00"),
            "payment_terms": "Net 15 Days",
        },
        {
            "name": "Distributor B",
            "customer_type": "distributor",
            "gstin": "29AABCD5678G1Z9",
            "state": "Karnataka",
            "address": "18 APMC Yard, Yeshwanthpur, Bengaluru, Karnataka - 560022",
            "contact_number": "+91-9845222002",
            "email": "procurement@distributorb-blr.in",
            "assigned_salesman_id": salesman_b.id,
            "credit_limit": Decimal("250000.00"),
            "payment_terms": "Net 30 Days",
        },
        {
            "name": "Madurai Annapoorna Supermart",
            "customer_type": "retailer",
            "gstin": "33AAACM7788H1Z2",
            "state": "Tamil Nadu",
            "address": "105 West Masi Street, Madurai, Tamil Nadu - 625001",
            "contact_number": "+91-9442333003",
            "email": "store@maduraisupermart.in",
            "assigned_salesman_id": salesman_a.id,
            "credit_limit": Decimal("100000.00"),
            "payment_terms": "Net 15 Days",
        },
    ]
    for cdata in customers_spec:
        existing = db.execute(select(Customer).where(Customer.name == cdata["name"])).scalar_one_or_none()
        if existing is None:
            db.add(Customer(**cdata))
    db.flush()

    # 4. Suppliers
    suppliers_spec = [
        {
            "name": "Kaveri Agro Flour Mills",
            "gstin": "33AAACK9012K1Z1",
            "address": "88 Gandhi Market Road, Thanjavur, Tamil Nadu - 613001",
            "contact_number": "+91-9443444001",
            "email": "sales@kaveriagro.in",
            "state": "Tamil Nadu",
        },
        {
            "name": "Cauvery Gold Oil Refineries",
            "gstin": "33AAACC3344L1Z4",
            "address": "12 Oil Mill Lane, Erode, Tamil Nadu - 638001",
            "contact_number": "+91-9443444002",
            "email": "dispatch@cauverygold.in",
            "state": "Tamil Nadu",
        },
        {
            "name": "Trichy FlexiPack Industries",
            "gstin": "33AAACT5566M1Z8",
            "address": "Plot 7, SIDCO Ariyamangalam, Tiruchirappalli, Tamil Nadu - 620010",
            "contact_number": "+91-9443444003",
            "email": "orders@trichyflexipack.in",
            "state": "Tamil Nadu",
        },
    ]
    for sdata in suppliers_spec:
        existing = db.execute(select(Supplier).where(Supplier.name == sdata["name"])).scalar_one_or_none()
        if existing is None:
            db.add(Supplier(**sdata))
    db.flush()

    # 5. Raw Materials & Packaging Materials (exact Section 15.1 rates and opening stocks)
    materials_spec = [
        # Raw materials
        {
            "code": "RM-FLOUR",
            "name": "Flour",
            "material_type": "raw",
            "category": "Grains & Flours",
            "base_unit": "kg",
            "opening_qty": Decimal("100.0000"),
            "opening_rate": Decimal("42.000000"),
            "reorder_level": Decimal("40.0000"),
        },
        {
            "code": "RM-OIL",
            "name": "Cooking oil",
            "material_type": "raw",
            "category": "Edible Oils",
            "base_unit": "litre",
            "opening_qty": Decimal("30.0000"),
            "opening_rate": Decimal("140.000000"),
            "reorder_level": Decimal("15.0000"),
            "density_kg_per_litre": Decimal("0.9100"),
        },
        {
            "code": "RM-SPICE",
            "name": "Salt and spice mix",
            "material_type": "raw",
            "category": "Seasonings",
            "base_unit": "kg",
            "opening_qty": Decimal("5.0000"),
            "opening_rate": Decimal("200.000000"),
            "reorder_level": Decimal("2.0000"),
        },
        # Packaging materials
        {
            "code": "PM-POUCH-200",
            "name": "200 g pouch",
            "material_type": "packaging",
            "category": "Primary Packaging",
            "base_unit": "piece",
            "opening_qty": Decimal("500.0000"),
            "opening_rate": Decimal("2.500000"),
            "reorder_level": Decimal("200.0000"),
        },
        {
            "code": "PM-POUCH-500",
            "name": "500 g pouch",
            "material_type": "packaging",
            "category": "Primary Packaging",
            "base_unit": "piece",
            "opening_qty": Decimal("250.0000"),
            "opening_rate": Decimal("4.200000"),
            "reorder_level": Decimal("100.0000"),
        },
        {
            "code": "PM-CARTON",
            "name": "Carton",
            "material_type": "packaging",
            "category": "Secondary Packaging",
            "base_unit": "piece",
            "opening_qty": Decimal("30.0000"),
            "opening_rate": Decimal("15.000000"),
            "reorder_level": Decimal("15.0000"),
        },
        {
            "code": "PM-LABEL",
            "name": "Labels",
            "material_type": "packaging",
            "category": "Labels & Stickers",
            "base_unit": "piece",
            "opening_qty": Decimal("600.0000"),
            "opening_rate": Decimal("0.500000"),
            "reorder_level": Decimal("150.0000"),
        },
    ]

    materials_by_code: dict[str, Material] = {}
    for mdata in materials_spec:
        mat = db.execute(select(Material).where(Material.code == mdata["code"])).scalar_one_or_none()
        if mat is None:
            mat = Material(
                code=mdata["code"],
                name=mdata["name"],
                material_type=mdata["material_type"],
                category=mdata["category"],
                base_unit=mdata["base_unit"],
                opening_qty=mdata["opening_qty"],
                opening_rate=mdata["opening_rate"],
                current_avg_rate=mdata["opening_rate"],
                reorder_level=mdata["reorder_level"],
                density_kg_per_litre=mdata.get("density_kg_per_litre"),
                is_active=True,
            )
            db.add(mat)
            db.flush()
            cat = "raw_material" if mat.material_type == "raw" else "packaging_material"
            if mat.opening_qty > Decimal("0"):
                record_stock_movement(
                    db,
                    item_category=cat,
                    material_id=mat.id,
                    transaction_type="opening",
                    direction="IN",
                    quantity=mat.opening_qty,
                    unit=mat.base_unit,
                    rate=mat.opening_rate,
                    source_doc_type="opening_stock",
                    source_doc_id=mat.id,
                    source_doc_ref=f"OPEN-{mat.code}",
                    user_id=admin_user.id,
                    remarks="Opening stock balance from initial seed",
                )
        materials_by_code[mat.code] = mat

    # 6. Products (Murukku 200 g benchmark + extra pack sizes/products)
    products_spec = [
        {
            "code": "FG-MUR-200",
            "name": "Murukku 200 g",
            "category": "Traditional Savouries",
            "description": "Crispy South Indian rice & urad dal butter murukku (200 g pack)",
            "pack_size": Decimal("200.000"),
            "pack_unit": "g",
            "carton_capacity": 20,
            "unit": "packet",
            "selling_price": Decimal("50.00"),
            "hsn_code": "19059090",
            "gst_rate": Decimal("5.00"),
            "reorder_level": Decimal("60.0000"),
            "opening_fg_qty": Decimal("50.0000"),
            "opening_fg_rate": Decimal("30.000000"),
        },
        {
            "code": "FG-MUR-500",
            "name": "Murukku 500 g",
            "category": "Traditional Savouries",
            "description": "Family pack South Indian butter murukku (500 g pack)",
            "pack_size": Decimal("500.000"),
            "pack_unit": "g",
            "carton_capacity": 12,
            "unit": "packet",
            "selling_price": Decimal("120.00"),
            "hsn_code": "19059090",
            "gst_rate": Decimal("5.00"),
            "reorder_level": Decimal("30.0000"),
            "opening_fg_qty": Decimal("20.0000"),
            "opening_fg_rate": Decimal("72.000000"),
        },
        {
            "code": "FG-MIX-200",
            "name": "Mixture 200 g",
            "category": "Mixtures",
            "description": "Madras spicy Kara Mixture with roasted peanuts & curry leaves",
            "pack_size": Decimal("200.000"),
            "pack_unit": "g",
            "carton_capacity": 20,
            "unit": "packet",
            "selling_price": Decimal("55.00"),
            "hsn_code": "21069099",
            "gst_rate": Decimal("5.00"),
            "reorder_level": Decimal("40.0000"),
            "opening_fg_qty": Decimal("30.0000"),
            "opening_fg_rate": Decimal("33.000000"),
        },
    ]

    products_by_code: dict[str, Product] = {}
    for pdata in products_spec:
        prod = db.execute(select(Product).where(Product.code == pdata["code"])).scalar_one_or_none()
        if prod is None:
            opening_qty = pdata.pop("opening_fg_qty")
            opening_rate = pdata.pop("opening_fg_rate")
            prod = Product(**pdata, is_active=True)
            db.add(prod)
            db.flush()
            # Standard Price List entry
            db.add(
                PriceList(
                    product_id=prod.id,
                    customer_id=None,
                    price=prod.selling_price,
                    effective_date=date.today() - timedelta(days=30),
                    created_by=admin_user.id,
                )
            )
            if opening_qty > Decimal("0"):
                record_stock_movement(
                    db,
                    item_category="finished_good",
                    product_id=prod.id,
                    transaction_type="opening",
                    direction="IN",
                    quantity=opening_qty,
                    unit=prod.unit,
                    rate=opening_rate,
                    source_doc_type="opening_stock",
                    source_doc_id=prod.id,
                    source_doc_ref=f"OPEN-{prod.code}",
                    user_id=admin_user.id,
                    batch_number=f"OPEN-{prod.code}-B01",
                    expiry_date=date.today() + timedelta(days=90),
                    remarks="Opening finished goods stock from initial seed",
                )
        products_by_code[prod.code] = prod

    # 7. BOMs (exact Section 15.1 for Murukku 200 g + scaled version for Murukku 500 g)
    mur200 = products_by_code["FG-MUR-200"]
    existing_bom = db.execute(
        select(Bom).where(Bom.product_id == mur200.id, Bom.version == 1)
    ).scalar_one_or_none()
    if existing_bom is None:
        bom200 = Bom(
            product_id=mur200.id,
            version=1,
            name="Murukku 200 g Standard Recipe v1",
            expected_output_qty=Decimal("200.0000"),
            is_active=True,
            notes="Standard 200-packet batch recipe (20 packets/carton).",
        )
        db.add(bom200)
        db.flush()
        bom200_items = [
            (materials_by_code["RM-FLOUR"].id, Decimal("40.0000"), "kg"),
            (materials_by_code["RM-OIL"].id, Decimal("10.0000"), "litre"),
            (materials_by_code["RM-SPICE"].id, Decimal("1.2000"), "kg"),
            (materials_by_code["PM-POUCH-200"].id, Decimal("200.0000"), "piece"),
            (materials_by_code["PM-CARTON"].id, Decimal("10.0000"), "piece"),
        ]
        for mat_id, qty, unit in bom200_items:
            db.add(BomItem(bom_id=bom200.id, material_id=mat_id, quantity=qty, unit=unit))

    mur500 = products_by_code["FG-MUR-500"]
    existing_bom500 = db.execute(
        select(Bom).where(Bom.product_id == mur500.id, Bom.version == 1)
    ).scalar_one_or_none()
    if existing_bom500 is None:
        bom500 = Bom(
            product_id=mur500.id,
            version=1,
            name="Murukku 500 g Family Pack Recipe v1",
            expected_output_qty=Decimal("80.0000"),
            is_active=True,
            notes="Scaled 80-packet batch recipe (12 packets/carton).",
        )
        db.add(bom500)
        db.flush()
        bom500_items = [
            (materials_by_code["RM-FLOUR"].id, Decimal("40.0000"), "kg"),
            (materials_by_code["RM-OIL"].id, Decimal("10.0000"), "litre"),
            (materials_by_code["RM-SPICE"].id, Decimal("1.2000"), "kg"),
            (materials_by_code["PM-POUCH-500"].id, Decimal("80.0000"), "piece"),
            (materials_by_code["PM-CARTON"].id, Decimal("7.0000"), "piece"),
        ]
        for mat_id, qty, unit in bom500_items:
            db.add(BomItem(bom_id=bom500.id, material_id=mat_id, quantity=qty, unit=unit))

    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Order-to-Audit database")
    parser.add_argument("--reset", action="store_true", help="Truncate all tables before seeding")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.reset:
            reset_database(db)
        seed_data(db)
        print("Seed completed successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
