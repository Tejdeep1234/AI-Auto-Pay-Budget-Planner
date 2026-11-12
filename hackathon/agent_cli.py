"""
Command Line Interface (CLI) for The Smart Auto-Pay & Balance Budget Planner.
Enables command-line monitoring, what-if simulations, and PayPal controls.
"""

import sys
import argparse
from datetime import datetime

# Configure UTF-8 output encoding for Windows terminal compatibility
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from database.db import get_db
from database.seed_data import seed_database
from paypal.client import PayPalClient
from paypal.webhook_handler import PayPalWebhookHandler
from agent.brain import AgentBrain

def print_banner():
    print("=" * 70)
    print("[*] THE SMART AUTO-PAY & BALANCE BUDGET PLANNER AI AGENT")
    print("=" * 70)

def cmd_scan(args, brain, db):
    print("\n🔍 Running AI Account Threshold & Cashflow Evaluation...\n")
    res = brain.evaluate_account_thresholds(trigger_event="CLI Manual Scan")
    acc = res["account"]
    fc = res["forecast"]

    print(f"• Current Balance:   ${acc['balance']:.2f}")
    print(f"• Safety Threshold:  ${acc['safety_threshold']:.2f}")
    print(f"• Overdraft Buffer:  ${acc['overdraft_buffer']:.2f}")
    print(f"• 14-Day Lowest Bal: ${fc['lowest_projected_balance']:.2f} (on {fc['lowest_balance_date']})")
    print(f"• Overdraft Risk:    {fc['overdraft_risk_percentage']}%")
    print(f"• Status:            {res['status']}")

    recs = res.get("recommendations", [])
    if recs:
        print(f"\n🚨 {len(recs)} Draining Subscriptions Intercepted by AI:")
        for i, r in enumerate(recs, 1):
            print(f"  {i}. {r['subscription_name']} (${r['amount']:.2f}/mo) | Score: {r['pause_score']:.1f} | Urgency: {r['urgency_level']}")
            print(f"     Next charge in {r['days_until_billing']} days ({r['next_billing_date']})")
            print(f"     AI Reason: {r['explanation'].splitlines()[0]}")
    else:
        print("\n✅ Savings guardrails secure. No upcoming autopays breach thresholds.")

def cmd_subs(args, brain, db):
    subs = db.get_subscriptions()
    print(f"\nMonitored PayPal Subscriptions ({len(subs)} total):\n")
    print(f"{'ID':<16} {'NAME':<28} {'AMOUNT':<10} {'STATUS':<12} {'NEXT DATE':<12} {'USED (30d)'}")
    print("-" * 88)
    for s in subs:
        usage = f"{s['usage_days_last_30']}d / {s['hours_used_last_30']:.1f}h"
        print(f"{s['id']:<16} {s['name'][:26]:<28} ${s['amount']:<9.2f} {s['status']:<12} {s['next_billing_date']:<12} {usage}")

def cmd_balance(args, brain, db):
    if args.new_balance is not None:
        db.update_balance(args.new_balance)
        print(f"\nUpdated account balance to ${args.new_balance:.2f}")
        cmd_scan(args, brain, db)
    else:
        acc = db.get_account()
        print(f"\nAccount Balance: ${acc['balance']:.2f}")

def cmd_pause(args, brain, db):
    res = brain.execute_pause(args.sub_id, reason="Paused via CLI tool")
    print(f"\n⏸️ Result: {res}")

def cmd_resume(args, brain, db):
    res = brain.execute_resume(args.sub_id, reason="Resumed via CLI tool")
    print(f"\n▶️ Result: {res}")

def cmd_webhook_drop(args, brain, db):
    handler = PayPalWebhookHandler(agent_brain=brain, db=db)
    drop_val = args.balance
    payload = {
        "id": f"WH-CLI-{datetime.now().strftime('%H%M%S')}",
        "event_type": "CUSTOMER.BALANCE.DROPPED",
        "summary": f"PayPal Balance Alert: Available balance dropped to ${drop_val:.2f}",
        "resource": {
            "current_balance": {"currency_code": "USD", "value": str(drop_val)}
        }
    }
    print(f"\n🚀 Ingesting simulated PayPal Webhook: CUSTOMER.BALANCE.DROPPED -> ${drop_val:.2f}...")
    res = handler.process_webhook_event(payload)
    print(f"Action Taken: {res['action_taken']}")
    if res["agent_result"]:
        recs = res["agent_result"].get("recommendations", [])
        print(f"AI Agent Alert Triggered: {len(recs)} subscriptions recommended for pause!")

def cmd_ask(args, brain, db):
    query = " ".join(args.query)
    print(f"\n👤 User: {query}\n")
    reply = brain.ask_agent(query)
    print(f"🤖 AI Agent:\n{reply}\n")

