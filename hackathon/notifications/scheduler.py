"""
Automated Month-End Scheduler.
Continuously or periodically checks date criteria to automatically generate
month-end expenditure statements, create the PDF, dispatch WhatsApp messages,
and post in-app notifications to the user.
"""

import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from database.db import get_db
from reports.notifier import ReportDeliveryService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MonthEndScheduler")

class MonthEndScheduler:
    """
    Automated job runner that monitors month-end cycles and triggers
    automatic report generation and multi-channel delivery.
    """

    def __init__(self, db=None, default_whatsapp: str = "+919876543210"):
        self.db = db or get_db()
        self.delivery_service = ReportDeliveryService(db=self.db)
        self.default_whatsapp = default_whatsapp

    def is_month_end(self, current_dt: Optional[datetime] = None) -> bool:
        """
        Determines if the given date is the last day of the month or 1st of new month.
        """
        now = current_dt or datetime.now()
        # In testing or demo environments, this can also be triggered manually
        # Real logic: next day has day == 1
        from datetime import timedelta
        tomorrow = now + timedelta(days=1)
        return tomorrow.day == 1 or now.day == 1

    def run_automated_month_end_cycle(self, whatsapp_number: Optional[str] = None, force: bool = False) -> Dict[str, Any]:
        """
        Executes the automated month-end generation and delivery routine:
        1. Compiles month-end expenditure table and transaction ledger.
        2. Generates the comprehensive PDF statement.
        3. Delivers via WhatsApp (message summary + PDF attachment).
        4. Creates In-App notification with PDF download link.
        """
        target_phone = whatsapp_number or self.default_whatsapp
        now = datetime.now()
        month_label = now.strftime("%B %Y")
        
        logger.info(f"[*] Running automated month-end cycle for {month_label} (Target WhatsApp: {target_phone})...")
        
        # Check if already delivered for this month unless forced
        if not force:
            notifications = self.db.get_app_notifications(limit=50)
            already_sent = any(
                n.get("notification_type") == "MONTH_END_REPORT" and month_label in n.get("title", "")
                for n in notifications
            )
            if already_sent:
                logger.info(f"Month-end report for {month_label} has already been delivered. Skipping duplicate.")
                return {"status": "SKIPPED", "reason": f"Already delivered for {month_label}"}

        # Deliver
        account = self.db.get_account() or {}
        user_name = account.get("user_name", "Alex Morgan")
        
        delivery_res = self.delivery_service.deliver_month_end_report(
            to_whatsapp_number=target_phone,
            user_name=user_name
        )
        
        logger.info(f"[+] Automated delivery complete: PDF={delivery_res.get('pdf_path')}, WhatsApp={delivery_res.get('whatsapp', {}).get('success')}")
        return {
            "status": "DELIVERED",
            "cycle": month_label,
            "details": delivery_res
        }

    def start_polling_daemon(self, check_interval_seconds: int = 3600):
        """
        Runs an automated background loop that triggers every month-end.
        """
        logger.info(f"Starting Month-End Scheduler Daemon (checking every {check_interval_seconds}s)...")
        while True:
            if self.is_month_end():
                self.run_automated_month_end_cycle()
            time.sleep(check_interval_seconds)

if __name__ == "__main__":
    scheduler = MonthEndScheduler()
    res = scheduler.run_automated_month_end_cycle(force=True)
    print("Execution Result:", res)
