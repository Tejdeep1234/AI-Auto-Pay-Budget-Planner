"""
Unit tests for Cloud Storage Manager (Property 3: Cloud Membership & Document Vault).
Tests: tier upgrade, usage tracking, upload, list_by_month, search_by_name.
"""

import unittest
from datetime import datetime
from database.db import DatabaseManager
from database.seed_data import seed_database
from business.cloud_storage import CloudStorageManager, TIERS


def make_test_db():
    db = DatabaseManager(db_path=":memory:")
    seed_database(db, force=True)
    return db


class TestCloudStorageTierUpgrade(unittest.TestCase):
    def setUp(self):
        self.db = make_test_db()
        self.mgr = CloudStorageManager(db=self.db)

    def test_default_tier_is_free(self):
        cfg = self.mgr.get_config()
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["plan_tier"], "FREE")
        self.assertEqual(cfg["plan_price"], 0.0)

    def test_upgrade_to_standard(self):
        result = self.mgr.upgrade_tier("STANDARD")
        self.assertTrue(result["success"])
        self.assertEqual(result["tier"], "STANDARD")
        self.assertAlmostEqual(result["price"], 4.99)
        self.assertEqual(result["quota_mb"], TIERS["STANDARD"]["quota_mb"])
        # Confirm persisted
        cfg = self.mgr.get_config()
        self.assertEqual(cfg["plan_tier"], "STANDARD")
        self.assertEqual(cfg["enabled"], 1)

    def test_upgrade_to_business(self):
        result = self.mgr.upgrade_tier("BUSINESS")
        self.assertTrue(result["success"])
        self.assertEqual(result["tier"], "BUSINESS")
        self.assertAlmostEqual(result["price"], 9.99)
        self.assertEqual(result["quota_mb"], TIERS["BUSINESS"]["quota_mb"])

    def test_invalid_tier_returns_error(self):
        result = self.mgr.upgrade_tier("GOLD_PLAN")
        self.assertFalse(result["success"])
        self.assertIn("error", result)

    def test_downgrade_to_free_disables_cloud(self):
        self.mgr.upgrade_tier("BUSINESS")
        result = self.mgr.upgrade_tier("FREE")
        self.assertTrue(result["success"])
        cfg = self.mgr.get_config()
        self.assertEqual(cfg["plan_tier"], "FREE")
        self.assertEqual(cfg["enabled"], 0)


class TestCloudDocumentUpload(unittest.TestCase):
    def setUp(self):
        self.db = make_test_db()
        self.mgr = CloudStorageManager(db=self.db)
        self.mgr.upgrade_tier("STANDARD")

    def _first_doc_id(self):
        docs = self.mgr.list_all()
        return docs[0]["id"] if docs else None

    def test_upload_blocked_on_free_tier(self):
        self.mgr.upgrade_tier("FREE")
        doc_id = self._first_doc_id()
        result = self.mgr.upload_document(doc_id, b"test data", "test.pdf")
        self.assertFalse(result["success"])
        self.assertIn("STANDARD", result["error"])

    def test_upload_stores_and_retrieves_bytes(self):
        doc_id = self._first_doc_id()
        file_bytes = b"%PDF-1.4 fake pdf content for unit test"
        result = self.mgr.upload_document(doc_id, file_bytes, "invoice_test.pdf")
        self.assertTrue(result["success"])
        self.assertEqual(result["doc_id"], doc_id)
        # Retrieve bytes
        retrieved = self.mgr.get_file_bytes(doc_id)
        self.assertEqual(retrieved, file_bytes)

    def test_storage_usage_increases_after_upload(self):
        usage_before = self.mgr.get_storage_usage_mb()
        doc_id = self._first_doc_id()
        big_data = b"X" * (512 * 1024)  # 512 KB
        self.mgr.upload_document(doc_id, big_data, "big_file.pdf")
        usage_after = self.mgr.get_storage_usage_mb()
        self.assertGreater(usage_after, usage_before)


class TestCloudDocumentListing(unittest.TestCase):
    def setUp(self):
        self.db = make_test_db()
        self.mgr = CloudStorageManager(db=self.db)

    def test_list_all_returns_docs_sorted_by_name_then_date(self):
        docs = self.mgr.list_all()
        self.assertGreater(len(docs), 0)
        names = [d["document_name"] for d in docs]
        # Names should be in ascending order
        self.assertEqual(names, sorted(names))

    def test_list_by_month_filters_correctly(self):
        now = datetime.now()
        # Seeded docs have dates spread across current month; at least some should match
        docs = self.mgr.list_by_month(now.year, now.month)
        # Every returned doc's upload_date must be in this month
        prefix = f"{now.year:04d}-{now.month:02d}"
        for d in docs:
            self.assertTrue(
                d["upload_date"].startswith(prefix),
                f"Doc {d['document_name']} has upload_date {d['upload_date']} outside {prefix}"
            )

    def test_list_by_month_nonexistent_returns_empty(self):
        docs = self.mgr.list_by_month(1999, 1)
        self.assertEqual(docs, [])

    def test_search_by_name_partial_match(self):
        # Seed has "AWS Cloud Infrastructure" and "Amazon Web Services" vendor
        results = self.mgr.search_by_name("aws")
        self.assertGreater(len(results), 0)

    def test_search_by_vendor_name(self):
        results = self.mgr.search_by_name("fedex")
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("fedex", r["vendor_name"].lower())

    def test_search_by_nonexistent_name_returns_empty(self):
        results = self.mgr.search_by_name("ZZZZZZ_NOBODY")
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