def cmd_month_end(args, brain, db):
    from notifications.scheduler import MonthEndScheduler
    target_phone = args.phone or "+919876543210"
    print(f"\n📊 Triggering Automated Month-End Report Cycle (Target WhatsApp: {target_phone})...\n")
    scheduler = MonthEndScheduler(db=db, default_whatsapp=target_phone)
    res = scheduler.run_automated_month_end_cycle(whatsapp_number=target_phone, force=True)
    details = res.get("details", {})

    print(f"✅ Status: {res.get('status')}")
    print(f"📄 PDF Path: {details.get('pdf_path')}")
    print(f"💰 Total Monthly Expenditure: ${details.get('total_spent', 0):.2f} across {details.get('transaction_count', 0)} transactions")
    print(f"🛡️ AI Guardrail Savings: +${details.get('total_saved', 0):.2f} preserved")

    # Display expenditure table summary
    cats = db.get_expenditure_by_category()
    print("\n--- Month-End Expenditure Table by Category ---")
    print(f"{'CATEGORY':<24} {'TXNS':<8} {'TOTAL SPENT':<14} {'AVG TXN'}")
    print("-" * 58)
    for c in cats:
        print(f"{c['category']:<24} {c['transaction_count']:<8} ${c['total_spent']:<13.2f} ${c['avg_transaction']:.2f}")

    # WhatsApp status
    wa = details.get("whatsapp", {})
    print(f"\n📲 WhatsApp Delivery: Provider={wa.get('provider')} | Success={wa.get('success')} | To={wa.get('to')}")
    print(f"🔔 In-App Notification: Created #{details.get('in_app_notification_id')}")

def cmd_notifications(args, brain, db):
    notifs = db.get_app_notifications(limit=20)
    print(f"\n🔔 In-App Notifications ({len(notifs)} total):\n")
    for n in notifs:
        read_str = "[READ]" if n["is_read"] else "[NEW!]"
        print(f"{read_str} #{n['id']} | {n['created_at'][5:16].replace('T', ' ')} | {n['title']}")
        print(f"       Message: {n['message']}")
        if n.get("pdf_path"):
            print(f"       Attachment: {n['pdf_path']}")
        print(f"       WhatsApp Status: {n.get('whatsapp_status')}")
        print()

def cmd_shortfall(args, brain, db):
    from agent.savings_advisor import SavingsAdvisor
    acc = db.get_account() or {}
    bal = float(acc.get("balance", 0.0))
    thresh = float(acc.get("safety_threshold", 300.0))
    subs = db.get_subscriptions(status="ACTIVE")

    print("\n🔍 Evaluating Payment Commitments vs Available Balance...\n")
    res = SavingsAdvisor.analyze_commitments_and_shortfall(bal, subs, thresh)

    print(f"• Current Available Balance:   ${res['available_balance']:.2f}")
    print(f"• Payments Due in 7 Days:      ${res['total_due_7d']:.2f}")
    print(f"• Required 14-Day Commitments: ${res['total_required_14d']:.2f}")
    print(f"• Shortfall / Deficit (14d):   ${res['shortfall_14d']:.2f} ({res['severity']})")
    print(f"• Status:                      {res['status_message']}")

    unwanted = res["unwanted_payments"]
    if unwanted:
        print(f"\n🚨 {len(unwanted)} Unwanted / Dormant Payments Flagged for Immediate Pause:")
        for i, u in enumerate(unwanted, 1):
            print(f"  {i}. {u['name']} (${u['amount']:.2f}/mo) — {u['primary_reason']}")
            print(f"     Next charge: {u['next_billing_date']} | Action: {u['recommendation']}")

    print("\n💡 Actionable Ways to Save Amount:")
    for i, t in enumerate(res["ways_to_save"], 1):
        print(f"  {i}. {t['tactic']} [{t['difficulty']}] -> Potential Savings: {t['savings_estimate']}")
        print(f"     {t['description']}")
        print(f"     Impact: {t['impact']}")

