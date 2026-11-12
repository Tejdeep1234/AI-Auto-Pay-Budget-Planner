"""
Business Month-End Reconciliation Report Generator.
Generates an official Business Expense Statement PDF and CSV export
with all daily uploaded bills pre-sorted by category, vendor, and tax status.
"""

import os
import csv
import io
from datetime import datetime
from typing import Dict, Any, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from business.sorter import BusinessBillSorter
from database.db import get_db

class BusinessReportGenerator:
    def __init__(self, output_dir: str = "reports_output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._init_styles()

    def _init_styles(self):
        self.styles.add(ParagraphStyle(
            name='BizTitle',
            parent=self.styles['Title'],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor('#0F172A'),
            spaceAfter=4
        ))
        self.styles.add(ParagraphStyle(
            name='BizSubtitle',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#475569'),
            spaceAfter=12
        ))
        self.styles.add(ParagraphStyle(
            name='BizHeading',
            parent=self.styles['Heading2'],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#1E3A8A'),
            spaceBefore=14,
            spaceAfter=6
        ))

    def generate_sorted_business_pdf(self, company_name: str = "Morgan Technologies LLC") -> str:
        """
        Generates a print-ready PDF containing the full auto-sorted business ledger.
        """
        sorter = BusinessBillSorter()
        recon = sorter.generate_month_end_reconciliation()
        stats = recon["stats"]
        all_bills = sorter.get_sorted_bills(sort_by="category")

        now = datetime.now()
        filename = f"Business_Sorted_Ledger_{now.strftime('%Y_%m')}.pdf"
        filepath = os.path.join(self.output_dir, filename)

        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=36,
            leftMargin=36,
            topMargin=40,
            bottomMargin=36
        )

        elements = []

        # Title Banner
        elements.append(Paragraph(f"🏢 {company_name} — Month-End Bill Reconciliation", self.styles['BizTitle']))
        elements.append(Paragraph(f"Auto-Sorted Business Expense & Invoice Statement | Period: {now.strftime('%B %Y')}", self.styles['BizSubtitle']))
        elements.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#1E3A8A'), spaceAfter=8))

        # Executive Summary Box
        summary_rows = [
            ['Total Invoices Sorted:', str(recon['total_bills_sorted']), 'Gross Business Expense:', f"${recon['total_expenses']:,.2f}"],
            ['Tax Deductible Expenses:', f"${recon['total_tax_deductible']:,.2f}", 'Total Sales/VAT Tax Paid:', f"${recon['total_tax_paid']:,.2f}"],
            ['Pending Accounts Payable:', f"${recon['pending_payables']:,.2f}", 'Overdue Payables:', f"${recon['overdue_payables']:,.2f}"]
        ]
        sum_table = Table(summary_rows, colWidths=[140, 120, 140, 120])
        sum_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#334155')),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#334155')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ]))
        elements.append(sum_table)
        elements.append(Spacer(1, 10))

        # Category Breakdown Table
        elements.append(Paragraph("1. Expenses Pre-Sorted by Accounting Category", self.styles['BizHeading']))
        cat_data = [['Accounting Category', 'Bills', 'Total Spend', '% Share']]
        for c in recon['by_category']:
            cat_data.append([
                c['category'],
                str(c['doc_count']),
                f"${c['total_amount']:,.2f}",
                f"{c['percentage']}%"
            ])
        cat_data.append(['TOTAL', str(recon['total_bills_sorted']), f"${recon['total_expenses']:,.2f}", '100%'])

        cat_tbl = Table(cat_data, colWidths=[200, 80, 130, 110])
        cat_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8.5),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E2E8F0')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(cat_tbl)
        elements.append(Spacer(1, 10))

        # Itemized Auto-Sorted Bills Ledger Table
        elements.append(Paragraph("2. Itemized Invoices & Bills Registry", self.styles['BizHeading']))
        bill_data = [['Date', 'Vendor / Supplier', 'Category', 'Invoice #', 'Status', 'Tax', 'Total']]
        for b in all_bills:
            bill_data.append([
                b['invoice_date'],
                b['vendor_name'][:20],
                b['category'][:18],
                b.get('invoice_number', '')[:14],
                b['payment_status'],
                f"${b['tax_amount']:.2f}",
                f"${b['total_amount']:,.2f}"
            ])

        bill_tbl = Table(bill_data, colWidths=[65, 110, 100, 85, 55, 45, 60])
        bill_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0F766E')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('ALIGN', (4, 0), (4, -1), 'CENTER'),
            ('ALIGN', (5, 0), (-1, -1), 'RIGHT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0FDFA')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
        ]))
        elements.append(bill_tbl)

        doc.build(elements)
        return os.path.abspath(filepath)

    def generate_sorted_csv(self) -> str:
        """
        Generates a clean CSV export for QuickBooks / Xero bookkeeping.
        """
        sorter = BusinessBillSorter()
        bills = sorter.get_sorted_bills(sort_by="category")
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Invoice Date", "Vendor Name", "Category", "Invoice Number",
            "Payment Status", "Tax Deductible", "Subtotal", "Tax Amount",
            "Total Amount", "Currency", "Due Date", "Document Title"
        ])
        for b in bills:
            writer.writerow([
                b["invoice_date"], b["vendor_name"], b["category"],
                b.get("invoice_number", ""), b["payment_status"],
                "Yes" if b.get("tax_deductible") else "No",
                b.get("subtotal", 0.0), b.get("tax_amount", 0.0),
                b["total_amount"], b.get("currency", "USD"),
                b.get("due_date", ""), b.get("document_name", "")
            ])
        return output.getvalue()
