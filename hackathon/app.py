"""
The Smart Auto-Pay & Balance Budget Planner
Interactive Streamlit Application & AI Agent Dashboard.
"""

import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import json

from config import config
from database.db import get_db
from database.seed_data import seed_database
from paypal.client import PayPalClient
from paypal.webhook_handler import PayPalWebhookHandler
from agent.brain import AgentBrain
from agent.classifier import SubscriptionClassifier
from agent.predictor import CashflowPredictor
from agent.savings_advisor import SavingsAdvisor
from reports.pdf_generator import MonthEndReportGenerator
from reports.notifier import ReportDeliveryService
from business.sorter import BusinessBillSorter
from business.document_parser import BusinessDocumentParser
from business.business_report_generator import BusinessReportGenerator
from business.cloud_storage import CloudStorageManager, TIERS as CLOUD_TIERS

# Set page configuration
st.set_page_config(
    page_title="Smart Auto-Pay & Balance Budget Planner",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern styling
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 16px;
        text-align: center;
    }
    .alert-banner {
        background-color: #FEF2F2;
        border-left: 5px solid #EF4444;
        padding: 16px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    .safe-banner {
        background-color: #F0FDF4;
        border-left: 5px solid #22C55E;
        padding: 16px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    .sub-card {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 14px;
        margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .badge-critical {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-moderate {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-safe {
        background-color: #DCFCE7;
        color: #166534;
        padding: 3px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .notif-card {
        background: #FFFBEB;
        border-left: 4px solid #F59E0B;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .notif-card-report {
        background: #EFF6FF;
        border-left: 4px solid #3B82F6;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .notif-card-alert {
        background: #FEF2F2;
        border-left: 4px solid #EF4444;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .wa-sent {
        background-color: #DCFCE7;
        color: #166534;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 0.75rem;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Database and Agent
import os
db = get_db()
seed_database(db, force=False)
account = db.get_account()

if not account:
    seed_database(db, force=True)
    account = db.get_account()

paypal_client = PayPalClient(db=db)
agent_brain = AgentBrain(paypal_client=paypal_client, db=db)
webhook_handler = PayPalWebhookHandler(agent_brain=agent_brain, db=db)
delivery_service = ReportDeliveryService(db=db)

# Sidebar: Controls & Settings
with st.sidebar:
    st.image("https://img.icons8.com/color/96/paypal.png", width=64)
    st.title("Guardrail Controls")
    
    st.subheader("Account Guardrail Thresholds")
    cur_bal = float(account["balance"])
    cur_thresh = float(account["safety_threshold"])
    cur_buf = float(account["overdraft_buffer"])
    cur_auto = bool(account.get("autonomous_mode", 0))

    new_thresh = st.slider("Safety Threshold ($)", min_value=100.0, max_value=800.0, value=cur_thresh, step=25.0)
    new_buf = st.slider("Overdraft Buffer ($)", min_value=25.0, max_value=300.0, value=cur_buf, step=25.0)
    
    st.subheader("Interception Mode")
    new_auto = st.toggle("Autonomous Auto-Pause", value=cur_auto, help="When enabled, AI automatically pauses subscriptions when balance breaches threshold.")
    
    if new_thresh != cur_thresh or new_buf != cur_buf or new_auto != cur_auto:
        db.update_thresholds(new_thresh, new_buf, new_auto)
        st.success("Guardrail parameters updated!")
        st.rerun()

    st.divider()

    # --- In-App Notification Bell ---
    unread_count = db.get_unread_notification_count()
    bell_label = f"🔔 Notifications ({unread_count} new)" if unread_count > 0 else "🔔 Notifications"
    if st.button(bell_label, use_container_width=True):
        db.mark_notifications_as_read()
        st.session_state["show_notifications"] = True
        st.rerun()

    st.divider()
    st.subheader("PayPal Sandbox Status")
    mode_text = "Emulated Sandbox (Zero-Config)" if paypal_client.mock_mode else f"Live {config.PAYPAL_ENV.upper()}"
    st.info(f"**Engine:** {mode_text}\n\n**API Base:** `{paypal_client.api_base}`")

    st.divider()
    if st.button("🔄 Reset Demo Data"):
        seed_database(db, force=True)
        st.success("Reset to original demo state!")
        st.rerun()

# Run Real-Time Agent Evaluation
eval_result = agent_brain.evaluate_account_thresholds(trigger_event="Live Dashboard Review")
forecast = eval_result["forecast"]
recommendations = eval_result["recommendations"]
actions_taken = eval_result["actions_taken"]
active_subs = db.get_subscriptions(status="ACTIVE")
paused_subs = db.get_subscriptions(status="SUSPENDED")
total_monthly_active = sum(s["amount"] for s in active_subs)
total_monthly_paused = sum(s["amount"] for s in paused_subs)

# Main Header
col_title, col_status = st.columns([3, 1])
with col_title:
    st.markdown('<div class="main-title">The Smart Auto-Pay & Balance Budget Planner</div>', unsafe_allow_html=True)
    st.markdown('<div class="subtitle">Autonomous AI agent continuously intercepting draining subscriptions to defend your balance guardrails.</div>', unsafe_allow_html=True)

with col_status:
    if eval_result["status"] in ("ALERT_INTERCEPTED", "WARNING_BELOW_THRESHOLD"):
        st.markdown("""
        <div style="background-color: #FEE2E2; border: 1px solid #F87171; border-radius: 8px; padding: 10px; text-align: center;">
            <strong style="color: #991B1B;">⚠️ GUARDRAIL ALERT</strong><br>
            <span style="font-size: 0.85rem; color: #7F1D1D;">Interception Required</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background-color: #DCFCE7; border: 1px solid #4ADE80; border-radius: 8px; padding: 10px; text-align: center;">
            <strong style="color: #166534;">🛡️ GUARDRAIL ACTIVE</strong><br>
            <span style="font-size: 0.85rem; color: #14532D;">Thresholds Protected</span>
        </div>
        """, unsafe_allow_html=True)

# Top KPI Metric Cards
m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    delta_color = "normal" if cur_bal >= cur_thresh else "inverse"
    st.metric("Available Balance", f"${cur_bal:.2f}", delta=f"{cur_bal - cur_thresh:+.2f} vs Guardrail", delta_color=delta_color)
with m2:
    st.metric("Safety Threshold", f"${cur_thresh:.2f}", help="Warning threshold before AI activates pause recommendations")
with m3:
    st.metric("Overdraft Buffer", f"${cur_buf:.2f}", help="Hard floor limit below which overdraft fees occur")
with m4:
    risk_pct = forecast["overdraft_risk_percentage"]
    st.metric("14-Day Overdraft Risk", f"{risk_pct}%", delta=f"{'HIGH' if risk_pct > 50 else 'LOW'}", delta_color="inverse" if risk_pct > 50 else "normal")
with m5:
    st.metric("Monthly Preserved", f"${total_monthly_paused:.2f}/mo", delta=f"{len(paused_subs)} Subscriptions Paused", delta_color="off")

st.markdown("<br>", unsafe_allow_html=True)

# MAIN INTERCEPT ALERT SECTION
if recommendations:
    st.markdown('<div class="alert-banner">', unsafe_allow_html=True)
    st.markdown(f"### 🚨 AI Interception Prompt: {len(recommendations)} Draining Subscriptions Intercepted")
    st.write(
        f"Your current balance of **${cur_bal:.2f}** is below your **${cur_thresh:.2f}** safety threshold, "
        f"or upcoming autopays will breach your **${cur_buf:.2f}** overdraft buffer in {forecast['days_to_threshold_breach'] or 0} days. "
        f"The AI Agent has pinpointed the following under-utilized subscriptions to pause via the PayPal Subscriptions API:"
    )

    # 1-Click Intercept All Button
    col_all, col_space = st.columns([1, 2])
    with col_all:
        if st.button("⚡ Pause All Recommended via PayPal API", type="primary", use_container_width=True):
            for rec in recommendations:
                agent_brain.execute_pause(rec["subscription_id"], reason="Bulk Auto-Pay Intercept by User")
            st.success("All recommended subscriptions successfully paused via PayPal API!")
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # Display candidate cards
    for rec in recommendations:
        with st.container():
            st.markdown(f"""
            <div class="sub-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 1.15rem; font-weight: 700; color: #1F2937;">{rec['subscription_name']} ({rec['vendor']})</span>
                    <span class="badge-critical">{rec['urgency_level']} PRIORITY • SCORE: {rec['pause_score']:.1f}</span>
                </div>
                <div style="color: #4B5563; font-size: 0.9rem; margin-top: 4px;">
                    Category: <strong>{rec['category']}</strong> | Monthly Cost: <strong style="color: #DC2626;">${rec['amount']:.2f}/mo</strong> | Next Billing: <strong>{rec['next_billing_date']} (in {rec['days_until_billing']} days)</strong>
                </div>
                <div style="background-color: #F9FAFB; border-left: 3px solid #6366F1; padding: 10px; margin-top: 10px; border-radius: 4px; font-size: 0.88rem;">
                    <strong>AI Brain Rationale:</strong><br>
                    {rec['explanation'].replace(chr(10), '<br>')}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Action buttons for this specific subscription
            b1, b2, b3 = st.columns([1.2, 1.5, 3])
            with b1:
                if st.button(f"⏸️ Pause ({rec['subscription_id']})", key=f"pause_{rec['subscription_id']}"):
                    agent_brain.execute_pause(rec["subscription_id"])
                    st.success(f"Paused {rec['subscription_name']} on PayPal!")
                    st.rerun()
            with b2:
                # Downgrade tier simulation
                if st.button(f"📉 Downgrade Tier", key=f"downgrade_{rec['subscription_id']}"):
                    new_tier_amt = round(rec["amount"] * 0.5, 2)
                    agent_brain.execute_revise(rec["subscription_id"], "P-REVISED-TIER-50", new_tier_amt)
                    st.success(f"Downgraded {rec['subscription_name']} to ${new_tier_amt:.2f}/mo!")
                    st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="safe-banner">', unsafe_allow_html=True)
    st.markdown("### ✅ Savings Guardrails Secure")
    st.write(f"All recurring PayPal autopays are balanced within your **${cur_thresh:.2f}** safety threshold. 14-day cashflow runway is healthy.")
    st.markdown('</div>', unsafe_allow_html=True)

# Tabs for Core Capabilities
tab_shortfall, tab_forecast, tab_subs, tab_business, tab_report, tab_agent_chat, tab_webhook, tab_audit = st.tabs([
    "💡 Shortfall & Ways to Save",
    "📈 Cashflow & Counterfactual Simulation",
    "💳 PayPal Subscriptions Portfolio",
    "🏢 Business Daily Bill Sorter",
    "📊 Month-End Report & Notifications",
    "🤖 AI Agent Chat & Reasoning",
    "⚡ PayPal Webhooks Simulator",
    "📋 Action Audit Trail"
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1: SHORTFALL & WAYS TO SAVE ADVISOR (Property 1)
# ─────────────────────────────────────────────────────────────────────────────
with tab_shortfall:
    st.subheader("💡 Smart Payment Shortfall & Ways to Save Advisor")
    st.caption("Active monitoring when available balance is less than required upcoming payments, pinpointing unwanted charges and actionable savings.")

    shortfall_res = SavingsAdvisor.analyze_commitments_and_shortfall(
        available_balance=cur_bal,
        subscriptions=active_subs,
        safety_threshold=cur_thresh
    )

    # Status Alert Banner
    if shortfall_res["has_shortfall"]:
        st.markdown(f"""
        <div style="background-color: #FEF2F2; border-left: 5px solid #EF4444; padding: 14px; border-radius: 8px; margin-bottom: 16px;">
            <strong style="color: #991B1B; font-size: 1.05rem;">⚠️ PAYMENT SHORTFALL DETECTED</strong><br>
            <span style="color: #7F1D1D; font-size: 0.95rem;">{shortfall_res['status_message']}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background-color: #F0FDF4; border-left: 5px solid #22C55E; padding: 14px; border-radius: 8px; margin-bottom: 16px;">
            <strong style="color: #166534; font-size: 1.05rem;">✅ COMMITMENTS COVERED</strong><br>
            <span style="color: #14532D; font-size: 0.95rem;">{shortfall_res['status_message']}</span>
        </div>
        """, unsafe_allow_html=True)

    # Commitment KPIs
    sk1, sk2, sk3, sk4 = st.columns(4)
    with sk1:
        st.metric("Available Balance", f"${cur_bal:.2f}")
    with sk2:
        st.metric("Due in Next 7 Days", f"${shortfall_res['total_due_7d']:.2f}",
                  delta=f"{len(shortfall_res['upcoming_7d_payments'])} upcoming charges", delta_color="off")
    with sk3:
        st.metric("14-Day Required Total", f"${shortfall_res['total_required_14d']:.2f}",
                  help="Includes upcoming autopays + basic living baseline expenses")
    with sk4:
        sf_amt = shortfall_res['shortfall_14d']
        st.metric("Runway Shortfall / Deficit", f"${sf_amt:.2f}",
                  delta="DEFICIT" if sf_amt > 0 else "SOLVENT",
                  delta_color="inverse" if sf_amt > 0 else "normal")

    st.markdown("<br>", unsafe_allow_html=True)

    # Section A: Unwanted / Non-Essential Payments
    st.markdown("### 🚨 Unwanted & Dormant Payments Advised for Immediate Pause")
    st.write("When balance is less than required commitments, the AI advises pausing these low-ROI or zero-usage subscriptions first:")

    unwanted = shortfall_res["unwanted_payments"]
    if unwanted:
        for u in unwanted:
            st.markdown(f"""
            <div style="background: #FFFFFF; border: 1px solid #FCA5A5; border-radius: 8px; padding: 14px; margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 1.1rem; font-weight: 700; color: #111827;">{u['name']} ({u['vendor']})</span>
                    <span class="badge-critical">${u['amount']:.2f}/mo • UNWANTED DRAIN</span>
                </div>
                <div style="color: #DC2626; font-size: 0.88rem; margin-top: 4px;">
                    <strong>Flagged Reason:</strong> {u['primary_reason']} | Next billing: <strong>{u['next_billing_date']}</strong>
                </div>
                <div style="color: #4B5563; font-size: 0.85rem; margin-top: 2px;">
                    💡 <em>{u['recommendation']}</em>
                </div>
            </div>
            """, unsafe_allow_html=True)

            uc1, uc2 = st.columns([1.5, 4])
            with uc1:
                if st.button(f"⏸️ Pause via PayPal API", key=f"sf_pause_{u['id']}"):
                    agent_brain.execute_pause(u['id'], reason="Shortfall Interception by Advisor")
                    st.success(f"Paused {u['name']}! Defended ${u['amount']:.2f}/mo.")
                    st.rerun()
    else:
        st.info("No unwanted or dormant subscriptions detected in your portfolio.")

    st.markdown("<br>", unsafe_allow_html=True)

    # Section B: Actionable Ways to Save
    st.markdown("### 🛠️ 5 Concrete Ways to Save Amount & Defend Runway")
    st.caption("Strategic financial tactics formulated by the AI Agent to eliminate payment shortfalls:")

    tactics = shortfall_res["ways_to_save"]
    for i, t in enumerate(tactics, 1):
        with st.expander(f"{t['tactic']} — Potential Savings: {t['savings_estimate']} [{t['difficulty']}]"):
            st.markdown(f"**How it works:** {t['description']}")
            st.markdown(f"**Financial Impact:** {t['impact']}")
            if "Instant Subscription" in t['tactic']:
                if st.button("⚡ Execute All Advised Pauses Now", key=f"tactic_btn_{i}", type="primary"):
                    for u in unwanted:
                        agent_brain.execute_pause(u["id"], reason="All Advised Pauses Executed")
                    st.success("All advised unwanted payments successfully paused via PayPal API!")
                    st.rerun()

    st.divider()

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2: CASHFLOW & FORECAST SIMULATION
# ─────────────────────────────────────────────────────────────────────────────
with tab_forecast:
    st.subheader("14-Day Predictive Cashflow Forecast")
    st.caption("Visualizing day-by-day account balance trajectory under baseline vs. AI guardrail protection.")

    sim_res = eval_result.get("simulation")
    daily_data = forecast["daily_projection"]

    # Build DataFrame for visualization
    chart_rows = []
    for day in daily_data:
        chart_rows.append({
            "Date": day["date"][5:],  # MM-DD
            "Baseline Forecast": day["projected_balance"],
            "Safety Threshold": cur_thresh,
            "Overdraft Floor": cur_buf
        })
    df_chart = pd.DataFrame(chart_rows).set_index("Date")
    st.line_chart(df_chart, color=["#EF4444", "#3B82F6", "#F59E0B"])

    st.markdown("#### Counterfactual Impact Analysis")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"**Baseline Lowest Balance:** `${forecast['lowest_projected_balance']:.2f}` on `{forecast['lowest_balance_date']}`")
    with c2:
        saved_if_paused = sum(r["amount"] for r in recommendations)
        st.markdown(f"**Protected Runway Benefit:** `+${saved_if_paused:.2f}` defended")
    with c3:
        status_word = "Averted" if (forecast['lowest_projected_balance'] < cur_buf and saved_if_paused > 0) else "Not at Immediate Risk"
        st.markdown(f"**Overdraft Hazard:** `{status_word}`")

    # Stress Test Slider
    st.divider()
    st.markdown("#### What-If Stress Tester")
    st.caption("Simulate an unexpected bill or balance drop to see how the AI Agent responds immediately.")
    stress_spend = st.slider("Simulate sudden debit expense ($)", min_value=0.0, max_value=300.0, value=0.0, step=10.0)
    if stress_spend > 0:
        sim_balance = max(0.0, cur_bal - stress_spend)
        st.write(f"If an unexpected **${stress_spend:.2f}** charge occurs, balance becomes **${sim_balance:.2f}**.")
        if st.button("Apply Stress Test to Balance"):
            db.update_balance(sim_balance)
            st.rerun()

# TAB 2: PAYPAL SUBSCRIPTIONS PORTFOLIO
with tab_subs:
    st.subheader("Monitored PayPal Subscriptions")
    all_subs = db.get_subscriptions()

    col_filter1, col_filter2 = st.columns([2, 1])
    with col_filter1:
        st.write(f"Total Subscriptions Monitored: **{len(all_subs)}** | Active Monthly Run Rate: **${total_monthly_active:.2f}/mo**")
    
    sub_table_data = []
    for s in all_subs:
        sub_table_data.append({
            "ID": s["id"],
            "Name": s["name"],
            "Vendor": s["vendor"],
            "Category": s["category"],
            "Amount": f"${s['amount']:.2f}",
            "Next Billing": s["next_billing_date"],
            "Status": s["status"],
            "Days Used (30d)": s["usage_days_last_30"],
            "Hours (30d)": f"{s['hours_used_last_30']:.1f}h",
            "Essentiality": s["essentiality"].title(),
            "Auto-Pause": "Yes" if s["auto_pause_eligible"] else "Protected"
        })
    st.dataframe(pd.DataFrame(sub_table_data), use_container_width=True)

    st.markdown("#### Subscription Quick Action Controls")
    for s in all_subs:
        with st.expander(f"{'🟢' if s['status'] == 'ACTIVE' else '⏸️'} {s['name']} — ${s['amount']:.2f}/mo (Status: {s['status']})"):
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.write(f"**Usage:** {s['usage_days_last_30']} days / {s['hours_used_last_30']:.1f} hrs in last month")
                st.write(f"**Next Charge:** {s['next_billing_date']}")
            with sc2:
                st.write(f"**Category:** {s['category']}")
                st.write(f"**Classification:** {s['essentiality']}")
            with sc3:
                if s["status"] == "ACTIVE":
                    if st.button("Pause Subscription", key=f"tbl_pause_{s['id']}"):
                        agent_brain.execute_pause(s["id"])
                        st.success(f"Paused {s['name']} via PayPal API")
                        st.rerun()
                else:
                    if st.button("Resume Subscription", key=f"tbl_resume_{s['id']}"):
                        agent_brain.execute_resume(s["id"])
                        st.success(f"Resumed {s['name']} via PayPal API")
                        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4: SMALL & BIG BUSINESS DAILY BILL INGESTION & AUTO-SORTER (Property 2)
# ─────────────────────────────────────────────────────────────────────────────
with tab_business:
    st.subheader("🏢 Small & Big Business Daily Bill Ingestion & Auto-Sorter")
    st.info(
        "💡 **Eliminating Month-End Bill Sorting Overhead:** Small and large businesses usually spend hours or days "
        "sorting through piles of invoices and receipts at the end of the month. With this feature, simply drop your "
        "documents daily as they arrive. The AI automatically parses, extracts tax/due dates, and pre-sorts your entire "
        "ledger by Accounting Category, Vendor, and Tax Deductibility!"
    )

    biz_sorter = BusinessBillSorter(db=db)
    biz_report_gen = BusinessReportGenerator()
    recon = biz_sorter.generate_month_end_reconciliation()
    stats = recon["stats"]

    # Section 1: Daily Document Dropzone
    with st.expander("📥 Daily Document & Bill Dropzone (Click to Ingest New Invoice/Bill)", expanded=False):
        st.markdown("##### Ingest Daily Invoice or Receipt")
        bf1, bf2 = st.columns(2)
        with bf1:
            in_vendor = st.text_input("Vendor / Supplier Name*", placeholder="e.g. Acme Industrial Supplies, FedEx, Google")
            in_title = st.text_input("Document / Item Description", placeholder="e.g. Raw Material Batch #402, Freight shipment")
            in_inv = st.text_input("Invoice / Bill #", placeholder="e.g. INV-2026-8812")
        with bf2:
            in_amount = st.number_input("Total Bill Amount ($)*", min_value=1.0, max_value=50000.0, value=250.0, step=25.0)
            in_cat = st.selectbox("Accounting Category", [
                "Auto-Detect",
                "Inventory & COGS",
                "Facilities & Rent",
                "IT & Software",
                "Utilities",
                "Shipping & Logistics",
                "Marketing & Advertising",
                "Professional Services",
                "Office & Equipment",
                "Insurance & Legal"
            ])
            in_status = st.selectbox("Payment Status", ["PAID", "PENDING", "OVERDUE"])

        if st.button("⚡ Ingest & Auto-Sort Daily Bill Now", type="primary"):
            if in_vendor:
                parsed_doc = BusinessDocumentParser.parse_document_input(
                    vendor_name=in_vendor,
                    total_amount=in_amount,
                    document_name=in_title,
                    invoice_number=in_inv,
                    category=in_cat,
                    payment_status=in_status
                )
                db.add_business_document(parsed_doc)
                st.success(f"✅ Document from '{in_vendor}' successfully ingested and pre-sorted into '{parsed_doc['category']}'!")
                st.rerun()
            else:
                st.warning("Please provide a Vendor Name.")

    # Section 2: Month-End Financial Reconciliation KPIs
    st.markdown("### 📊 Month-End Business Reconciliation Summary")
    bk1, bk2, bk3, bk4 = st.columns(4)
    with bk1:
        st.metric("Total Bills Auto-Sorted", f"{recon['total_bills_sorted']} Invoices",
                  delta="100% Pre-Categorized", delta_color="normal")
    with bk2:
        st.metric("Gross Business Expense", f"${recon['total_expenses']:,.2f}")
    with bk3:
        st.metric("100% Tax Deductible", f"${recon['total_tax_deductible']:,.2f}",
                  delta="Ready for CPA / IRS Filing", delta_color="off")
    with bk4:
        st.metric("Pending Accounts Payable", f"${recon['pending_payables']:,.2f}",
                  delta=f"{len(recon['pending_bills'])} unpaid bills", delta_color="inverse" if recon['pending_payables'] > 0 else "normal")

    st.markdown("<br>", unsafe_allow_html=True)

    # Section 3: Interactive Sorting Controls
    st.markdown("### 🗂️ Pre-Sorted Business Ledger")
    c_sort, c_cat, c_stat = st.columns([1.5, 1.5, 1.5])
    with c_sort:
        chosen_sort = st.selectbox("Sort Bills By:", ["category", "vendor", "date", "status", "amount"],
                                   format_func=lambda x: f"Sort by {x.title()}")
    with c_cat:
        available_cats = ["All"] + [c["category"] for c in recon["by_category"]]
        chosen_cat = st.selectbox("Filter Category:", available_cats)
    with c_stat:
        chosen_status = st.selectbox("Filter Status:", ["All", "PAID", "PENDING", "OVERDUE"])

    sorted_docs = biz_sorter.get_sorted_bills(
        sort_by=chosen_sort,
        category_filter=chosen_cat,
        status_filter=chosen_status
    )

    if sorted_docs:
        ledger_table = []
        for d in sorted_docs:
            ledger_table.append({
                "Date": d["invoice_date"],
                "Vendor / Supplier": d["vendor_name"],
                "Category": d["category"],
                "Invoice #": d.get("invoice_number", ""),
                "Due Date": d.get("due_date", ""),
                "Tax ($)": f"${d['tax_amount']:.2f}",
                "Total Amount ($)": f"${d['total_amount']:,.2f}",
                "Status": d["payment_status"],
                "Tax Deductible": "Yes" if d.get("tax_deductible") else "No"
            })
        st.dataframe(pd.DataFrame(ledger_table), use_container_width=True, hide_index=True)
    else:
        st.info("No documents match the selected filters.")

    # Section 4: 1-Click Month-End Export Center
    st.markdown("#### 📥 Month-End Export Center (For Accountants & Tax Filing)")
    st.caption("No manual sorting required. Export your fully reconciled and sorted statement in 1 click:")

    ex1, ex2 = st.columns(2)
    with ex1:
        if st.button("📄 Generate Sorted Month-End Business PDF", use_container_width=True):
            biz_pdf_path = biz_report_gen.generate_sorted_business_pdf()
            with open(biz_pdf_path, "rb") as bpf:
                st.download_button(
                    label="📥 Download Official Business Statement (PDF)",
                    data=bpf.read(),
                    file_name=os.path.basename(biz_pdf_path),
                    mime="application/pdf",
                    use_container_width=True
                )
    with ex2:
        csv_data = biz_report_gen.generate_sorted_csv()
        st.download_button(
            label="📊 Export Bookkeeping CSV (QuickBooks / Xero)",
            data=csv_data,
            file_name=f"Business_Reconciled_Ledger_{datetime.now().strftime('%Y_%m')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    st.divider()

    # ─────────────────────────────────────────────────────────────────────────
    # Cloud Storage Plan & Document Vault (Property 3)
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("### ☁️ Cloud Storage Plan & Document Vault")
    st.info(
        "Worried about local storage space? Upgrade your **Cloud Membership** to unlock automatic "
        "cloud document storage. All files are organised by **name and date** so they always match "
        "your month-end list and are easy to find."
    )

    cloud_mgr = CloudStorageManager(db=db)
    cloud_cfg = cloud_mgr.get_config()
    cur_tier = cloud_cfg["plan_tier"] if cloud_cfg else "FREE"
    cur_quota = cloud_cfg["storage_quota_mb"] if cloud_cfg else 50
    cur_used_mb = cloud_mgr.get_storage_usage_mb()
    usage_pct = min(100.0, (cur_used_mb / max(1, cur_quota)) * 100)
    tier_meta = CLOUD_TIERS.get(cur_tier, CLOUD_TIERS["FREE"])

    cv1, cv2, cv3 = st.columns(3)
    with cv1:
        tier_color = {"FREE": "🔵", "STANDARD": "🟡", "BUSINESS": "🟢"}.get(cur_tier, "🔵")
        st.metric("Current Plan", f"{tier_color} {cur_tier}", delta=tier_meta["label"])
    with cv2:
        st.metric("Monthly Price", f"${tier_meta['price']:.2f}/mo",
                  delta="Included in PayPal billing" if cur_tier != "FREE" else "Upgrade to unlock cloud")
    with cv3:
        st.metric("Storage Used", f"{cur_used_mb:.2f} MB / {cur_quota} MB",
                  delta=f"{usage_pct:.1f}% of quota")

    # Plan feature comparison
    with st.expander("📋 Compare Cloud Plans & Upgrade", expanded=(cur_tier == "FREE")):
        pc1, pc2, pc3 = st.columns(3)
        for col, (tier_key, t_info) in zip([pc1, pc2, pc3], CLOUD_TIERS.items()):
            highlight = tier_key == cur_tier
            border_style = "border: 2px solid #3B82F6;" if highlight else "border: 1px solid #E2E8F0;"
            badge = " ✓ Current" if highlight else ""
            feat_html = "".join(f"<li style='font-size:0.85rem'>{f}</li>" for f in t_info["features"])
            col.markdown(
                f"""<div style="padding:14px; border-radius:10px; {border_style} background:#F8FAFC">
                    <strong>{t_info['label']}{badge}</strong><br>
                    <ul style='margin-top:8px; padding-left:16px'>{feat_html}</ul>
                </div>""",
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)
        up_col1, up_col2 = st.columns([2, 1])
        with up_col1:
            new_plan = st.selectbox(
                "Select New Plan:",
                list(CLOUD_TIERS.keys()),
                index=list(CLOUD_TIERS.keys()).index(cur_tier),
                format_func=lambda x: CLOUD_TIERS[x]["label"],
                key="cloud_plan_select"
            )
        with up_col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Apply Plan Change", use_container_width=True, type="primary"):
                result = cloud_mgr.upgrade_tier(new_plan)
                if result["success"]:
                    st.success(
                        f"✅ Plan upgraded to **{result['label']}** — "
                        f"${result['price']:.2f}/mo | {result['quota_mb']:,} MB storage unlocked!"
                    )
                    st.rerun()
                else:
                    st.error(result.get("error", "Upgrade failed."))

    st.markdown("<br>", unsafe_allow_html=True)

    # Document Vault — search / filter / month view
    st.markdown("#### 🗄️ Document Vault (Sorted by Name → Date)")
    vault_col_a, vault_col_b = st.columns([2, 1])
    with vault_col_a:
        vault_search = st.text_input("🔍 Search by document name or vendor:", placeholder="e.g. invoice, aws, fedex")
    with vault_col_b:
        import datetime as _dt
        months_list = [
            (_dt.datetime.now() - _dt.timedelta(days=30 * i)).strftime("%Y-%m")
            for i in range(6)
        ]
        selected_month_str = st.selectbox("📅 Filter by Month:", ["All"] + months_list, key="vault_month_sel")

    # Retrieve docs
    if vault_search:
        vault_docs = cloud_mgr.search_by_name(vault_search)
    elif selected_month_str != "All":
        yr, mo = int(selected_month_str[:4]), int(selected_month_str[5:])
        vault_docs = cloud_mgr.list_by_month(yr, mo)
    else:
        vault_docs = cloud_mgr.list_all()

    if vault_docs:
        v_rows = []
        for vd in vault_docs:
            v_rows.append({
                "ID":            vd["id"],
                "Document Name": vd["document_name"],
                "Upload Date":   vd["upload_date"],
                "Vendor":        vd["vendor_name"],
                "Category":      vd["category"],
                "Invoice #":     vd.get("invoice_number", ""),
                "Total ($)":     f"${vd['total_amount']:,.2f}",
                "Status":        vd["payment_status"],
                "File Stored":   "☁️ Yes" if vd.get("has_file") else "📂 Local Only",
            })
        st.dataframe(pd.DataFrame(v_rows), use_container_width=True, hide_index=True)
        st.caption(
            f"📌 Showing **{len(vault_docs)}** document(s) sorted by **Name A→Z** then **Date (newest first)**"
            + (f" | Filter: '{vault_search}'" if vault_search else "")
            + (f" | Month: {selected_month_str}" if selected_month_str != "All" else "")
        )

        # Upload a file blob to an existing document
        if cur_tier != "FREE":
            with st.expander("📤 Attach File to Existing Document (Cloud Upload)", expanded=False):
                upload_doc_id = st.number_input("Document ID to Attach File To:", min_value=1, step=1, value=vault_docs[0]["id"])
                uploaded_file = st.file_uploader("Upload PDF / Image / Receipt", type=["pdf", "png", "jpg", "jpeg", "csv"])
                if uploaded_file and st.button("⬆️ Upload to Cloud Vault", type="primary"):
                    up_result = cloud_mgr.upload_document(
                        doc_id=int(upload_doc_id),
                        file_bytes=uploaded_file.read(),
                        filename=uploaded_file.name,
                    )
                    if up_result["success"]:
                        st.success(
                            f"✅ '{uploaded_file.name}' uploaded to Document #{upload_doc_id} "
                            f"({up_result['size_kb']:.1f} KB). "
                            f"Total used: {up_result['used_mb']:.2f} MB"
                        )
                        st.rerun()
                    else:
                        st.error(up_result.get("error", "Upload failed."))
        else:
            st.info("🔒 File upload requires **STANDARD** or **BUSINESS** plan. Upgrade above to attach & store files in the cloud vault.")
    else:
        st.info("No documents found. Ingest your first daily bill above, or adjust the search / month filter.")

    st.divider()

# TAB 3: AI AGENT CHAT & REASONING
with tab_agent_chat:
    st.subheader("Autonomous AI Agent Chat")
    st.caption("Converse with the Smart Auto-Pay Agent to understand budget thresholds, risk forecasts, and pause decisions.")

    # Quick prompt buttons
    st.markdown("**Quick Prompts:**")
    qp1, qp2, qp3 = st.columns(3)
    selected_prompt = None
    with qp1:
        if st.button("🔍 Analyze draining subscriptions"):
            selected_prompt = "Analyze my budget and find draining subscriptions"
    with qp2:
        if st.button("📊 Assess 14-day overdraft risk"):
            selected_prompt = "What is my overdraft risk for the next 14 days?"
    with qp3:
        if st.button("🏋️ Why pause Metro Gym & Adobe?"):
            selected_prompt = "Why should I pause Metro Gym and Adobe Creative Cloud?"

    # Chat history
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "assistant", "content": "Hello Alex! I am your **Smart Auto-Pay & Guardrail Agent**. I continuously monitor your balance and PayPal recurring billing to prevent overdrafts. How can I assist your budget today?"}
        ]

    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_query = st.chat_input("Ask about your subscriptions, balance, or overdraft risk...") or selected_prompt
    if user_query:
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        agent_reply = agent_brain.ask_agent(user_query)
        st.session_state.chat_history.append({"role": "assistant", "content": agent_reply})
        with st.chat_message("assistant"):
            st.markdown(agent_reply)

# TAB 4: PAYPAL WEBHOOKS SIMULATOR
with tab_webhook:
    st.subheader("Real-Time PayPal Webhook Ingestion Engine")
    st.caption("Simulate incoming PayPal balance alerts or transaction events and watch the AI Agent immediately wake up and intercept draining charges.")

    wh_col1, wh_col2 = st.columns([1, 1])
    with wh_col1:
        st.markdown("#### Dispatch Simulated Webhook")
        event_choice = st.selectbox("Select PayPal Webhook Event:", [
            "CUSTOMER.BALANCE.DROPPED",
            "PAYMENT.SALE.COMPLETED",
            "BILLING.SUBSCRIPTION.SUSPENDED",
            "BILLING.SUBSCRIPTION.ACTIVATED"
        ])

        if event_choice == "CUSTOMER.BALANCE.DROPPED":
            drop_val = st.number_input("New Balance Value ($):", min_value=10.0, max_value=1000.0, value=175.0, step=25.0)
            sample_payload = {
                "id": f"WH-DROP-{datetime.now().strftime('%H%M%S')}",
                "event_type": "CUSTOMER.BALANCE.DROPPED",
                "summary": f"PayPal Balance Alert: Available balance dropped to ${drop_val:.2f}",
                "resource": {
                    "current_balance": {"currency_code": "USD", "value": str(drop_val)}
                }
            }
        elif event_choice == "PAYMENT.SALE.COMPLETED":
            sale_amt = st.number_input("Debit Amount ($):", min_value=5.0, max_value=500.0, value=85.0, step=10.0)
            sample_payload = {
                "id": f"WH-SALE-{datetime.now().strftime('%H%M%S')}",
                "event_type": "PAYMENT.SALE.COMPLETED",
                "summary": f"PayPal Sale Completed: ${sale_amt:.2f}",
                "resource": {
                    "amount": {"total": str(sale_amt), "currency": "USD"}
                }
            }
        else:
            sample_payload = {
                "id": f"WH-SUB-{datetime.now().strftime('%H%M%S')}",
                "event_type": event_choice,
                "summary": f"Subscription update: {event_choice}",
                "resource": {
                    "id": "I-ADOBECC9921"
                }
            }

        st.json(sample_payload)

        if st.button("🚀 Ingest Webhook Event", type="primary"):
            wh_res = webhook_handler.process_webhook_event(sample_payload)
            st.success(f"Webhook {wh_res['event_type']} processed! Action: {wh_res['action_taken']}")
            st.rerun()

    with wh_col2:
        st.markdown("#### Recent Webhook Ingestion Log")
        logs = db.get_webhook_logs(limit=10)
        if logs:
            for l in logs:
                with st.expander(f"{l['processed_at'][11:19]} — {l['event_type']} ({l['status']})"):
                    st.write(f"**Summary:** {l['summary']}")
                    st.json(l["payload"])
        else:
            st.info("No incoming webhooks recorded yet. Fire a simulated webhook to test!")

# TAB 5: ACTION AUDIT TRAIL
with tab_audit:
    st.subheader("AI Agent Action & Decision Log")
    st.caption("Immutable record of all threshold interceptions, PayPal suspensions, and savings created.")
    actions = db.get_agent_actions(limit=25)
    if actions:
        action_table = []
        for a in actions:
            action_table.append({
                "Timestamp": a["created_at"][5:19].replace("T", " "),
                "Action": a["action_type"],
                "Subscription": a.get("subscription_name") or a.get("subscription_id") or "Account",
                "Trigger": a["trigger_reason"],
                "Saved": f"${a['savings_amount']:.2f}" if a["savings_amount"] else "$0.00",
                "Status": a["user_status"],
                "Explanation": a["ai_explanation"][:80] + "..." if len(a["ai_explanation"]) > 80 else a["ai_explanation"]
            })
        st.dataframe(pd.DataFrame(action_table), use_container_width=True)
    else:
        st.info("No agent actions recorded yet.")

# ─────────────────────────────────────────────────────────────────────────────
# TAB 6: MONTH-END EXPENDITURE REPORT & NOTIFICATIONS
# ─────────────────────────────────────────────────────────────────────────────
with tab_report:
    import os as _os
    from reports.pdf_generator import MonthEndReportGenerator
    from reports.notifier import ReportDeliveryService

    delivery_svc = ReportDeliveryService(db=db)

    st.subheader("📊 Month-End Expenditure Report & Delivery")
    st.caption(
        "Automatically generates a professional PDF summarising your monthly transactions, "
        "expenditure by category, subscriptions, and AI agent savings — then delivers it via "
        "WhatsApp message and an in-app notification."
    )

    # ── Live expenditure & transactions summary ──────────────────────────────
    transactions      = db.get_monthly_transactions(limit=200)
    expenditure_cats  = db.get_expenditure_by_category()
    total_month_spent = round(sum(t["amount"] for t in transactions), 2)
    agent_acts        = db.get_agent_actions(limit=50)
    total_ai_saved    = round(sum(a.get("savings_amount", 0) for a in agent_acts
                                  if a.get("savings_amount")), 2)

    # KPIs row
    rk1, rk2, rk3, rk4 = st.columns(4)
    with rk1:
        st.metric("Total Month Expenditure", f"${total_month_spent:.2f}",
                  delta=f"{len(transactions)} transactions")
    with rk2:
        top_cat = expenditure_cats[0] if expenditure_cats else {}
        st.metric("Top Spending Category",
                  top_cat.get("category", "N/A"),
                  delta=f'${top_cat.get("total_spent", 0):.2f}')
    with rk3:
        st.metric("Categories Tracked", str(len(expenditure_cats)))
    with rk4:
        st.metric("AI Guardrail Savings", f"${total_ai_saved:.2f}",
                  delta="Preserved via Auto-Pause", delta_color="off")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Expenditure by Category Table ───────────────────────────────────────
    st.markdown("### 🏷️ Month-End Expenditure by Category")
    if expenditure_cats:
        cat_rows = []
        for c in expenditure_cats:
            pct = round((c["total_spent"] / total_month_spent) * 100, 1) if total_month_spent else 0
            cat_rows.append({
                "Category":           c["category"],
                "Transactions":       c["transaction_count"],
                "Total Spent ($)":    round(c["total_spent"], 2),
                "Avg per Txn ($)":    round(c["avg_transaction"], 2),
                "% of Total":         f"{pct}%"
            })
        cat_rows.append({
            "Category":        "── TOTAL ──",
            "Transactions":    len(transactions),
            "Total Spent ($)": total_month_spent,
            "Avg per Txn ($)": round(total_month_spent / max(1, len(transactions)), 2),
            "% of Total":      "100%"
        })
        st.dataframe(pd.DataFrame(cat_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No transaction data yet. Reset demo data to populate.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Full Monthly Transaction Ledger ─────────────────────────────────────
    st.markdown("### 🧾 Full Monthly Transaction Ledger")
    if transactions:
        tx_rows = []
        for t in transactions:
            tx_rows.append({
                "Date":           t["transaction_date"],
                "Merchant":       t["merchant"],
                "Category":       t["category"],
                "Amount ($)":     round(t["amount"], 2),
                "Payment Method": t["payment_method"],
                "Status":         t["status"]
            })
        st.dataframe(pd.DataFrame(tx_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No transactions recorded yet.")

    st.divider()

    # ── WhatsApp & PDF Delivery Panel ───────────────────────────────────────
    st.markdown("### 📲 Send Report via WhatsApp + In-App Notification")
    st.info(
        "Enter a WhatsApp number below and click **Generate & Send**. The agent will:\n\n"
        "1. 📄 Generate a professional PDF with all tables above\n"
        "2. 💬 Send it to WhatsApp with a formatted summary message\n"
        "3. 🔔 Create an in-app notification for instant dashboard access\n\n"
        "**Live credentials:** Set `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` "
        "or `META_WA_TOKEN` + `META_WA_PHONE_NUMBER_ID` env vars. "
        "Without them, the sandbox emulator is used (fully functional for demos)."
    )

    wa_col, btn_col = st.columns([2, 1])
    with wa_col:
        wa_number = st.text_input(
            "WhatsApp Number (with country code)",
            value="+919876543210",
            placeholder="+1 234 567 8900"
        )
    with btn_col:
        st.markdown("<br>", unsafe_allow_html=True)
        generate_btn = st.button("⚡ Generate & Send Report", type="primary",
                                 use_container_width=True)

    if generate_btn:
        with st.spinner("Generating PDF, composing WhatsApp message, and sending..."):
            result = delivery_svc.deliver_month_end_report(
                to_whatsapp_number=wa_number,
                user_name=account.get("user_name", "Alex Morgan")
            )

        if result["pdf_generated"]:
            st.success("✅ PDF report generated successfully!")
        else:
            st.error("⚠️ PDF generation encountered an issue.")

        wa_ok     = result["whatsapp"].get("success")
        provider  = result["whatsapp"].get("provider", "Unknown")
        if wa_ok:
            st.success(
                f"📲 WhatsApp message sent via **{provider}** to `{wa_number}` with PDF attached."
            )
        else:
            st.error(f"WhatsApp delivery failed: {result['whatsapp'].get('error', 'Unknown error')}")

        # Preview the WhatsApp message
        with st.expander("📋 Preview WhatsApp Message Sent"):
            wa_body = delivery_svc.build_whatsapp_message(
                account=account,
                expenditure_by_category=expenditure_cats,
                total_spent=total_month_spent,
                transaction_count=len(transactions),
                total_saved=total_ai_saved
            )
            st.code(wa_body, language="")

        # PDF download button
        pdf_path = result.get("pdf_path")
        if pdf_path and _os.path.exists(pdf_path):
            with open(pdf_path, "rb") as pdf_file:
                st.download_button(
                    label="📥 Download Month-End PDF Report",
                    data=pdf_file.read(),
                    file_name=_os.path.basename(pdf_path),
                    mime="application/pdf",
                    use_container_width=True
                )

        st.info(f"🔔 In-app notification #{result['in_app_notification_id']} created.")
        st.rerun()

    # ── Previously generated PDFs ────────────────────────────────────────────
    pdf_dir = "reports_output"
    existing_pdfs = sorted(
        [f for f in _os.listdir(pdf_dir) if f.endswith(".pdf")] if _os.path.isdir(pdf_dir) else [],
        reverse=True
    )
    if existing_pdfs:
        st.markdown("### 📂 Previously Generated Reports")
        for pdf_name in existing_pdfs[:5]:
            full_path = _os.path.join(pdf_dir, pdf_name)
            with open(full_path, "rb") as pf:
                st.download_button(
                    label=f"📄 {pdf_name}",
                    data=pf.read(),
                    file_name=pdf_name,
                    mime="application/pdf",
                    key=f"dl_{pdf_name}"
                )

    st.divider()

    # ── In-App Notification Feed ─────────────────────────────────────────────
    st.markdown("### 🔔 In-App Notification Feed")
    notifications = db.get_app_notifications(limit=20)
    if notifications:
        for n in notifications:
            icon      = "📊" if n["notification_type"] == "MONTH_END_REPORT" else "⚠️"
            card_cls  = "notif-card-report" if n["notification_type"] == "MONTH_END_REPORT" else "notif-card-alert"
            read_badge = "" if n["is_read"] else " 🆕"
            wa_badge  = (
                '<span class="wa-sent">✓ WhatsApp Sent</span>'
                if n.get("whatsapp_status") == "SENT" else ""
            )
            st.markdown(f"""
            <div class="{card_cls}">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <strong>{icon} {n['title']}{read_badge}</strong>
                    {wa_badge}
                </div>
                <div style="color:#374151; font-size:0.9rem; margin-top:6px;">{n['message']}</div>
                <div style="color:#9CA3AF; font-size:0.78rem; margin-top:4px;">
                    {n['created_at'][5:16].replace('T', ' ')}
                </div>
            </div>
            """, unsafe_allow_html=True)
            if n.get("pdf_path") and _os.path.exists(str(n["pdf_path"])):
                with open(n["pdf_path"], "rb") as pf:
                    st.download_button(
                        label="📥 Download PDF",
                        data=pf.read(),
                        file_name=_os.path.basename(n["pdf_path"]),
                        mime="application/pdf",
                        key=f"notif_dl_{n['id']}"
                    )
    else:
        st.info("No notifications yet. Click **Generate & Send Report** above to trigger your first one.")
