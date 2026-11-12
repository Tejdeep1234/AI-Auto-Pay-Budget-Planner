"""
Business Bill Sorter and Month-End Reconciliation Engine.
Solves the month-end sorting burden by grouping, indexing, and auditing
daily ingested bills across multiple accounting dimensions.
"""

from typing import List, Dict, Any
from database.db import get_db

class BusinessBillSorter:
    """
    Automates the month-end sorting process for small and large businesses.
    """

    def __init__(self, db=None):
        self.db = db or get_db()

    def get_sorted_bills(
        self,
        sort_by: str = "category",  # 'category', 'vendor', 'date', 'status', 'amount'
        category_filter: str = "All",
        vendor_filter: str = "All",
        status_filter: str = "All"
    ) -> List[Dict[str, Any]]:
        """
        Retrieves and sorts business bills based on user-chosen accounting criteria.
        """
        docs = self.db.get_business_documents(
            category=category_filter,
            vendor=vendor_filter,
            payment_status=status_filter,
            limit=200
        )

        if sort_by == "category":
            return sorted(docs, key=lambda x: (x["category"], -x["total_amount"]))
        elif sort_by == "vendor":
            return sorted(docs, key=lambda x: (x["vendor_name"], -x["total_amount"]))
        elif sort_by == "amount":
            return sorted(docs, key=lambda x: x["total_amount"], reverse=True)
        elif sort_by == "status":
            return sorted(docs, key=lambda x: (x["payment_status"], x["invoice_date"]), reverse=True)
        else:  # default date
            return sorted(docs, key=lambda x: x["invoice_date"], reverse=True)

    def generate_month_end_reconciliation(self) -> Dict[str, Any]:
        """
        Builds an executive month-end audit pack:
        - Category breakdown with percentages
        - Vendor concentration breakdown
        - Accounts Payable aging schedule
        - Tax-deductible expense summary
        """
        summary = self.db.get_business_month_end_summary()
        stats = summary["stats"]
        total_exp = stats.get("total_expenses", 0.0)

        # Add percentage to categories
        categories = []
        for c in summary["by_category"]:
            c_amt = c["total_amount"]
            pct = round((c_amt / total_exp * 100), 1) if total_exp > 0 else 0.0
            categories.append({**c, "percentage": pct})

        # Separate accounts payable
        all_docs = self.db.get_business_documents(limit=300)
        pending_bills = [d for d in all_docs if d.get("payment_status") == "PENDING"]
        paid_bills = [d for d in all_docs if d.get("payment_status") == "PAID"]
        overdue_bills = [d for d in all_docs if d.get("payment_status") == "OVERDUE"]

        return {
            "stats": stats,
            "total_expenses": total_exp,
            "total_tax_deductible": stats.get("total_tax_deductible", 0.0),
            "total_tax_paid": stats.get("total_tax_paid", 0.0),
            "pending_payables": stats.get("pending_payables", 0.0),
            "overdue_payables": stats.get("overdue_payables", 0.0),
            "by_category": categories,
            "by_vendor": summary["by_vendor"],
            "pending_bills": pending_bills,
            "paid_bills": paid_bills,
            "overdue_bills": overdue_bills,
            "total_bills_sorted": len(all_docs)
        }
