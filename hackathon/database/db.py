"""
SQLite Database Manager for accounts, subscriptions, cashflow forecast, and agent logs.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from config import DB_PATH

class DatabaseManager:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._mem_conn = None
        if self.db_path == ":memory:":
            self._mem_conn = sqlite3.connect(":memory:")
            self._mem_conn.row_factory = sqlite3.Row
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        if self._mem_conn is not None:
            return self._mem_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Creates tables if they don't exist."""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Account & Thresholds table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT NOT NULL,
                balance REAL NOT NULL,
                safety_threshold REAL NOT NULL,
                overdraft_buffer REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                autonomous_mode INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """)

            # Subscriptions table (mirrored with PayPal)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                vendor TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                billing_cycle TEXT NOT NULL,
                next_billing_date TEXT NOT NULL,
                status TEXT NOT NULL,
                usage_days_last_30 INTEGER DEFAULT 0,
                hours_used_last_30 REAL DEFAULT 0.0,
                essentiality TEXT NOT NULL,
                user_priority INTEGER DEFAULT 3,
                auto_pause_eligible INTEGER DEFAULT 1,
                paypal_plan_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # Agent Actions & Audit Log table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agent_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                subscription_id TEXT,
                trigger_reason TEXT NOT NULL,
                projected_balance_before REAL,
                projected_balance_after REAL,
                savings_amount REAL,
                user_status TEXT NOT NULL,
                ai_explanation TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (subscription_id) REFERENCES subscriptions (id)
            );
            """)

            # Webhook Events table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS webhook_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                summary TEXT,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                processed_at TEXT NOT NULL
            );
            """)

            # Cashflow & Upcoming Events table (Income, Recurring bills, etc.)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cashflow_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                event_type TEXT NOT NULL,
                amount REAL NOT NULL,
                expected_date TEXT NOT NULL,
                is_recurring INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """)

            # Monthly Transactions table (for month-end expenditure ledger)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS monthly_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_date TEXT NOT NULL,
                merchant TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                payment_method TEXT DEFAULT 'PayPal',
                status TEXT DEFAULT 'COMPLETED',
                subscription_id TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # In-App Notifications table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS app_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                notification_type TEXT NOT NULL,
                pdf_path TEXT,
                whatsapp_status TEXT DEFAULT 'PENDING',
                is_read INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """)

            # Business Daily Invoices, Bills & Documents Table (for automated sorting & month-end reconciliation)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_name TEXT NOT NULL,
                file_path TEXT,
                upload_date TEXT NOT NULL,
                document_type TEXT DEFAULT 'INVOICE',
                vendor_name TEXT NOT NULL,
                invoice_number TEXT,
                invoice_date TEXT NOT NULL,
                due_date TEXT,
                subtotal REAL DEFAULT 0.0,
                tax_amount REAL DEFAULT 0.0,
                total_amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                category TEXT NOT NULL,
                payment_status TEXT DEFAULT 'PAID',
                tax_deductible INTEGER DEFAULT 1,
                extracted_notes TEXT,
                created_at TEXT NOT NULL
            );
            """)

            conn.commit()

    # --- Account Methods ---
    def get_account(self) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM accounts LIMIT 1;")
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_balance(self, new_balance: float) -> float:
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE accounts SET balance = ?, updated_at = ? WHERE id = 1;", (new_balance, now))
            conn.commit()
        return new_balance

    def update_thresholds(self, safety_threshold: float, overdraft_buffer: float, autonomous_mode: bool):
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE accounts 
                SET safety_threshold = ?, overdraft_buffer = ?, autonomous_mode = ?, updated_at = ?
                WHERE id = 1;
            """, (safety_threshold, overdraft_buffer, 1 if autonomous_mode else 0, now))
            conn.commit()

    # --- Subscription Methods ---
    def get_subscriptions(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM subscriptions WHERE status = ? ORDER BY amount DESC;", (status,))
            else:
                cursor.execute("SELECT * FROM subscriptions ORDER BY amount DESC;")
            return [dict(row) for row in cursor.fetchall()]

    def get_subscription(self, sub_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM subscriptions WHERE id = ?;", (sub_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_subscription_status(self, sub_id: str, new_status: str) -> bool:
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE subscriptions SET status = ?, updated_at = ? WHERE id = ?;", (new_status, now, sub_id))
            conn.commit()
            return cursor.rowcount > 0

    def add_subscription(self, sub: Dict[str, Any]) -> str:
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO subscriptions (
                    id, name, vendor, category, amount, billing_cycle,
                    next_billing_date, status, usage_days_last_30, hours_used_last_30,
                    essentiality, user_priority, auto_pause_eligible, paypal_plan_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                sub["id"], sub["name"], sub["vendor"], sub["category"],
                sub["amount"], sub["billing_cycle"], sub["next_billing_date"],
                sub.get("status", "ACTIVE"), sub.get("usage_days_last_30", 0),
                sub.get("hours_used_last_30", 0.0), sub.get("essentiality", "negotiable"),
                sub.get("user_priority", 3), sub.get("auto_pause_eligible", 1),
                sub.get("paypal_plan_id", "P-MOCK"),
                sub.get("created_at", now), now
            ))
            conn.commit()
            return sub["id"]

    # --- Agent Action Logging ---
    def log_agent_action(self, action: Dict[str, Any]) -> int:
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO agent_actions (
                    action_type, subscription_id, trigger_reason,
                    projected_balance_before, projected_balance_after,
                    savings_amount, user_status, ai_explanation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                action["action_type"],
                action.get("subscription_id"),
                action["trigger_reason"],
                action.get("projected_balance_before", 0.0),
                action.get("projected_balance_after", 0.0),
                action.get("savings_amount", 0.0),
                action.get("user_status", "PROPOSED"),
                action.get("ai_explanation", ""),
                now
            ))
            conn.commit()
            return cursor.lastrowid

    def get_agent_actions(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.*, s.name as subscription_name, s.vendor as subscription_vendor
                FROM agent_actions a
                LEFT JOIN subscriptions s ON a.subscription_id = s.id
                ORDER BY a.id DESC LIMIT ?;
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def update_action_status(self, action_id: int, new_status: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE agent_actions SET user_status = ? WHERE id = ?;", (new_status, action_id))
            conn.commit()

    # --- Webhook Logs ---
    def log_webhook_event(self, event_id: str, event_type: str, summary: str, payload: Dict[str, Any], status: str = "PROCESSED"):
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO webhook_logs (event_id, event_type, summary, payload, status, processed_at)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (event_id, event_type, summary, json.dumps(payload), status, now))
            conn.commit()

    def get_webhook_logs(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM webhook_logs ORDER BY id DESC LIMIT ?;", (limit,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                d = dict(r)
                try:
                    d["payload"] = json.loads(d["payload"])
                except Exception:
                    pass
                results.append(d)
            return results

    # --- Cashflow Events ---
    def get_cashflow_events(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cashflow_events ORDER BY expected_date ASC;")
            return [dict(row) for row in cursor.fetchall()]

    def add_cashflow_event(self, event: Dict[str, Any]):
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO cashflow_events (title, event_type, amount, expected_date, is_recurring, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (
                event["title"], event["event_type"], event["amount"],
                event["expected_date"], event.get("is_recurring", 0), now
            ))
            conn.commit()

    # --- Monthly Transactions & Expenditure Table Methods ---
    def get_monthly_transactions(self, limit: int = 100) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM monthly_transactions ORDER BY transaction_date DESC, id DESC LIMIT ?;", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def add_transaction(self, tx: Dict[str, Any]) -> int:
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO monthly_transactions (
                    transaction_date, merchant, category, amount, payment_method, status, subscription_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                tx["transaction_date"], tx["merchant"], tx["category"],
                tx["amount"], tx.get("payment_method", "PayPal"),
                tx.get("status", "COMPLETED"), tx.get("subscription_id"), now
            ))
            conn.commit()
            return cursor.lastrowid

    def get_expenditure_by_category(self) -> List[Dict[str, Any]]:
        """Aggregates monthly transactions into an expenditure summary table."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    category,
                    COUNT(id) as transaction_count,
                    SUM(amount) as total_spent,
                    ROUND(AVG(amount), 2) as avg_transaction
                FROM monthly_transactions
                GROUP BY category
                ORDER BY total_spent DESC;
            """)
            return [dict(row) for row in cursor.fetchall()]

    # --- In-App Notifications Methods ---
    def add_app_notification(self, title: str, message: str, notification_type: str = "MONTH_END_REPORT", pdf_path: Optional[str] = None, whatsapp_status: str = "SENT") -> int:
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO app_notifications (title, message, notification_type, pdf_path, whatsapp_status, is_read, created_at)
                VALUES (?, ?, ?, ?, ?, 0, ?);
            """, (title, message, notification_type, pdf_path, whatsapp_status, now))
            conn.commit()
            return cursor.lastrowid

    def get_app_notifications(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM app_notifications ORDER BY id DESC LIMIT ?;", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def mark_notifications_as_read(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE app_notifications SET is_read = 1 WHERE is_read = 0;")
            conn.commit()

    def get_unread_notification_count(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(id) FROM app_notifications WHERE is_read = 0;")
            row = cursor.fetchone()
            return row[0] if row else 0

    # --- Business Daily Bill & Document Management Methods ---
    def add_business_document(self, doc: Dict[str, Any]) -> int:
        now = datetime.now().isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO business_documents (
                    document_name, file_path, upload_date, document_type,
                    vendor_name, invoice_number, invoice_date, due_date,
                    subtotal, tax_amount, total_amount, currency, category,
                    payment_status, tax_deductible, extracted_notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                doc.get("document_name", "Invoice"),
                doc.get("file_path"),
                doc.get("upload_date", datetime.now().strftime("%Y-%m-%d")),
                doc.get("document_type", "INVOICE"),
                doc["vendor_name"],
                doc.get("invoice_number", f"INV-{int(datetime.now().timestamp())}"),
                doc.get("invoice_date", datetime.now().strftime("%Y-%m-%d")),
                doc.get("due_date"),
                float(doc.get("subtotal", 0.0)),
                float(doc.get("tax_amount", 0.0)),
                float(doc["total_amount"]),
                doc.get("currency", "USD"),
                doc.get("category", "General Expense"),
                doc.get("payment_status", "PAID"),
                1 if doc.get("tax_deductible", True) else 0,
                doc.get("extracted_notes", ""),
                now
            ))
            conn.commit()
            return cursor.lastrowid

    def get_business_documents(self, category: Optional[str] = None, vendor: Optional[str] = None, payment_status: Optional[str] = None, limit: int = 150) -> List[Dict[str, Any]]:
        query = "SELECT * FROM business_documents WHERE 1=1"
        params = []
        if category and category != "All":
            query += " AND category = ?"
            params.append(category)
        if vendor and vendor != "All":
            query += " AND vendor_name = ?"
            params.append(vendor)
        if payment_status and payment_status != "All":
            query += " AND payment_status = ?"
            params.append(payment_status)
        query += " ORDER BY invoice_date DESC, id DESC LIMIT ?"
        params.append(limit)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_business_month_end_summary(self) -> Dict[str, Any]:
        """
        Calculates month-end aggregation for business bills:
        - Total gross expense
        - Total tax deductible amount
        - Total pending/unpaid accounts payable
        - Breakdown by category
        - Breakdown by vendor
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Totals
            cursor.execute("""
                SELECT 
                    COUNT(id) as total_bills,
                    COALESCE(SUM(total_amount), 0.0) as total_expenses,
                    COALESCE(SUM(CASE WHEN tax_deductible = 1 THEN total_amount ELSE 0 END), 0.0) as total_tax_deductible,
                    COALESCE(SUM(tax_amount), 0.0) as total_tax_paid,
                    COALESCE(SUM(CASE WHEN payment_status = 'PENDING' THEN total_amount ELSE 0 END), 0.0) as pending_payables,
                    COALESCE(SUM(CASE WHEN payment_status = 'OVERDUE' THEN total_amount ELSE 0 END), 0.0) as overdue_payables
                FROM business_documents;
            """)
            summary_stats = dict(cursor.fetchone() or {})

            # Category breakdown
            cursor.execute("""
                SELECT 
                    category,
                    COUNT(id) as doc_count,
                    SUM(total_amount) as total_amount,
                    ROUND(AVG(total_amount), 2) as avg_amount
                FROM business_documents
                GROUP BY category
                ORDER BY total_amount DESC;
            """)
            by_category = [dict(row) for row in cursor.fetchall()]

            # Vendor breakdown
            cursor.execute("""
                SELECT 
                    vendor_name,
                    COUNT(id) as bill_count,
                    SUM(total_amount) as total_amount,
                    MAX(invoice_date) as latest_bill_date
                FROM business_documents
                GROUP BY vendor_name
                ORDER BY total_amount DESC;
            """)
            by_vendor = [dict(row) for row in cursor.fetchall()]

            return {
                "stats": summary_stats,
                "by_category": by_category,
                "by_vendor": by_vendor
            }


_db_instance = None

def get_db() -> DatabaseManager:
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
