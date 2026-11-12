"""
Daily Business Document & Bill Parser.
Extracts invoice numbers, vendors, tax amounts, categories, and due dates
from uploaded documents and daily receipts for small and large businesses.
"""

import re
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

class BusinessDocumentParser:
    """
    Parses and categorizes daily business invoices, receipts, and bills
    to eliminate month-end manual sorting overhead.
    """

    VENDOR_CATEGORY_MAP = {
        "aws": "IT & Software",
        "amazon web services": "IT & Software",
        "google": "IT & Software",
        "microsoft": "IT & Software",
        "slack": "IT & Software",
        "adobe": "IT & Software",
        "github": "IT & Software",
        "commercial realty": "Facilities & Rent",
        "landlord": "Facilities & Rent",
        "lease": "Facilities & Rent",
        "power": "Utilities",
        "electric": "Utilities",
        "water": "Utilities",
        "telecom": "Utilities",
        "at&t": "Utilities",
        "verizon": "Utilities",
        "fedex": "Shipping & Logistics",
        "ups": "Shipping & Logistics",
        "dhl": "Shipping & Logistics",
        "freight": "Shipping & Logistics",
        "acme": "Inventory & COGS",
        "supplies": "Inventory & COGS",
        "packaging": "Inventory & COGS",
        "materials": "Inventory & COGS",
        "meta": "Marketing & Advertising",
        "facebook": "Marketing & Advertising",
        "ads": "Marketing & Advertising",
        "billboard": "Marketing & Advertising",
        "print": "Marketing & Advertising",
        "accounting": "Professional Services",
        "cpa": "Professional Services",
        "legal": "Professional Services",
        "law": "Professional Services",
        "insurance": "Insurance & Legal",
        "grainger": "Office & Equipment",
        "office depot": "Office & Equipment",
        "staples": "Office & Equipment"
    }

    @classmethod
    def infer_category(cls, vendor_name: str, doc_name: str = "") -> str:
        text = f"{vendor_name} {doc_name}".lower()
        for keyword, cat in cls.VENDOR_CATEGORY_MAP.items():
            if keyword in text:
                return cat
        return "General Business Expense"

    @classmethod
    def parse_document_input(
        cls,
        vendor_name: str,
        total_amount: float,
        document_name: Optional[str] = None,
        invoice_number: Optional[str] = None,
        invoice_date: Optional[str] = None,
        category: Optional[str] = None,
        tax_amount: Optional[float] = None,
        payment_status: str = "PAID",
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Validates, enriches, and structures a daily bill entry for instant sorting.
        """
        now = datetime.now()
        date_str = invoice_date or now.strftime("%Y-%m-%d")
        
        # Calculate due date (default net-30 if not specified)
        try:
            inv_dt = datetime.strptime(date_str, "%Y-%m-%d")
            due_str = (inv_dt + timedelta(days=30)).strftime("%Y-%m-%d")
        except Exception:
            due_str = (now + timedelta(days=30)).strftime("%Y-%m-%d")

        # Inferred Category if not given
        resolved_category = category if (category and category != "Auto-Detect") else cls.infer_category(vendor_name, document_name or "")

        # Default estimated tax if zero (e.g. 7.5% commercial sales/service tax)
        calc_tax = tax_amount if tax_amount is not None else round(total_amount * 0.08, 2)
        calc_subtotal = round(max(0.0, total_amount - calc_tax), 2)

        # Tax deductibility (standard business expenses are tax deductible)
        is_tax_deductible = True
        if "fine" in (document_name or "").lower() or "penalty" in (document_name or "").lower():
            is_tax_deductible = False

        doc_title = document_name or f"Bill from {vendor_name}"
        inv_no = invoice_number or f"INV-{now.strftime('%Y%m%d')}-{abs(hash(vendor_name)) % 10000:04d}"

        return {
            "document_name": doc_title,
            "vendor_name": vendor_name.strip(),
            "invoice_number": inv_no.strip(),
            "invoice_date": date_str,
            "due_date": due_str,
            "subtotal": calc_subtotal,
            "tax_amount": calc_tax,
            "total_amount": round(total_amount, 2),
            "currency": "USD",
            "category": resolved_category,
            "payment_status": payment_status.upper(),
            "tax_deductible": 1 if is_tax_deductible else 0,
            "extracted_notes": notes or f"Daily bill parsed and auto-categorized into '{resolved_category}'"
        }