def cmd_business_bills(args, brain, db):
    from business.sorter import BusinessBillSorter
    from business.business_report_generator import BusinessReportGenerator

    sorter = BusinessBillSorter(db=db)
    sort_key = args.sort or "category"
    bills = sorter.get_sorted_bills(sort_by=sort_key)
    recon = sorter.generate_month_end_reconciliation()

    print(f"\n🏢 Month-End Pre-Sorted Business Bills ({len(bills)} total bills, Sorted by: {sort_key.upper()}):\n")
    print(f"{'DATE':<12} {'VENDOR':<24} {'CATEGORY':<22} {'STATUS':<10} {'TAX':<8} {'TOTAL AMOUNT'}")
    print("-" * 88)
    for b in bills:
        print(f"{b['invoice_date']:<12} {b['vendor_name'][:22]:<24} {b['category'][:20]:<22} {b['payment_status']:<10} ${b['tax_amount']:<7.2f} ${b['total_amount']:<10.2f}")

    print("\n--- Month-End Accounting Reconciliation ---")
    print(f"• Gross Business Expense:    ${recon['total_expenses']:,.2f}")
    print(f"• 100% Tax Deductible Total: ${recon['total_tax_deductible']:,.2f}")
    print(f"• Total Tax Paid (VAT/Sales):${recon['total_tax_paid']:,.2f}")
    print(f"• Pending Accounts Payable:  ${recon['pending_payables']:,.2f}")

    if args.export:
        gen = BusinessReportGenerator()
        pdf_path = gen.generate_sorted_business_pdf()
        print(f"\n📄 Exported Official Business Reconciliation PDF: {pdf_path}")

def cmd_add_bill(args, brain, db):
    from business.document_parser import BusinessDocumentParser
    parsed = BusinessDocumentParser.parse_document_input(
        vendor_name=args.vendor,
        total_amount=args.amount,
        document_name=args.title,
        invoice_number=args.invoice,
        category=args.category,
        payment_status=args.status or "PAID"
    )
    doc_id = db.add_business_document(parsed)
    print(f"\n✅ Daily Bill Ingested & Auto-Categorized #{doc_id}:")
    print(f"   • Vendor:    {parsed['vendor_name']}")
    print(f"   • Amount:    ${parsed['total_amount']:.2f}")
    print(f"   • Category:  {parsed['category']} (Auto-Sorted!)")
    print(f"   • Status:    {parsed['payment_status']}")
    print(f"   • Due Date:  {parsed['due_date']}")
    print("   At month-end, this bill is already organized and ready for accounting/tax filing!")

def cmd_reset(args, brain, db):
    seed_database(db, force=True)
    print("\nDatabase reset to realistic demonstration data successfully!")


def cmd_cloud_storage(args, brain, db):
    from business.cloud_storage import CloudStorageManager, TIERS

    mgr = CloudStorageManager(db=db)

    # Upgrade tier
    if hasattr(args, "upgrade") and args.upgrade:
        result = mgr.upgrade_tier(args.upgrade)
        if result["success"]:
            print(f"\n✅ Cloud storage plan upgraded to: {result['label']}")
            print(f"   Monthly Price: ${result['price']:.2f}/mo")
            print(f"   Storage Quota: {result['quota_mb']:,} MB")
        else:
            print(f"\n❌ Upgrade failed: {result.get('error')}")
        return

    cfg = mgr.get_config()
    cur_tier = cfg["plan_tier"] if cfg else "FREE"
    cur_quota = cfg["storage_quota_mb"] if cfg else 50
    used_mb = mgr.get_storage_usage_mb()

    print(f"\n☁️  Cloud Storage Membership")
    print(f"   Plan:    {cur_tier} — {TIERS[cur_tier]['label']}")
    print(f"   Price:   ${TIERS[cur_tier]['price']:.2f}/mo")
    print(f"   Usage:   {used_mb:.2f} MB / {cur_quota} MB")
    print(f"   Status:  {'ACTIVE' if cfg and cfg['enabled'] else 'LOCAL ONLY'}")

    # List by month
    if hasattr(args, "month") and args.month:
        try:
            yr, mo = int(args.month[:4]), int(args.month[5:])
        except Exception:
            print(f"\n❌ Invalid month format. Use YYYY-MM (e.g. 2026-11).")
            return
        docs = mgr.list_by_month(yr, mo)
        label = f"Month: {args.month}"
    elif hasattr(args, "search") and args.search:
        docs = mgr.search_by_name(args.search)
        label = f"Search: '{args.search}'"
    else:
        docs = mgr.list_all()
        label = "All Documents"

    print(f"\n🗄️  Document Vault — {label} ({len(docs)} documents, sorted by Name → Date)")
    if docs:
        print(f"\n{'ID':<5} {'DOCUMENT NAME':<35} {'UPLOAD DATE':<13} {'VENDOR':<24} {'TOTAL':>10}  {'FILE'}")
        print("-" * 100)
        for d in docs:
            file_flag = "☁️" if d.get("has_file") else "  "
            print(f"{d['id']:<5} {d['document_name'][:33]:<35} {d['upload_date']:<13} {d['vendor_name'][:22]:<24} ${d['total_amount']:>9,.2f}  {file_flag}")
    else:
        print("   (No documents found for the given filter)")


