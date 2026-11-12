"""
WhatsApp & In-App Notification Delivery System.
Sends month-end expenditure PDF reports via:
  1. WhatsApp Business API (Twilio or Meta Cloud API)
  2. In-App push notifications stored in SQLite and shown in Streamlit dashboard
"""

import os
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any

logger = logging.getLogger("NotificationService")

# ─────────────────────────────────────────────────────────────────
# WhatsApp Delivery Engine
# Supports:
#   - Twilio WhatsApp Sandbox (dev mode, zero-config mock)
#   - Meta WhatsApp Cloud API (production)
# ─────────────────────────────────────────────────────────────────

class WhatsAppNotifier:
    """
    Sends WhatsApp messages with optional PDF media attachment.
    Falls back to rich local simulation when credentials are absent.
    """

    def __init__(self):
        self.twilio_sid       = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.twilio_token     = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.twilio_from      = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
        self.meta_token       = os.environ.get("META_WA_TOKEN", "")
        self.meta_phone_id    = os.environ.get("META_WA_PHONE_NUMBER_ID", "")
        self.mock_mode        = not (self.twilio_sid or self.meta_token)

    # ── Twilio path ──────────────────────────────────────────────
    def _send_via_twilio(self, to_number: str, body: str, pdf_path: Optional[str]) -> Dict[str, Any]:
        try:
            from twilio.rest import Client
            client = Client(self.twilio_sid, self.twilio_token)
            msg_kwargs = {
                "from_": self.twilio_from,
                "body": body,
                "to": f"whatsapp:{to_number}"
            }
            if pdf_path and os.path.exists(pdf_path):
                msg_kwargs["media_url"] = [f"file://{pdf_path}"]   # local dev; use public URL in prod
            msg = client.messages.create(**msg_kwargs)
            return {"success": True, "provider": "Twilio", "sid": msg.sid}
        except ImportError:
            logger.warning("twilio package not installed — switching to mock.")
            return self._mock_send(to_number, body, pdf_path)
        except Exception as e:
            logger.error(f"Twilio send failed: {e}")
            return {"success": False, "provider": "Twilio", "error": str(e)}

    # ── Meta Cloud API path ───────────────────────────────────────
    def _send_via_meta(self, to_number: str, body: str, pdf_path: Optional[str]) -> Dict[str, Any]:
        try:
            import requests
            url = f"https://graph.facebook.com/v18.0/{self.meta_phone_id}/messages"
            headers = {
                "Authorization": f"Bearer {self.meta_token}",
                "Content-Type": "application/json"
            }
            payload: Dict[str, Any] = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {"body": body}
            }
            if pdf_path and os.path.exists(pdf_path):
                # Upload document first then send as document message
                payload["type"] = "document"
                payload["document"] = {
                    "link": f"file://{pdf_path}",
                    "caption": "Month-End Budget Report",
                    "filename": os.path.basename(pdf_path)
                }
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code == 200:
                return {"success": True, "provider": "Meta Cloud API", "response": resp.json()}
            return {"success": False, "provider": "Meta Cloud API",
                    "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            logger.error(f"Meta WA send failed: {e}")
            return {"success": False, "provider": "Meta Cloud API", "error": str(e)}

    # ── Mock / simulation path ────────────────────────────────────
    def _mock_send(self, to_number: str, body: str, pdf_path: Optional[str]) -> Dict[str, Any]:
        logger.info(f"[MOCK WhatsApp] → {to_number}\n{body}")
        if pdf_path:
            logger.info(f"[MOCK WhatsApp] PDF attachment: {pdf_path}")
        return {
            "success": True,
            "provider": "Mock Sandbox",
            "to": to_number,
            "body_preview": body[:120],
            "pdf_attached": pdf_path is not None and os.path.exists(str(pdf_path)),
            "timestamp": datetime.now().isoformat()
        }

    def send(self, to_number: str, body: str, pdf_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Dispatches the WhatsApp message through the best available provider.
        Priority: Twilio → Meta Cloud API → Mock Sandbox
        """
        if self.mock_mode:
            return self._mock_send(to_number, body, pdf_path)
        if self.twilio_sid:
            return self._send_via_twilio(to_number, body, pdf_path)
        return self._send_via_meta(to_number, body, pdf_path)


# ─────────────────────────────────────────────────────────────────
# Combined Report Delivery Service
# ─────────────────────────────────────────────────────────────────

class ReportDeliveryService:
    """
    Orchestrates the complete month-end report delivery pipeline:
      1. Generates the PDF via MonthEndReportGenerator
      2. Sends it over WhatsApp with a formatted summary message
      3. Creates an in-app notification record in SQLite
      4. Returns delivery metadata for display in the dashboard
    """

    def __init__(self, db=None):
        from database.db import get_db
        self.db = db or get_db()
        self.wa = WhatsAppNotifier()

    def build_whatsapp_message(self, account: Dict[str, Any],
                                expenditure_by_category: list,
                                total_spent: float,
                                transaction_count: int,
                                total_saved: float) -> str:
        """Formats the WhatsApp message body with key financial highlights."""
        from datetime import datetime
        month = datetime.now().strftime("%B %Y")
        name = account.get("user_name", "User")
        balance = account.get("balance", 0.0)
        threshold = account.get("safety_threshold", 300.0)
        guard_status = "SAFE ✅" if balance >= threshold else "BELOW THRESHOLD ⚠️"

        top_cats = expenditure_by_category[:3]
        cat_lines = "\n".join(
            f"  • {c['category']}: ${c['total_spent']:.2f} ({c['transaction_count']} transactions)"
            for c in top_cats
        )

        return (
            f"📊 *Month-End Budget Report — {month}*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 *Account:* {name}\n"
            f"💰 *Available Balance:* ${balance:.2f}  [{guard_status}]\n"
            f"🛡️ *Safety Guardrail:* ${threshold:.2f}\n\n"
            f"📋 *Month Expenditure Summary:*\n"
            f"  Total Spent: *${total_spent:.2f}* across *{transaction_count} transactions*\n\n"
            f"🏷️ *Top Spending Categories:*\n{cat_lines}\n\n"
            f"🤖 *AI Guardrail Savings:* ${total_saved:.2f} preserved by auto-pausing subscriptions\n\n"
            f"📄 Your full Month-End PDF report is attached.\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_Smart Auto-Pay & Balance Budget Planner_"
        )

    def deliver_month_end_report(self,
                                  to_whatsapp_number: str = "+1234567890",
                                  user_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Full pipeline: generate PDF → send WhatsApp → create in-app notification.
        """
        from reports.pdf_generator import MonthEndReportGenerator

        # Step 1: Generate PDF
        try:
            gen = MonthEndReportGenerator()
            pdf_path = gen.generate_monthly_report(user_name=user_name)
            pdf_generated = True
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            pdf_path = None
            pdf_generated = False

        # Step 2: Gather data for WhatsApp message
        account = self.db.get_account() or {}
        transactions = self.db.get_monthly_transactions(limit=200)
        expenditure_by_category = self.db.get_expenditure_by_category()
        agent_actions = self.db.get_agent_actions(limit=50)

        total_spent = round(sum(t["amount"] for t in transactions), 2)
        total_saved = round(sum(a.get("savings_amount", 0) for a in agent_actions
                                if a.get("savings_amount")), 2)
        month_label = datetime.now().strftime("%B %Y")

        wa_body = self.build_whatsapp_message(
            account=account,
            expenditure_by_category=expenditure_by_category,
            total_spent=total_spent,
            transaction_count=len(transactions),
            total_saved=total_saved
        )

        # Step 3: Send via WhatsApp
        wa_result = self.wa.send(
            to_number=to_whatsapp_number,
            body=wa_body,
            pdf_path=pdf_path
        )

        # Step 4: Store in-app notification in SQLite
        notif_title = f"📊 Month-End Report Ready — {month_label}"
        notif_msg = (
            f"Your {month_label} expenditure report has been generated and sent to WhatsApp ({to_whatsapp_number}). "
            f"Total spent: ${total_spent:.2f} | AI Savings: ${total_saved:.2f}. "
            f"Tap to view the full PDF breakdown."
        )
        notif_id = self.db.add_app_notification(
            title=notif_title,
            message=notif_msg,
            notification_type="MONTH_END_REPORT",
            pdf_path=pdf_path,
            whatsapp_status="SENT" if wa_result.get("success") else "FAILED"
        )

        # Also add a threshold alert notification if below guardrail
        balance = account.get("balance", 0.0)
        threshold = account.get("safety_threshold", 300.0)
        if balance < threshold:
            self.db.add_app_notification(
                title="⚠️ Balance Below Safety Guardrail",
                message=(
                    f"Your balance of ${balance:.2f} is below your ${threshold:.2f} safety threshold. "
                    f"The AI Agent has identified subscriptions to pause. Tap for details."
                ),
                notification_type="GUARDRAIL_ALERT",
                pdf_path=None,
                whatsapp_status="N/A"
            )

        return {
            "pdf_generated": pdf_generated,
            "pdf_path": pdf_path,
            "whatsapp": wa_result,
            "in_app_notification_id": notif_id,
            "total_spent": total_spent,
            "total_saved": total_saved,
            "transaction_count": len(transactions),
            "month": month_label,
            "timestamp": datetime.now().isoformat()
        }
