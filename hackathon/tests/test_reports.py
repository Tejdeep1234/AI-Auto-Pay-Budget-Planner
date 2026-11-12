"""
Unit tests for Month-End PDF Generator, WhatsApp Delivery, and In-App Notifications.
"""

import unittest
import os
from database.db import DatabaseManager
from database.seed_data import seed_database
from reports.pdf_generator import MonthEndReportGenerator
from reports.notifier import WhatsAppNotifier, ReportDeliveryService
from notifications.scheduler import MonthEndScheduler

class TestMonthEndReports(unittest.TestCase):
    def setUp(self):
        # Use an isolated test database
        self.db = DatabaseManager(db_path="test_reports.db")
        seed_database(self.db, force=True)

    def tearDown(self):
        if os.path.exists("test_reports.db"):
            try:
                os.remove("test_reports.db")
            except Exception:
                pass

    def test_pdf_report_generator_creates_valid_pdf(self):
        generator = MonthEndReportGenerator(output_dir="test_reports_output")
        pdf_path = generator.generate_monthly_report(user_name="Test User")
        
        self.assertTrue(os.path.exists(pdf_path))
        self.assertTrue(pdf_path.endswith(".pdf"))
        self.assertGreater(os.path.getsize(pdf_path), 5000)  # Valid PDF is at least several KB

        # Cleanup test output
        try:
            os.remove(pdf_path)
            os.rmdir("test_reports_output")
        except Exception:
            pass

    def test_whatsapp_notifier_mock_dispatch(self):
        notifier = WhatsAppNotifier()
        result = notifier.send(
            to_number="+919876543210",
            body="Test budget summary",
            pdf_path=None
        )
        self.assertTrue(result["success"])
        self.assertIn("to", result)
        self.assertEqual(result["to"], "+919876543210")

    def test_report_delivery_service_full_pipeline(self):
        service = ReportDeliveryService(db=self.db)
        delivery = service.deliver_month_end_report(
            to_whatsapp_number="+919876543210",
            user_name="Alex Morgan"
        )

        self.assertTrue(delivery["pdf_generated"])
        self.assertTrue(os.path.exists(delivery["pdf_path"]))
        self.assertTrue(delivery["whatsapp"]["success"])
        self.assertGreater(delivery["total_spent"], 0)
        self.assertGreater(delivery["transaction_count"], 0)

        # Verify In-App notification stored in database
        notifs = self.db.get_app_notifications()
        self.assertGreaterEqual(len(notifs), 1)
        self.assertIn("Month-End Report", notifs[0]["title"])
        self.assertEqual(notifs[0]["whatsapp_status"], "SENT")
        self.assertEqual(notifs[0]["pdf_path"], delivery["pdf_path"])

    def test_month_end_scheduler_cycle(self):
        scheduler = MonthEndScheduler(db=self.db, default_whatsapp="+919876543210")
        result = scheduler.run_automated_month_end_cycle(force=True)
        self.assertEqual(result["status"], "DELIVERED")
        self.assertIn("November", result["cycle"])

if __name__ == "__main__":
    unittest.main()
