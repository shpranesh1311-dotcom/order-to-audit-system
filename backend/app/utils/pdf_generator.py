import io
from decimal import Decimal
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from app.models.sales import Invoice


def generate_invoice_pdf(invoice: Invoice) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>TAX INVOICE (GST)</b>", styles["Title"]))
    elements.append(Spacer(1, 4))

    header_data = [
        [
            Paragraph(
                f"<b>Seller:</b><br/>{invoice.seller_name}<br/>{invoice.seller_address}<br/>"
                f"GSTIN: <b>{invoice.seller_gstin}</b> | State: {invoice.seller_state}",
                styles["Normal"],
            ),
            Paragraph(
                f"<b>Invoice No:</b> {invoice.invoice_number}<br/>"
                f"<b>Invoice Date:</b> {invoice.invoice_date.strftime('%d-%m-%Y')}<br/>"
                f"<b>Financial Year:</b> {invoice.financial_year}<br/>"
                f"<b>Place of Supply:</b> {invoice.place_of_supply}<br/>"
                f"<b>Tax Type:</b> {invoice.tax_type.replace('_', ' + ')}",
                styles["Normal"],
            ),
        ],
        [
            Paragraph(
                f"<b>Buyer / Bill To:</b><br/>{invoice.buyer_name}<br/>{invoice.buyer_address}<br/>"
                f"GSTIN: {invoice.buyer_gstin or 'Unregistered'} | State: {invoice.buyer_state}",
                styles["Normal"],
            ),
            Paragraph(
                f"<b>Dispatch Status:</b> {invoice.dispatch_status.upper()}<br/>"
                f"<b>Invoice Status:</b> {invoice.status.upper()}",
                styles["Normal"],
            ),
        ],
    ]
    header_table = Table(header_data, colWidths=[105 * mm, 77 * mm])
    header_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#78350F")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D6D3D1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 10))

    item_rows = [
        [
            "#",
            "Product Description",
            "HSN",
            "Qty",
            "Rate (INR)",
            "Taxable (INR)",
            "GST %",
            "Tax (INR)",
            "Total (INR)",
        ]
    ]
    for idx, item in enumerate(invoice.items, start=1):
        line_tax = Decimal(item.cgst_amount) + Decimal(item.sgst_amount) + Decimal(item.igst_amount)
        item_rows.append(
            [
                str(idx),
                item.product_name,
                item.hsn_code,
                f"{item.quantity:,.2f}",
                f"{item.unit_price:,.2f}",
                f"{item.taxable_value:,.2f}",
                f"{item.gst_rate:.2f}%",
                f"{line_tax:,.2f}",
                f"{item.total_amount:,.2f}",
            ]
        )

    items_table = Table(
        item_rows,
        colWidths=[8 * mm, 46 * mm, 20 * mm, 18 * mm, 20 * mm, 24 * mm, 14 * mm, 16 * mm, 20 * mm],
    )
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#B45309")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("ALIGN", (3, 1), (-1, -1), "RIGHT"),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#78350F")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E7E5E4")),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(items_table)
    elements.append(Spacer(1, 10))

    summary_rows = [
        ["Taxable Value", f"INR {invoice.taxable_value:,.2f}"],
        ["CGST", f"INR {invoice.cgst_amount:,.2f}"],
        ["SGST", f"INR {invoice.sgst_amount:,.2f}"],
        ["IGST", f"INR {invoice.igst_amount:,.2f}"],
        ["Total Tax", f"INR {invoice.total_tax:,.2f}"],
        ["Grand Total", f"INR {invoice.grand_total:,.2f}"],
    ]
    summary_table = Table(summary_rows, colWidths=[45 * mm, 40 * mm], hAlign="RIGHT")
    summary_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#78350F")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E7E5E4")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#FEF3C7")),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 14))
    elements.append(
        Paragraph(
            "<i>This is a computer-generated GST invoice from Order-to-Audit System. Subject to Tiruchirappalli jurisdiction.</i>",
            styles["Normal"],
        )
    )

    doc.build(elements)
    return buffer.getvalue()


def generate_report_pdf(report_data: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"<b>{report_data['title']}</b>", styles["Heading2"]), Spacer(1, 6)]

    if report_data.get("disclaimer"):
        elements.append(Paragraph(report_data["disclaimer"], styles["Normal"]))
        elements.append(Spacer(1, 6))

    cols = report_data["columns"]
    table_data = [[c.replace("_", " ").title() for c in cols]]
    for row in report_data["rows"]:
        table_data.append([str(row.get(c, "")) for c in cols])

    if len(table_data) == 1:
        table_data.append(["No records found"] + [""] * (len(cols) - 1))

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#B45309")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(table)
    doc.build(elements)
    return buffer.getvalue()
