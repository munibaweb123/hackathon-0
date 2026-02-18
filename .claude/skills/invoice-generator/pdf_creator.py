"""
PDF Creator — generates professional invoice PDFs using reportlab.

Creates letter-sized invoices with company branding, line item tables,
tax calculations, and payment instructions.
"""

import os
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# Brand colors
BRAND_PRIMARY = colors.HexColor("#1a1a2e")
BRAND_ACCENT = colors.HexColor("#16213e")
BRAND_LIGHT = colors.HexColor("#f5f5f5")
BRAND_TEXT = colors.HexColor("#333333")
BRAND_MUTED = colors.HexColor("#666666")


class InvoicePDFCreator:
    """Generates professional invoice PDFs with company branding."""

    def __init__(self, company_info: Dict[str, Any]) -> None:
        self.company = company_info
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    # ------------------------------------------------------------------
    # Custom styles
    # ------------------------------------------------------------------

    def _setup_custom_styles(self) -> None:
        """Define custom paragraph styles for the invoice."""
        self.styles.add(ParagraphStyle(
            name="CompanyName",
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=BRAND_PRIMARY,
            spaceAfter=2,
        ))
        self.styles.add(ParagraphStyle(
            name="CompanyTagline",
            fontName="Helvetica",
            fontSize=9,
            textColor=BRAND_MUTED,
            spaceAfter=6,
        ))
        self.styles.add(ParagraphStyle(
            name="CompanyDetail",
            fontName="Helvetica",
            fontSize=8,
            textColor=BRAND_MUTED,
            leading=11,
        ))
        self.styles.add(ParagraphStyle(
            name="InvoiceTitle",
            fontName="Helvetica-Bold",
            fontSize=24,
            textColor=BRAND_PRIMARY,
            spaceAfter=4,
        ))
        self.styles.add(ParagraphStyle(
            name="MetaLabel",
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=BRAND_MUTED,
        ))
        self.styles.add(ParagraphStyle(
            name="MetaValue",
            fontName="Helvetica",
            fontSize=10,
            textColor=BRAND_TEXT,
        ))
        self.styles.add(ParagraphStyle(
            name="SectionHeader",
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=BRAND_PRIMARY,
            spaceBefore=16,
            spaceAfter=8,
        ))
        self.styles.add(ParagraphStyle(
            name="FooterText",
            fontName="Helvetica",
            fontSize=8,
            textColor=BRAND_MUTED,
            alignment=1,  # center
        ))
        self.styles.add(ParagraphStyle(
            name="NotesText",
            fontName="Helvetica",
            fontSize=9,
            textColor=BRAND_TEXT,
            leading=13,
        ))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_pdf(self, invoice_data: Dict[str, Any], output_path: str) -> str:
        """
        Generate a professional invoice PDF.

        Args:
            invoice_data: Dict with invoice_number, date, due_date, customer,
                         customer_email, line_items, subtotal, tax_rate,
                         tax_amount, total, notes, payment_terms.
            output_path: Full path for the output PDF file.

        Returns:
            The output path string.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            leftMargin=0.75 * inch,
            rightMargin=0.75 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.75 * inch,
        )

        elements = []

        # Header: company info + invoice title
        elements.extend(self._build_header(invoice_data))
        elements.append(Spacer(1, 20))

        # Meta: invoice number, dates, bill-to
        elements.extend(self._build_meta(invoice_data))
        elements.append(Spacer(1, 20))

        # Line items table
        elements.extend(self._build_line_items(invoice_data))
        elements.append(Spacer(1, 12))

        # Totals
        elements.extend(self._build_totals(invoice_data))
        elements.append(Spacer(1, 24))

        # Notes (if any)
        notes = invoice_data.get("notes")
        if notes:
            elements.append(Paragraph("Notes", self.styles["SectionHeader"]))
            elements.append(Paragraph(notes, self.styles["NotesText"]))
            elements.append(Spacer(1, 16))

        # Payment instructions
        elements.extend(self._build_payment_info(invoice_data))
        elements.append(Spacer(1, 30))

        # Footer
        elements.extend(self._build_footer())

        doc.build(elements)
        return output_path

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_header(self, invoice: Dict[str, Any]) -> list:
        """Company branding + INVOICE title."""
        elements = []

        # Two-column layout: company info on left, INVOICE on right
        company_name = self.company.get("company_name", "Company")
        tagline = self.company.get("tagline", "")

        # Company logo (if exists)
        logo_path = self.company.get("logo_path", "")
        logo_element = None
        if logo_path:
            # logo_path is relative to vault
            abs_logo = Path(logo_path)
            if abs_logo.exists():
                try:
                    logo_element = Image(str(abs_logo), width=1.5 * inch, height=0.6 * inch)
                    logo_element.hAlign = "LEFT"
                except Exception:
                    logo_element = None

        # Build header table
        left_col = []
        if logo_element:
            left_col.append(logo_element)
        left_col.append(Paragraph(company_name, self.styles["CompanyName"]))
        if tagline:
            left_col.append(Paragraph(tagline, self.styles["CompanyTagline"]))

        # Company contact details
        address = self.company.get("address", "").replace("\n", "<br/>")
        email = self.company.get("email", "")
        phone = self.company.get("phone", "")
        contact_parts = []
        if address:
            contact_parts.append(address)
        if email:
            contact_parts.append(email)
        if phone:
            contact_parts.append(phone)
        if contact_parts:
            left_col.append(Paragraph("<br/>".join(contact_parts), self.styles["CompanyDetail"]))

        right_col = [Paragraph("INVOICE", self.styles["InvoiceTitle"])]

        header_data = [[left_col, right_col]]
        header_table = Table(header_data, colWidths=[4.5 * inch, 2.5 * inch])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ]))

        elements.append(header_table)

        # Divider line
        divider = Table([[""]],colWidths=[7 * inch], rowHeights=[1])
        divider.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 2, BRAND_PRIMARY),
        ]))
        elements.append(divider)

        return elements

    def _build_meta(self, invoice: Dict[str, Any]) -> list:
        """Invoice number, dates, and bill-to section."""
        elements = []

        inv_number = invoice.get("invoice_number", "N/A")
        inv_date = invoice.get("date", date.today().isoformat())
        due_date = invoice.get("due_date", "N/A")
        customer = invoice.get("customer", "Customer")
        customer_email = invoice.get("customer_email", "")

        # Left: Bill To, Right: Invoice details
        bill_to_lines = [
            Paragraph("BILL TO", self.styles["MetaLabel"]),
            Spacer(1, 4),
            Paragraph(f"<b>{customer}</b>", self.styles["MetaValue"]),
        ]
        if customer_email:
            bill_to_lines.append(Paragraph(customer_email, self.styles["CompanyDetail"]))

        meta_lines = [
            Paragraph("Invoice Number", self.styles["MetaLabel"]),
            Paragraph(f"<b>{inv_number}</b>", self.styles["MetaValue"]),
            Spacer(1, 6),
            Paragraph("Invoice Date", self.styles["MetaLabel"]),
            Paragraph(inv_date, self.styles["MetaValue"]),
            Spacer(1, 6),
            Paragraph("Due Date", self.styles["MetaLabel"]),
            Paragraph(f"<b>{due_date}</b>", self.styles["MetaValue"]),
        ]

        meta_data = [[bill_to_lines, meta_lines]]
        meta_table = Table(meta_data, colWidths=[4.5 * inch, 2.5 * inch])
        meta_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ]))
        elements.append(meta_table)

        return elements

    def _build_line_items(self, invoice: Dict[str, Any]) -> list:
        """Line items table with description, qty, rate, amount."""
        elements = []
        items = invoice.get("line_items", [])
        currency = invoice.get("currency", self.company.get("default_currency", "USD"))
        symbol = "$" if currency == "USD" else currency + " "

        # Table header
        header = ["Description", "Qty", "Rate", "Amount"]
        data = [header]

        for item in items:
            desc = item.get("description", "Service")
            qty = item.get("quantity", 1)
            rate = float(item.get("rate", 0))
            amount = float(item.get("amount", qty * rate))
            data.append([
                desc,
                str(qty),
                f"{symbol}{rate:,.2f}",
                f"{symbol}{amount:,.2f}",
            ])

        col_widths = [3.8 * inch, 0.8 * inch, 1.2 * inch, 1.2 * inch]
        table = Table(data, colWidths=col_widths)
        table.setStyle(TableStyle([
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            # Body rows
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("TOPPADDING", (0, 1), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
            # Alternating row colors
            *[
                ("BACKGROUND", (0, i), (-1, i), BRAND_LIGHT)
                for i in range(2, len(data), 2)
            ],
            # Alignment
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("ALIGN", (0, 0), (0, -1), "LEFT"),
            # Grid
            ("LINEBELOW", (0, 0), (-1, 0), 1, BRAND_PRIMARY),
            ("LINEBELOW", (0, -1), (-1, -1), 1, BRAND_PRIMARY),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        elements.append(table)
        return elements

    def _build_totals(self, invoice: Dict[str, Any]) -> list:
        """Subtotal, tax, and total section."""
        elements = []
        currency = invoice.get("currency", self.company.get("default_currency", "USD"))
        symbol = "$" if currency == "USD" else currency + " "

        subtotal = float(invoice.get("subtotal", 0))
        tax_rate = float(invoice.get("tax_rate", 0))
        tax_amount = float(invoice.get("tax_amount", 0))
        total = float(invoice.get("total", 0))

        totals_data = [
            ["", "Subtotal:", f"{symbol}{subtotal:,.2f}"],
        ]
        if tax_rate > 0:
            totals_data.append(
                ["", f"Tax ({tax_rate * 100:.1f}%):", f"{symbol}{tax_amount:,.2f}"]
            )
        totals_data.append(["", "TOTAL:", f"{symbol}{total:,.2f}"])

        totals_table = Table(
            totals_data,
            colWidths=[3.8 * inch, 1.8 * inch, 1.4 * inch],
        )

        style_commands = [
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            # Total row emphasis
            ("FONTNAME", (1, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE", (1, -1), (-1, -1), 12),
            ("TEXTCOLOR", (1, -1), (-1, -1), BRAND_PRIMARY),
            ("LINEABOVE", (1, -1), (-1, -1), 1, BRAND_PRIMARY),
        ]
        totals_table.setStyle(TableStyle(style_commands))

        elements.append(totals_table)
        return elements

    def _build_payment_info(self, invoice: Dict[str, Any]) -> list:
        """Payment instructions section."""
        elements = []
        elements.append(Paragraph("Payment Information", self.styles["SectionHeader"]))

        payment_terms = invoice.get(
            "payment_terms", self.company.get("default_payment_terms", "Net 30")
        )
        bank_name = self.company.get("bank_name", "")
        bank_account = self.company.get("bank_account", "")
        bank_routing = self.company.get("bank_routing", "")

        lines = [f"<b>Payment Terms:</b> {payment_terms}"]
        if bank_name:
            lines.append(f"<b>Bank:</b> {bank_name}")
        if bank_account:
            lines.append(f"<b>Account:</b> {bank_account}")
        if bank_routing:
            lines.append(f"<b>Routing:</b> {bank_routing}")

        billing_email = self.company.get("email", "")
        if billing_email:
            lines.append(f"<b>Questions?</b> Contact {billing_email}")

        elements.append(Paragraph("<br/>".join(lines), self.styles["NotesText"]))
        return elements

    def _build_footer(self) -> list:
        """Footer with thank you message."""
        elements = []
        company_name = self.company.get("company_name", "Company")
        website = self.company.get("website", "")

        divider = Table([[""]],colWidths=[7 * inch], rowHeights=[1])
        divider.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, BRAND_MUTED),
        ]))
        elements.append(divider)
        elements.append(Spacer(1, 8))

        footer_text = f"Thank you for your business! — {company_name}"
        if website:
            footer_text += f" | {website}"
        elements.append(Paragraph(footer_text, self.styles["FooterText"]))

        return elements
