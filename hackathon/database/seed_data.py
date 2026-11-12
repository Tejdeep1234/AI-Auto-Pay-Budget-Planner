"""
Seed realistic demonstration data for Smart Auto-Pay & Balance Budget Planner.
"""

from datetime import datetime, timedelta
from database.db import DatabaseManager

def seed_database(db: DatabaseManager, force: bool = False):
    account = db.get_account()
    if account and not force:
        return  # Already seeded

    today = datetime.now()
    now_str = today.isoformat()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Clean existing data if force
        if force:
            cursor.execute("DELETE FROM accounts;")
            cursor.execute("DELETE FROM subscriptions;")
            cursor.execute("DELETE FROM agent_actions;")
            cursor.execute("DELETE FROM webhook_logs;")
            cursor.execute("DELETE FROM cashflow_events;")
            cursor.execute("DELETE FROM monthly_transactions;")
            cursor.execute("DELETE FROM app_notifications;")
            cursor.execute("DELETE FROM business_documents;")

        # 1. Initialize Account
        # Starting balance is close to safety threshold to showcase threshold alerts
        cursor.execute("""
            INSERT INTO accounts (id, user_name, balance, safety_threshold, overdraft_buffer, currency, autonomous_mode, updated_at)
            VALUES (1, 'Alex Morgan', 345.50, 300.00, 100.00, 'USD', 0, ?);
        """, (now_str,))

        # 2. Add realistic Subscriptions
        # Subscriptions have varying billing dates over the next 14 days
        sample_subs = [
            {
                "id": "I-ADOBECC9921",
                "name": "Adobe Creative Cloud",
                "vendor": "Adobe Inc.",
                "category": "Software & Productivity",
                "amount": 54.99,
                "billing_cycle": "MONTHLY",
                "next_billing_date": (today + timedelta(days=2)).strftime("%Y-%m-%d"),
                "status": "ACTIVE",
                "usage_days_last_30": 0,
                "hours_used_last_30": 0.0,
                "essentiality": "luxury",
                "user_priority": 1,
                "auto_pause_eligible": 1,
                "paypal_plan_id": "P-7889ADOBE"
            },
            {
                "id": "I-FITNESSEX28",
                "name": "Metro Elite Gym Membership",
                "vendor": "Metro Fitness LLC",
                "category": "Fitness & Health",
                "amount": 89.00,
                "billing_cycle": "MONTHLY",
                "next_billing_date": (today + timedelta(days=4)).strftime("%Y-%m-%d"),
                "status": "ACTIVE",
                "usage_days_last_30": 1,
                "hours_used_last_30": 1.2,
                "essentiality": "negotiable",
                "user_priority": 2,
                "auto_pause_eligible": 1,
                "paypal_plan_id": "P-4421GYM"
            },
            {
                "id": "I-MEALKITBOX12",
                "name": "Gourmet Meal Kit Subscription",
                "vendor": "FreshTable Delivery",
                "category": "Food & Dining",
                "amount": 79.99,
                "billing_cycle": "MONTHLY",
                "next_billing_date": (today + timedelta(days=6)).strftime("%Y-%m-%d"),
                "status": "ACTIVE",
                "usage_days_last_30": 2,
                "hours_used_last_30": 3.0,
                "essentiality": "negotiable",
                "user_priority": 2,
                "auto_pause_eligible": 1,
                "paypal_plan_id": "P-9932FOOD"
            },
            {
                "id": "I-NETFLIX4K88",
                "name": "Netflix Premium 4K",
                "vendor": "Netflix Inc.",
                "category": "Entertainment & Streaming",
                "amount": 22.99,
                "billing_cycle": "MONTHLY",
                "next_billing_date": (today + timedelta(days=5)).strftime("%Y-%m-%d"),
                "status": "ACTIVE",
                "usage_days_last_30": 24,
                "hours_used_last_30": 42.5,
                "essentiality": "negotiable",
                "user_priority": 4,
                "auto_pause_eligible": 1,
                "paypal_plan_id": "P-1123NFLX"
            },
            {
                "id": "I-SPOTIFYFAM4",
                "name": "Spotify Family Plan",
                "vendor": "Spotify AB",
                "category": "Entertainment & Streaming",
                "amount": 16.99,
                "billing_cycle": "MONTHLY",
                "next_billing_date": (today + timedelta(days=8)).strftime("%Y-%m-%d"),
                "status": "ACTIVE",
                "usage_days_last_30": 29,
                "hours_used_last_30": 68.0,
                "essentiality": "negotiable",
                "user_priority": 4,
                "auto_pause_eligible": 1,
                "paypal_plan_id": "P-5561SPOT"
            },
            {
                "id": "I-CLOUDHOST33",
                "name": "Cloud Server & Database Backup",
                "vendor": "DigitalOcean / AWS",
                "category": "Developer & Infrastructure",
                "amount": 42.00,
                "billing_cycle": "MONTHLY",
                "next_billing_date": (today + timedelta(days=9)).strftime("%Y-%m-%d"),
                "status": "ACTIVE",
                "usage_days_last_30": 30,
                "hours_used_last_30": 720.0,
                "essentiality": "essential",
                "user_priority": 5,
                "auto_pause_eligible": 0,
                "paypal_plan_id": "P-8822DOAWS"
            },
            {
                "id": "I-PSPLUSPREM1",
                "name": "PlayStation Plus Deluxe",
                "vendor": "Sony Interactive",
                "category": "Gaming",
                "amount": 17.99,
                "billing_cycle": "MONTHLY",
                "next_billing_date": (today + timedelta(days=3)).strftime("%Y-%m-%d"),
                "status": "ACTIVE",
                "usage_days_last_30": 2,
                "hours_used_last_30": 2.5,
                "essentiality": "luxury",
                "user_priority": 2,
                "auto_pause_eligible": 1,
                "paypal_plan_id": "P-3344PSPLUS"
            },
            {
                "id": "I-POWERUTIL77",
                "name": "City Municipal Power Autopay",
                "vendor": "City Power & Light",
                "category": "Utilities",
                "amount": 115.00,
                "billing_cycle": "MONTHLY",
                "next_billing_date": (today + timedelta(days=11)).strftime("%Y-%m-%d"),
                "status": "ACTIVE",
                "usage_days_last_30": 30,
                "hours_used_last_30": 720.0,
                "essentiality": "essential",
                "user_priority": 5,
                "auto_pause_eligible": 0,
                "paypal_plan_id": "P-UTIL001"
            }
        ]

        for sub in sample_subs:
            cursor.execute("""
                INSERT INTO subscriptions (
                    id, name, vendor, category, amount, billing_cycle,
                    next_billing_date, status, usage_days_last_30, hours_used_last_30,
                    essentiality, user_priority, auto_pause_eligible, paypal_plan_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                sub["id"], sub["name"], sub["vendor"], sub["category"],
                sub["amount"], sub["billing_cycle"], sub["next_billing_date"],
                sub["status"], sub["usage_days_last_30"], sub["hours_used_last_30"],
                sub["essentiality"], sub["user_priority"], sub["auto_pause_eligible"],
                sub["paypal_plan_id"], now_str, now_str
            ))

        # 3. Add Scheduled Cashflow events (Upcoming Paycheck)
        cursor.execute("""
            INSERT INTO cashflow_events (title, event_type, amount, expected_date, is_recurring, created_at)
            VALUES 
            ('Direct Deposit Paycheck', 'INCOME', 1850.00, ?, 1, ?),
            ('Vehicle Insurance Autopay', 'EXPENSE', 120.00, ?, 1, ?);
        """, (
            (today + timedelta(days=12)).strftime("%Y-%m-%d"), now_str,
            (today + timedelta(days=13)).strftime("%Y-%m-%d"), now_str
        ))

        # 4. Seed an initial informative agent log entry
        cursor.execute("""
            INSERT INTO agent_actions (
                action_type, subscription_id, trigger_reason,
                projected_balance_before, projected_balance_after,
                savings_amount, user_status, ai_explanation, created_at
            ) VALUES (
                'INITIAL_AUDIT', NULL, 'Baseline account scan initialized',
                345.50, 345.50, 0.00, 'SYSTEM',
                'AI Agent initialized active monitoring. Safety Threshold set to $300.00, Overdraft Buffer at $100.00.',
                ?
            );
        """, (now_str,))

        # 5. Seed realistic Monthly Transactions (for Month-End Expenditure Report)
        sample_transactions = [
            ("Whole Foods Market", "Groceries", 142.30, "PayPal Card", today - timedelta(days=26)),
            ("Trader Joe's", "Groceries", 88.45, "Debit Card", today - timedelta(days=22)),
            ("Costco Wholesale", "Groceries", 195.10, "Debit Card", today - timedelta(days=12)),
            ("City Power & Light", "Utilities", 115.00, "PayPal Autopay", today - timedelta(days=28)),
            ("AT&T Fiber Internet", "Utilities", 70.00, "PayPal Autopay", today - timedelta(days=20)),
            ("DigitalOcean / AWS Cloud", "Developer & SaaS", 42.00, "PayPal Autopay", today - timedelta(days=19)),
            ("Netflix Premium", "Entertainment", 22.99, "PayPal Autopay", today - timedelta(days=25)),
            ("Spotify Family", "Entertainment", 16.99, "PayPal Autopay", today - timedelta(days=21)),
            ("PlayStation Network", "Entertainment", 17.99, "PayPal Autopay", today - timedelta(days=27)),
            ("Shell Oil Station", "Transportation", 48.50, "Debit Card", today - timedelta(days=24)),
            ("Uber Technologies", "Transportation", 34.20, "PayPal", today - timedelta(days=16)),
            ("Chevron Gas", "Transportation", 52.10, "Debit Card", today - timedelta(days=8)),
            ("Chipotle Mexican Grill", "Dining & Coffee", 18.75, "PayPal", today - timedelta(days=23)),
            ("Starbucks Reserve", "Dining & Coffee", 14.50, "PayPal Card", today - timedelta(days=18)),
            ("Sweetgreen", "Dining & Coffee", 21.30, "Debit Card", today - timedelta(days=14)),
            ("Panera Bread", "Dining & Coffee", 16.80, "PayPal", today - timedelta(days=5)),
            ("CVS Pharmacy", "Healthcare", 38.60, "Debit Card", today - timedelta(days=15)),
            ("Target Superstore", "Household & Shopping", 84.90, "Debit Card", today - timedelta(days=11)),
            ("Home Depot", "Household & Shopping", 62.40, "PayPal Card", today - timedelta(days=7))
        ]

        for merchant, cat, amt, method, tx_date in sample_transactions:
            cursor.execute("""
                INSERT INTO monthly_transactions (
                    transaction_date, merchant, category, amount, payment_method, status, created_at
                ) VALUES (?, ?, ?, ?, ?, 'COMPLETED', ?);
            """, (tx_date.strftime("%Y-%m-%d"), merchant, cat, amt, method, now_str))

        # 6. Seed realistic Daily Business Invoices & Bills (for Small/Big Business Auto-Sorting)
        sample_business_bills = [
            ("Raw Material Batch #401", "INVOICE", "Acme Industrial Supplies", "INV-2026-9901", 1250.00, 100.00, 1350.00, "Inventory & COGS", "PAID", 1, today - timedelta(days=27)),
            ("Monthly Office Lease - Suite 400", "INVOICE", "Commercial Realty Partners", "LEASE-NOV-40", 2200.00, 0.00, 2200.00, "Facilities & Rent", "PAID", 1, today - timedelta(days=26)),
            ("AWS Cloud Infrastructure", "INVOICE", "Amazon Web Services", "AWS-882190-NOV", 430.50, 34.44, 464.94, "IT & Software", "PAID", 1, today - timedelta(days=24)),
            ("Pallet Logistics & Freight", "INVOICE", "FedEx Freight Services", "FDX-77412", 380.00, 22.80, 402.80, "Shipping & Logistics", "PAID", 1, today - timedelta(days=21)),
            ("Google Workspace Enterprise (25 seats)", "INVOICE", "Google LLC", "GW-99410-ENT", 450.00, 0.00, 450.00, "IT & Software", "PAID", 1, today - timedelta(days=19)),
            ("Packaging Materials & Cartons", "INVOICE", "Pacific Packaging Ltd", "PAC-3392", 640.00, 51.20, 691.20, "Inventory & COGS", "PAID", 1, today - timedelta(days=17)),
            ("Commercial High-Speed Fiber Internet", "UTILITY_BILL", "AT&T Business Telecom", "ATT-BIZ-551", 210.00, 16.80, 226.80, "Utilities", "PAID", 1, today - timedelta(days=15)),
            ("Meta Ads Lead Campaign", "INVOICE", "Meta Platforms Inc", "META-ADS-9912", 520.00, 0.00, 520.00, "Marketing & Advertising", "PAID", 1, today - timedelta(days=13)),
            ("CPA Tax Compliance & Bookkeeping", "INVOICE", "Vanguard Accounting LLP", "VAN-2026-112", 750.00, 60.00, 810.00, "Professional Services", "PAID", 1, today - timedelta(days=10)),
            ("Industrial Safety Equipment & Gloves", "RECEIPT", "Grainger Industrial Supplies", "GRA-88129", 185.00, 14.80, 199.80, "Office & Equipment", "PAID", 1, today - timedelta(days=7)),
            ("Quarterly Commercial Insurance", "INVOICE", "Hartford Business Insurance", "HART-BIZ-889", 850.00, 0.00, 850.00, "Insurance & Legal", "PENDING", 1, today - timedelta(days=4)),
            ("Commercial Printing & Brochures", "INVOICE", "SpeedyPrint Commercial", "PRNT-4491", 290.00, 23.20, 313.20, "Marketing & Advertising", "PENDING", 1, today - timedelta(days=2))
        ]

        for doc_name, doc_type, vendor, inv_num, subtotal, tax, total, cat, status, deductible, dt in sample_business_bills:
            cursor.execute("""
                INSERT INTO business_documents (
                    document_name, file_path, upload_date, document_type,
                    vendor_name, invoice_number, invoice_date, due_date,
                    subtotal, tax_amount, total_amount, currency, category,
                    payment_status, tax_deductible, extracted_notes, created_at
                ) VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'USD', ?, ?, ?, 'Auto-parsed from daily business document ingestion', ?);
            """, (
                doc_name, dt.strftime("%Y-%m-%d"), doc_type, vendor, inv_num,
                dt.strftime("%Y-%m-%d"), (dt + timedelta(days=30)).strftime("%Y-%m-%d"),
                subtotal, tax, total, cat, status, deductible, now_str
            ))

        conn.commit()

if __name__ == "__main__":
    db = DatabaseManager()
    seed_database(db, force=True)
    print("Database successfully seeded with realistic subscriptions and account balance!")
