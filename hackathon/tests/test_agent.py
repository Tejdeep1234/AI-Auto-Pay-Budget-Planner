"""
Unit tests for AgentBrain.
"""

import unittest
from database.db import DatabaseManager
from database.seed_data import seed_database
from paypal.client import PayPalClient
from agent.brain import AgentBrain

class TestAgentBrain(unittest.TestCase):
    def setUp(self):
        self.db = DatabaseManager(db_path=":memory:")
        seed_database(self.db, force=True)
        self.paypal = PayPalClient(db=self.db)
        self.brain = AgentBrain(paypal_client=self.paypal, db=self.db)

    def test_evaluate_thresholds_generates_recommendations(self):
        # Current seeded balance is $345.50, threshold is $300, buffer is $100
        # If we simulate balance dropping to $220.00:
        self.db.update_balance(220.00)

        eval_result = self.brain.evaluate_account_thresholds(trigger_event="Simulated Drop Test")
        self.assertEqual(eval_result["status"], "ALERT_INTERCEPTED")
        self.assertGreater(len(eval_result["recommendations"]), 0)

        # Check top recommendation
        top_rec = eval_result["recommendations"][0]
        self.assertIn("Adobe", top_rec["subscription_name"])
        self.assertEqual(top_rec["urgency_level"], "CRITICAL")
        self.assertTrue("ALERT" in top_rec["explanation"] or "URGENT" in top_rec["explanation"])

    def test_autonomous_mode_auto_pauses(self):
        # Enable autonomous mode
        self.db.update_thresholds(safety_threshold=300.0, overdraft_buffer=100.0, autonomous_mode=True)
        self.db.update_balance(180.00)

        eval_result = self.brain.evaluate_account_thresholds(trigger_event="Autonomous Trigger Test")
        self.assertGreater(len(eval_result["actions_taken"]), 0)

        # Check that target subscription status changed to SUSPENDED in DB
        paused_id = eval_result["actions_taken"][0]["subscription_id"]
        sub = self.db.get_subscription(paused_id)
        self.assertEqual(sub["status"], "SUSPENDED")

    def test_ask_agent_conversational_queries(self):
        reply = self.brain.ask_agent("Why should I pause Metro gym?")
        self.assertIn("Metro", reply)
        self.assertIn("workout hour", reply)

        reply_forecast = self.brain.ask_agent("What is my overdraft risk?")
        self.assertIn("Overdraft", reply_forecast)
        self.assertIn("Balance", reply_forecast)

if __name__ == "__main__":
    unittest.main()
