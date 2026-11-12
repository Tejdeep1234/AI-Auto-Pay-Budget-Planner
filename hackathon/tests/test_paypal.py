"""
Unit tests for PayPalClient and PayPalWebhookHandler.
"""

import unittest
from database.db import DatabaseManager
from database.seed_data import seed_database
from paypal.client import PayPalClient
from paypal.webhook_handler import PayPalWebhookHandler
from agent.brain import AgentBrain

class TestPayPalIntegration(unittest.TestCase):
    def setUp(self):
        # Use an in-memory or temporary test DB
        self.db = DatabaseManager(db_path=":memory:")
        seed_database(self.db, force=True)
        self.paypal = PayPalClient(db=self.db)
        self.brain = AgentBrain(paypal_client=self.paypal, db=self.db)
        self.paypal_handler = PayPalWebhookHandler(agent_brain=self.brain, db=self.db)

    def test_suspend_and_activate_subscription(self):
        # Retrieve an active subscription
        subs = self.db.get_subscriptions(status="ACTIVE")
        self.assertTrue(len(subs) > 0)
        target_id = subs[0]["id"]

        # Suspend
        res_suspend = self.paypal.suspend_subscription(target_id, reason="Test suspension")
        self.assertTrue(res_suspend["success"])
        self.assertEqual(res_suspend["status"], "SUSPENDED")

        # Verify DB updated
        sub_after = self.db.get_subscription(target_id)
        self.assertEqual(sub_after["status"], "SUSPENDED")

        # Activate
        res_activate = self.paypal.activate_subscription(target_id, reason="Test activation")
        self.assertTrue(res_activate["success"])
        self.assertEqual(res_activate["status"], "ACTIVE")

        sub_reactivated = self.db.get_subscription(target_id)
        self.assertEqual(sub_reactivated["status"], "ACTIVE")

    def test_webhook_balance_drop_triggers_evaluation(self):
        # Simulating PayPal Webhook: CUSTOMER.BALANCE.DROPPED to $150 (below $300 safety threshold)
        webhook_payload = {
            "id": "WH-TEST-DROP-001",
            "event_type": "CUSTOMER.BALANCE.DROPPED",
            "summary": "PayPal Balance Alert: Available balance dropped",
            "resource": {
                "current_balance": {"currency_code": "USD", "value": "150.00"}
            }
        }

        res = self.paypal_handler.process_webhook_event(webhook_payload)
        self.assertEqual(res["status"], "success")
        self.assertTrue(res["agent_triggered"])
        
        # Verify account balance was updated
        account = self.db.get_account()
        self.assertEqual(account["balance"], 150.00)

        # Agent should have identified interception candidates
        agent_result = res["agent_result"]
        self.assertIn(agent_result["status"], ["ALERT_INTERCEPTED", "WARNING_BELOW_THRESHOLD"])
        self.assertTrue(len(agent_result["recommendations"]) > 0)

    def test_revise_subscription_tier(self):
        subs = self.db.get_subscriptions(status="ACTIVE")
        target_id = subs[0]["id"]
        old_amount = subs[0]["amount"]

        new_amount = round(old_amount * 0.5, 2)
        res = self.paypal.revise_subscription(target_id, "P-REVISED-BASIC", new_amount)
        self.assertTrue(res["success"])
        self.assertEqual(res["new_amount"], new_amount)

if __name__ == "__main__":
    unittest.main()
