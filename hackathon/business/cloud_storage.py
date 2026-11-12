"""
Cloud Storage Manager — membership tiers, document vault, name+date indexing.
Stores file blobs in SQLite for demo; ready to swap to S3/GCS with real credentials.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import List, Dict, Any, Optional


TIERS: Dict[str, Dict[str, Any]] = {
    "FREE": {
        "price": 0.0,
        "quota_mb": 50,
        "label": "Free (Local Only)",
        "features": ["Up to 50 MB local storage", "Manual document sorting", "Basic export"],
    },
    "STANDARD": {
        "price": 4.99,
        "quota_mb": 2_000,
        "label": "Standard Cloud — $4.99/mo",
        "features": [
            "2 GB cloud storage",
            "Auto-sorted by name & date",
            "Month-end document index in PDF",
            "Search by filename",
        ],
    },
    "BUSINESS": {
        "price": 9.99,
        "quota_mb": 10_000,
        "label": "Business Cloud — $9.99/mo",
        "features": [
            "10 GB cloud storage",
            "All Standard features",
            "Unlimited document history",
            "QuickBooks / Xero CSV sync",
            "Priority AI reconciliation",
        ],
    },
}


class CloudStorageManager:
    """Manages cloud storage membership tiers and the document vault."""

    def __init__(self, db=None):
        from database.db import get_db
        self.db = db or get_db()
        self._ensure_schema()

    # ─── Schema ───────────────────────────────────────────────────────────────

    def _ensure_schema(self):
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS cloud_storage_config (
                    id INTEGER PRIMARY KEY,
                    plan_tier TEXT DEFAULT 'FREE',
                    plan_price REAL DEFAULT 0.0,
                    storage_quota_mb INTEGER DEFAULT 50,
                    used_storage_mb REAL DEFAULT 0.0,
                    enabled INTEGER DEFAULT 0,
                    updated_at TEXT NOT NULL
                );
            """)
            # Add file_data BLOB column to business_documents if not present
            try:
                c.execute("ALTER TABLE business_documents ADD COLUMN file_data BLOB;")
            except Exception:
                pass  # Column already exists
            conn.commit()
        # Seed default config row if missing
        cfg = self.get_config()
        if not cfg:
            now = datetime.now().isoformat()
            with self.db.get_connection() as conn:
                conn.cursor().execute(
                    "INSERT INTO cloud_storage_config (id, plan_tier, plan_price, storage_quota_mb, used_storage_mb, enabled, updated_at) VALUES (1, 'FREE', 0.0, 50, 0.0, 0, ?);",
                    (now,),
                )
                conn.commit()

    # ─── Config Methods ───────────────────────────────────────────────────────

    def get_config(self) -> Optional[Dict[str, Any]]:
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM cloud_storage_config WHERE id = 1;")
            row = c.fetchone()
            return dict(row) if row else None

    def upgrade_tier(self, new_tier: str) -> Dict[str, Any]:
        """Upgrade (or downgrade) the cloud storage membership tier."""
        new_tier = new_tier.upper()
        if new_tier not in TIERS:
            return {"success": False, "error": f"Unknown tier '{new_tier}'. Choose FREE, STANDARD, or BUSINESS."}
        tier_info = TIERS[new_tier]
        now = datetime.now().isoformat()
        with self.db.get_connection() as conn:
            conn.cursor().execute(
                """UPDATE cloud_storage_config
                   SET plan_tier = ?, plan_price = ?, storage_quota_mb = ?, enabled = ?, updated_at = ?
                   WHERE id = 1;""",
                (new_tier, tier_info["price"], tier_info["quota_mb"], 0 if new_tier == "FREE" else 1, now),
            )
            conn.commit()
        return {
            "success": True,
            "tier": new_tier,
            "label": tier_info["label"],
            "price": tier_info["price"],
            "quota_mb": tier_info["quota_mb"],
        }

    def get_storage_usage_mb(self) -> float:
        """Sum of all stored file_data blobs (in MB)."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT COALESCE(SUM(LENGTH(file_data)), 0) FROM business_documents WHERE file_data IS NOT NULL;")
            row = c.fetchone()
            bytes_used = row[0] if row else 0
        return round(bytes_used / (1024 * 1024), 4)

    # ─── Upload / Store ───────────────────────────────────────────────────────

    def upload_document(
        self,
        doc_id: int,
        file_bytes: bytes,
        filename: str,
    ) -> Dict[str, Any]:
        """
        Attach file bytes to an existing business_document row.
        In demo mode this stores bytes in SQLite BLOB.
        Real cloud: swap to boto3 / GCS client.
        """
        cfg = self.get_config()
        if not cfg or cfg["plan_tier"] == "FREE":
            return {
                "success": False,
                "error": "Cloud storage requires STANDARD or BUSINESS tier. Upgrade your plan.",
            }
        now = datetime.now().isoformat()
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute(
                "UPDATE business_documents SET file_data = ?, document_name = ?, upload_date = ? WHERE id = ?;",
                (file_bytes, filename, now[:10], doc_id),
            )
            conn.commit()
            affected = c.rowcount

        # Recalculate usage
        used = self.get_storage_usage_mb()
        with self.db.get_connection() as conn:
            conn.cursor().execute(
                "UPDATE cloud_storage_config SET used_storage_mb = ?, updated_at = ? WHERE id = 1;",
                (used, now),
            )
            conn.commit()

        return {
            "success": affected > 0,
            "doc_id": doc_id,
            "filename": filename,
            "size_kb": round(len(file_bytes) / 1024, 2),
            "used_mb": used,
        }

    # ─── Retrieval ────────────────────────────────────────────────────────────

    def list_by_month(self, year: int, month: int) -> List[Dict[str, Any]]:
        """
        Return documents whose upload_date falls in year/month,
        sorted by document_name ASC then upload_date DESC.
        """
        month_prefix = f"{year:04d}-{month:02d}"
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute(
                """SELECT id, document_name, upload_date, document_type, vendor_name,
                          invoice_number, invoice_date, total_amount, category,
                          payment_status,
                          CASE WHEN file_data IS NOT NULL THEN 1 ELSE 0 END as has_file
                   FROM business_documents
                   WHERE upload_date LIKE ?
                   ORDER BY document_name ASC, upload_date DESC;""",
                (f"{month_prefix}%",),
            )
            return [dict(r) for r in c.fetchall()]

    def list_all(self) -> List[Dict[str, Any]]:
        """All documents sorted by name then upload date (most recent first)."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute(
                """SELECT id, document_name, upload_date, document_type, vendor_name,
                          invoice_number, invoice_date, total_amount, category,
                          payment_status,
                          CASE WHEN file_data IS NOT NULL THEN 1 ELSE 0 END as has_file
                   FROM business_documents
                   ORDER BY document_name ASC, upload_date DESC;"""
            )
            return [dict(r) for r in c.fetchall()]

    def search_by_name(self, query: str) -> List[Dict[str, Any]]:
        """Partial case-insensitive match on document_name or vendor_name."""
        pattern = f"%{query.lower()}%"
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute(
                """SELECT id, document_name, upload_date, document_type, vendor_name,
                          invoice_number, invoice_date, total_amount, category,
                          payment_status,
                          CASE WHEN file_data IS NOT NULL THEN 1 ELSE 0 END as has_file
                   FROM business_documents
                   WHERE LOWER(document_name) LIKE ?
                      OR LOWER(vendor_name) LIKE ?
                   ORDER BY document_name ASC, upload_date DESC;""",
                (pattern, pattern),
            )
            return [dict(r) for r in c.fetchall()]

    def get_file_bytes(self, doc_id: int) -> Optional[bytes]:
        """Retrieve stored file bytes for download."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute("SELECT file_data FROM business_documents WHERE id = ?;", (doc_id,))
            row = c.fetchone()
            return row[0] if row and row[0] else None

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def tier_info(tier: str) -> Dict[str, Any]:
        return TIERS.get(tier.upper(), TIERS["FREE"])

    @staticmethod
    def all_tiers() -> Dict[str, Dict[str, Any]]:
        return TIERS