def main():
    print_banner()
    db = get_db()
    seed_database(db, force=False)
    paypal = PayPalClient(db=db)
    brain = AgentBrain(paypal_client=paypal, db=db)

    parser = argparse.ArgumentParser(description="Smart Auto-Pay & Balance Budget Planner CLI")
    subparsers = parser.add_subparsers(dest="command")

    # scan
    subparsers.add_parser("scan", help="Evaluate account thresholds & forecast cashflow")

    # subs
    subparsers.add_parser("subs", help="List all monitored PayPal subscriptions")

    # balance
    p_bal = subparsers.add_parser("balance", help="View or update account balance")
    p_bal.add_argument("new_balance", type=float, nargs="?", default=None, help="New balance to set")

    # pause
    p_pause = subparsers.add_parser("pause", help="Pause a subscription via PayPal API")
    p_pause.add_argument("sub_id", type=str, help="Subscription ID (e.g. I-ADOBECC9921)")

    # resume
    p_resume = subparsers.add_parser("resume", help="Resume a subscription via PayPal API")
    p_resume.add_argument("sub_id", type=str, help="Subscription ID")

    # webhook-drop
    p_wh = subparsers.add_parser("webhook-drop", help="Simulate a PayPal balance drop webhook")
    p_wh.add_argument("balance", type=float, help="New dropped balance amount")

    # ask
    p_ask = subparsers.add_parser("ask", help="Query the AI Agent with natural language")
    p_ask.add_argument("query", nargs="+", help="Natural language question")

    # month-end
    p_me = subparsers.add_parser("month-end", help="Generate & automatically deliver month-end expenditure table & transactions PDF via WhatsApp + App Notification")
    p_me.add_argument("--phone", type=str, default="+919876543210", help="WhatsApp phone number with country code")

    # notifications
    subparsers.add_parser("notifications", help="List in-app notifications and PDF download records")

    # shortfall & ways-to-save (Property 1)
    subparsers.add_parser("shortfall", help="Advise on payment shortfalls, unwanted payments, and actionable ways to save")
    subparsers.add_parser("ways-to-save", help="Alias for shortfall analysis and savings advice")

    # business-bills (Property 2)
    p_biz = subparsers.add_parser("business-bills", help="View pre-sorted business bills ledger and month-end reconciliation")
    p_biz.add_argument("--sort", type=str, default="category", choices=["category", "vendor", "date", "status", "amount"], help="Sort criteria")
    p_biz.add_argument("--export", action="store_true", help="Generate and export official business reconciliation PDF")

    # add-bill (Property 2 daily ingestion)
    p_add = subparsers.add_parser("add-bill", help="Ingest a daily bill/invoice for automated sorting")
    p_add.add_argument("--vendor", type=str, required=True, help="Vendor / Supplier name")
    p_add.add_argument("--amount", type=float, required=True, help="Total bill amount")
    p_add.add_argument("--title", type=str, default=None, help="Document title or item description")
    p_add.add_argument("--invoice", type=str, default=None, help="Invoice number")
    p_add.add_argument("--category", type=str, default=None, help="Accounting category (Auto-detected if omitted)")
    p_add.add_argument("--status", type=str, default="PAID", choices=["PAID", "PENDING", "OVERDUE"], help="Payment status")

    # reset
    subparsers.add_parser("reset", help="Reset demonstration data")

    # cloud-storage (Property 3)
    p_cloud = subparsers.add_parser("cloud-storage", help="Manage cloud document storage membership and vault")
    p_cloud.add_argument("--upgrade", type=str, choices=["FREE", "STANDARD", "BUSINESS"], metavar="TIER",
                         help="Upgrade (or change) cloud storage plan: FREE / STANDARD / BUSINESS")
    p_cloud.add_argument("--month", type=str, metavar="YYYY-MM",
                         help="List documents uploaded in a given month (e.g. 2026-11), sorted by name+date")
    p_cloud.add_argument("--search", type=str, metavar="QUERY",
                         help="Search documents by partial name or vendor (case-insensitive)")

    args = parser.parse_args()

    cmds = {
        "scan": cmd_scan,
        "subs": cmd_subs,
        "balance": cmd_balance,
        "pause": cmd_pause,
        "resume": cmd_resume,
        "webhook-drop": cmd_webhook_drop,
        "ask": cmd_ask,
        "month-end": cmd_month_end,
        "notifications": cmd_notifications,
        "shortfall": cmd_shortfall,
        "ways-to-save": cmd_shortfall,
        "business-bills": cmd_business_bills,
        "add-bill": cmd_add_bill,
        "reset": cmd_reset,
        "cloud-storage": cmd_cloud_storage,
    }

    if args.command in cmds:
        cmds[args.command](args, brain, db)
    else:
        cmd_scan(args, brain, db)

if __name__ == "__main__":
    main()
