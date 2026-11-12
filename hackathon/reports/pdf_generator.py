"""
Professional Month-End Expenditure & Transaction PDF Report Generator.
Uses ReportLab to produce print-quality financial statements that are
delivered via WhatsApp and in-app notifications.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    HRFlowable, PageBreak, KeepTogether
)

from database.db import get_db


class MonthEndReportGenerator:
    """Generates a professional Month-End Expenditure & Transaction PDF Report."""

    def __init__(self, output_dir: str = "reports_output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.styles = getSampleStyleSheet()
        self._build_custom_styles()

    def _build_custom_styles(self):
        """Define custom paragraph styles for the PDF report."""
        self.styles.add(ParagraphStyle(
            name='ReportTitle',
            parent=self.styles['Title'],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor('#1E3A8A'),
            spaceAfter=6
        ))
        self.styles.add(ParagraphStyle(
            name='ReportSubtitle',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.HexColor('#4B5563'),
            alignment=TA_CENTER,
            spaceAfter=14
        ))
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor('#1E3A8A'),
            spaceBefore=16,
            spaceAfter=8,
            borderPadding=(0, 0, 4, 0)
        ))
        self.styles.add(ParagraphStyle(
            name='SmallText',
            parent=self.styles['Normal'],
            fontSize=8,
            textColor=colors.HexColor('#6B7280')
        ))
        self.styles.add(ParagraphStyle(
            name='MetricValue',
            parent=self.styles['Normal'],
            fontSize=12,
            leading=16,
            textColor=colors.HexColor('#111827')
        ))
        self.styles.add(ParagraphStyle(
            name='AlertRed',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#DC2626')
        ))
        self.styles.add(ParagraphStyle(
            name='AlertGreen',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#16A34A')
        ))

    def generate_monthly_report(self, user_name: Optional[str] = None) -> str:
        """
        Generates the complete Month-End Expenditure & Transaction PDF.
        Returns the file path of the generated PDF.
        """
        db = get_db()
        account = db.get_account() or {}
        transactions = db.get_monthly_transactions(limit=200)
        expenditure_by_category = db.get_expenditure_by_category()
        subscriptions = db.get_subscriptions()
        active_subs = [s for s in subscriptions if s.get("status") == "ACTIVE"]
        paused_subs = [s for s in subscriptions if s.get("status") == "SUSPENDED"]
        agent_actions = db.get_agent_actions(limit=30)

        name = user_name or account.get("user_name", "User")
        balance = account.get("balance", 0.0)
        threshold = account.get("safety_threshold", 300.0)
        buffer_val = account.get("overdraft_buffer", 100.0)
        currency = account.get("currency", "USD")

        now = datetime.now()
        month_name = now.strftime("%B %Y")
        report_date = now.strftime("%b %d, %Y at %I:%M %p")

        filename = f"MonthEnd_Report_{now.strftime('%Y_%m')}.pdf"
        filepath = os.path.join(self.output_dir, filename)

        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=50,
            bottomMargin=40
        )

        elements = []

        # -------- HEADER / TITLE SECTION --------
        elements.append(Paragraph(
            "Smart Auto-Pay & Balance Budget Planner",
            self.styles['ReportTitle']
        ))
        elements.append(Paragraph(
            f"Month-End Expenditure Report  |  {month_name}",
            self.styles['ReportSubtitle']
        ))
        elements.append(HRFlowable(
            width="100%", thickness=2,
            color=colors.HexColor('#3B82F6'), spaceAfter=10
        ))

        # Meta info row
        meta_data = [
            ['Account Holder:', name, 'Report Generated:', report_date],
            ['Account Currency:', currency, 'AI Agent Status:', 'Active & Monitoring']
        ]
        meta_table = Table(meta_data, colWidths=[100, 140, 120, 150])
        meta_table.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#6B7280')),
            ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#6B7280')),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
            ('FONTNAME', (3, 0), (3, -1), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 12))

        # -------- ACCOUNT SUMMARY SECTION --------
        elements.append(Paragraph("1. Account & Guardrail Summary", self.styles['SectionHeader']))

        total_spent = sum(t["amount"] for t in transactions)
        total_active_subs = sum(s["amount"] for s in active_subs)
        total_paused_subs = sum(s["amount"] for s in paused_subs)
        total_saved = sum(a.get("savings_amount", 0) for a in agent_actions if a.get("savings_amount"))

        summary_data = [
            ['Metric', 'Value', 'Status'],
            ['Current Available Balance', f'${balance:.2f}',
             'SAFE' if balance >= threshold else 'BELOW THRESHOLD'],
            ['Safety Threshold', f'${threshold:.2f}', 'Guardrail Active'],
            ['Overdraft Buffer Floor', f'${buffer_val:.2f}', 'Protected'],
            ['Total Month Expenditure', f'${total_spent:.2f}', f'{len(transactions)} Transactions'],
            ['Active Subscriptions', f'${total_active_subs:.2f}/mo', f'{len(active_subs)} Active'],
            ['Paused (Savings Preserved)', f'${total_paused_subs:.2f}/mo', f'{len(paused_subs)} Paused'],
            ['Total AI Agent Savings', f'${total_saved:.2f}', f'{len(agent_actions)} Actions Taken']
        ]

        summary_table = Table(summary_data, colWidths=[200, 130, 150])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F4FF')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 16))

        # -------- EXPENDITURE BY CATEGORY TABLE --------
        elements.append(Paragraph("2. Month-End Expenditure by Category", self.styles['SectionHeader']))

        cat_header = ['Category', 'Transactions', 'Total Spent', 'Avg per Transaction', '% of Total']
        cat_rows = [cat_header]
        for cat in expenditure_by_category:
            pct = round((cat["total_spent"] / total_spent) * 100, 1) if total_spent > 0 else 0
            cat_rows.append([
                cat["category"],
                str(cat["transaction_count"]),
                f'${cat["total_spent"]:.2f}',
                f'${cat["avg_transaction"]:.2f}',
                f'{pct}%'
            ])
        # Grand total row
        cat_rows.append([
            'GRAND TOTAL', str(len(transactions)), f'${total_spent:.2f}', '', '100%'
        ])

        cat_table = Table(cat_rows, colWidths=[140, 80, 100, 110, 70])
        cat_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (2, 0), (3, -1), 'RIGHT'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#ECFDF5')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#F0FDF4')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
        ]
        cat_table.setStyle(TableStyle(cat_style))
        elements.append(cat_table)
        elements.append(Spacer(1, 16))

        # -------- FULL MONTHLY TRANSACTION LEDGER --------
        elements.append(Paragraph("3. Complete Monthly Transaction Ledger", self.styles['SectionHeader']))

        tx_header = ['Date', 'Merchant', 'Category', 'Amount', 'Payment Method', 'Status']
        tx_rows = [tx_header]
        for t in transactions:
            tx_rows.append([
                t["transaction_date"],
                t["merchant"][:25],
                t["category"],
                f'${t["amount"]:.2f}',
                t["payment_method"],
                t["status"]
            ])

        tx_table = Table(tx_rows, colWidths=[70, 130, 95, 65, 80, 65])
        tx_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#7C3AED')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('ALIGN', (5, 0), (5, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F5F3FF')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ]
        tx_table.setStyle(TableStyle(tx_style))
        elements.append(tx_table)
        elements.append(Spacer(1, 16))

        # -------- ACTIVE PAYPAL SUBSCRIPTIONS TABLE --------
        elements.append(Paragraph("4. Active PayPal Subscriptions", self.styles['SectionHeader']))

        sub_header = ['Subscription', 'Vendor', 'Amount/mo', 'Next Billing', 'Usage (30d)', 'Classification']
        sub_rows = [sub_header]
        for s in active_subs:
            sub_rows.append([
                s["name"][:22],
                s["vendor"][:18],
                f'${s["amount"]:.2f}',
                s["next_billing_date"],
                f'{s["usage_days_last_30"]}d / {s["hours_used_last_30"]:.0f}h',
                s["essentiality"].title()
            ])
        if paused_subs:
            for s in paused_subs:
                sub_rows.append([
                    s["name"][:22] + " [PAUSED]",
                    s["vendor"][:18],
                    f'${s["amount"]:.2f}',
                    'SUSPENDED',
                    f'{s["usage_days_last_30"]}d / {s["hours_used_last_30"]:.0f}h',
                    s["essentiality"].title()
                ])

        sub_table = Table(sub_rows, colWidths=[120, 90, 65, 75, 75, 75])
        sub_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0369A1')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('ALIGN', (3, 0), (3, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F0F9FF')]),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(sub_table)
        elements.append(Spacer(1, 16))

        # -------- AI AGENT ACTIONS AUDIT LOG --------
        elements.append(Paragraph("5. AI Agent Actions & Savings Audit", self.styles['SectionHeader']))

        if agent_actions:
            act_header = ['Timestamp', 'Action', 'Subscription', 'Saved', 'Status']
            act_rows = [act_header]
            for a in agent_actions[:15]:
                act_rows.append([
                    a["created_at"][5:16].replace("T", " "),
                    a["action_type"],
                    (a.get("subscription_name") or a.get("subscription_id") or "Account")[:22],
                    f'${a.get("savings_amount", 0):.2f}',
                    a["user_status"]
                ])

            act_table = Table(act_rows, colWidths=[100, 100, 130, 70, 100])
            act_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#B45309')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
                ('ALIGN', (4, 0), (4, -1), 'CENTER'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#FFFBEB')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
            ]))
            elements.append(act_table)
        else:
            elements.append(Paragraph("No AI agent actions recorded this period.", self.styles['Normal']))

        elements.append(Spacer(1, 20))

        # -------- FOOTER --------
        elements.append(HRFlowable(
            width="100%", thickness=1,
            color=colors.HexColor('#D1D5DB'), spaceAfter=8
        ))
        elements.append(Paragraph(
            f"This report was auto-generated by the Smart Auto-Pay & Balance Budget Planner AI Agent on {report_date}. "
            f"Delivered via WhatsApp and in-app notification for your convenience.",
            self.styles['SmallText']
        ))
        elements.append(Paragraph(
            "Powered by PayPal Subscriptions API  |  Autonomous Financial Protection Agent",
            self.styles['SmallText']
        ))

        # Build the PDF
        doc.build(elements)
        return os.path.abspath(filepath)
