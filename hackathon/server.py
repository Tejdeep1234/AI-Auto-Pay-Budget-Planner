"""
Asynchronous REST API and PayPal Webhook Receiver Server.
Built on Starlette and Uvicorn.
"""

import uvicorn
import json
import logging
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.requests import Request

from config import config
from database.db import get_db
from database.seed_data import seed_database
from paypal.client import PayPalClient
from paypal.webhook_handler import PayPalWebhookHandler
from agent.brain import AgentBrain

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BudgetServer")

# Initialize DB, Agent & Webhook Handler
db = get_db()
seed_database(db, force=False)
paypal = PayPalClient(db=db)
brain = AgentBrain(paypal_client=paypal, db=db)
webhook_handler = PayPalWebhookHandler(agent_brain=brain, db=db)

async def health(request: Request):
    account = db.get_account()
    return JSONResponse({
        "status": "healthy",
        "service": "The Smart Auto-Pay & Balance Budget Planner",
        "account_balance": account["balance"] if account else None,
        "paypal_engine": "mock_sandbox" if paypal.mock_mode else "live_paypal"
    })

async def handle_paypal_webhook(request: Request):
    """
    Receives incoming PayPal Webhook POST events.
    PayPal sends events such as CUSTOMER.BALANCE.DROPPED, PAYMENT.SALE.COMPLETED,
    BILLING.SUBSCRIPTION.SUSPENDED, etc.
    """
    try:
        body_bytes = await request.body()
        raw_body = body_bytes.decode("utf-8")
        payload = json.loads(raw_body)
        headers = dict(request.headers)

        # Webhook validation
        if not webhook_handler.verify_webhook_signature(headers, raw_body):
            return JSONResponse({"status": "error", "message": "Invalid webhook signature"}, status_code=400)

        # Process and trigger AI Agent
        result = webhook_handler.process_webhook_event(payload)
        return JSONResponse(result, status_code=200)

    except json.JSONDecodeError:
        return JSONResponse({"status": "error", "message": "Invalid JSON payload"}, status_code=400)
    except Exception as e:
        logger.error(f"Error handling webhook: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

async def trigger_agent_scan(request: Request):
    """Triggers an AI Agent evaluation of account thresholds and cashflow."""
    eval_result = brain.evaluate_account_thresholds(trigger_event="REST API On-Demand Scan")
    return JSONResponse(eval_result)

async def list_subscriptions(request: Request):
    subs = db.get_subscriptions()
    return JSONResponse({"count": len(subs), "subscriptions": subs})

async def pause_subscription(request: Request):
    sub_id = request.path_params["sub_id"]
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    reason = body.get("reason", "Manual API Intercept")
    result = brain.execute_pause(sub_id, reason=reason)
    return JSONResponse(result)

async def resume_subscription(request: Request):
    sub_id = request.path_params["sub_id"]
    result = brain.execute_resume(sub_id, reason="Manual API Resume")
    return JSONResponse(result)

async def get_balance(request: Request):
    account = db.get_account()
    return JSONResponse(account or {})

async def update_balance(request: Request):
    data = await request.json()
    new_bal = float(data.get("balance", 0.0))
    db.update_balance(new_bal)
    # Immediately trigger review
    eval_res = brain.evaluate_account_thresholds(trigger_event=f"API Balance Update to ${new_bal:.2f}")
    return JSONResponse({"balance": new_bal, "agent_evaluation": eval_res})

async def trigger_month_end_report(request: Request):
    """Generates month-end PDF, dispatches WhatsApp message, and logs in-app notification."""
    from notifications.scheduler import MonthEndScheduler
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    phone = body.get("phone", "+919876543210")
    force = body.get("force", True)
    scheduler = MonthEndScheduler(db=db, default_whatsapp=phone)
    result = scheduler.run_automated_month_end_cycle(whatsapp_number=phone, force=force)
    return JSONResponse(result)

async def list_notifications(request: Request):
    notifs = db.get_app_notifications(limit=50)
    return JSONResponse({"count": len(notifs), "notifications": notifs})

routes = [
    Route("/", health, methods=["GET"]),
    Route("/api/webhook/paypal", handle_paypal_webhook, methods=["POST"]),
    Route("/api/agent/scan", trigger_agent_scan, methods=["GET", "POST"]),
    Route("/api/subscriptions", list_subscriptions, methods=["GET"]),
    Route("/api/subscriptions/{sub_id}/pause", pause_subscription, methods=["POST"]),
    Route("/api/subscriptions/{sub_id}/resume", resume_subscription, methods=["POST"]),
    Route("/api/balance", get_balance, methods=["GET"]),
    Route("/api/balance", update_balance, methods=["POST"]),
    Route("/api/reports/month-end", trigger_month_end_report, methods=["POST"]),
    Route("/api/notifications", list_notifications, methods=["GET"]),
]

app = Starlette(debug=True, routes=routes)

def start_server():
    print(f"Starting Smart Auto-Pay Webhook Server on http://{config.WEBHOOK_HOST}:{config.WEBHOOK_PORT}...")
    uvicorn.run(app, host=config.WEBHOOK_HOST, port=config.WEBHOOK_PORT)

if __name__ == "__main__":
    start_server()
