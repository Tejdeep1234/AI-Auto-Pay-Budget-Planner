"""
Unit tests for SavingsAdvisor (Property 1) and Business Bill Sorter (Property 2).
"""

import unittest
import os
from database.db import DatabaseManager
from database.seed_data import seed_database
from agent.savings_advisor import SavingsAdvisor
from business.document_parser import BusinessDocumentParser
from business.sorter import BusinessBillSorter
from business.business_report_generator import BusinessReportGenerator

class TestBusinessAndSavings(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager(db_path="test_biz_savings.db")
        seed_database(self.db, force=True)

    def tearDown(self):
        if os.path.exists("test_biz_savings.db"):
            try:
                os.remove("test_biz_savings.db")
            except Exception:
                pass

    # --- Property 1: Shortfall & Ways to Save Tests ---
    def test_shortfall_detection_when_balance_is_low(self):
        subs = self.db.get_subscriptions(status="ACTIVE")
        # Available balance: $150.00, while upcoming 14-day commitments exceed $500
        analysis = SavingsAdvisor.analyze_commitments_and_shortfall(
            available_balance=150.00,
            subscriptions=subs,
            safety_threshold=300.0
        )
        self.assertTrue(analysis["has_shortfall"])
        self.assertGreater(analysis["shortfall_14d"], 0)
        self.assertIn("DEFICIT", analysis["severity"])

    def test_unwanted_payments_flagged_with_reasons(self):
        subs = self.db.get_subscriptions(status="ACTIVE")
        unwanted = SavingsAdvisor.identify_unwanted_payments(subs)
        self.assertGreater(len(unwanted), 0)
        
        # Adobe CC has 0 usage -> should be flagged
        flagged_names = [u["name"] for u in unwanted]
        self.assertTrue(any("Adobe" in n for n in flagged_names))
        self.assertTrue(any("Gym" in n for n in flagged_names))

    def test_ways_to_save_provides_actionable_strategies(self):
        subs = self.db.get_subscriptions(status="ACTIVE")
        unwanted = SavingsAdvisor.identify_unwanted_payments(subs)
        tactics = SavingsAdvisor.formulate_ways_to_save(
            available_balance=200.0,
            shortfall_14d=150.0,
            active_subs=subs,
            unwanted_payments=unwanted
        )
        self.assertGreaterEqual(len(tactics), 4)
        tactic_titles = [t["tactic"] for t in tactics]
        self.assertTrue(any("Subscription Interception" in t for t in tactic_titles))
        self.assertTrue(any("Downgrade" in t for t in tactic_titles))

    # --- Property 2: Business Bill Sorter & Ingestion Tests ---
    def test_document_parser_auto_categorizes_vendor(self):
        parsed_aws = BusinessDocumentParser.parse_document_input(
            vendor_name="Amazon Web Services",
            total_amount=320.00,
            document_name="Cloud compute invoice"
        )
        self.assertEqual(parsed_aws["category"], "IT & Software")
        self.assertEqual(parsed_aws["tax_deductible"], 1)

        parsed_fedex = BusinessDocumentParser.parse_document_input(
            vendor_name="FedEx Ground Freight",
            total_amount=175.50
        )
        self.assertEqual(parsed_fedex["category"], "Shipping & Logistics")

    def test_business_sorter_reconciliation_and_sorting(self):
        sorter = BusinessBillSorter(db=self.db)
        recon = sorter.generate_month_end_reconciliation()
        
        self.assertGreater(recon["total_bills_sorted"], 0)
        self.assertGreater(recon["total_expenses"], 0.0)
        self.assertGreater(recon["total_tax_deductible"], 0.0)
        self.assertGreater(len(recon["by_category"]), 0)

        # Test sorting
        sorted_by_cat = sorter.get_sorted_bills(sort_by="category")
        self.assertEqual(len(sorted_by_cat), recon["total_bills_sorted"])

    def test_business_report_generator_pdf_and_csv(self):
        gen = BusinessReportGenerator(output_dir="test_biz_output")
        pdf_path = gen.generate_sorted_business_pdf("Test Corp LLC")
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 1000)

        csv_str = gen.generate_sorted_csv()
        self.assertIn("Invoice Date", csv_str)
        self.assertIn("Vendor Name", csv_str)

        try:
            os.remove(pdf_path)
            os.rmdir("test_biz_output")
        except Exception:
            pass

if __name__ == "__main__":
    unittest.main()
