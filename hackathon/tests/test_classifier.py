"""
Unit tests for SubscriptionClassifier.
"""

import unittest
from datetime import datetime, timedelta
from agent.classifier import SubscriptionClassifier

class TestSubscriptionClassifier(unittest.TestCase):
    def setUp(self):
        today = datetime.now()
        self.sub_dormant = {
            "id": "I-DORMANT01",
            "name": "Dormant Luxury App",
            "vendor": "Ghost Corp",
            "category": "Software",
            "amount": 50.00,
            "next_billing_date": (today + timedelta(days=2)).strftime("%Y-%m-%d"),
            "status": "ACTIVE",
            "usage_days_last_30": 0,
            "hours_used_last_30": 0.0,
            "essentiality": "luxury",
            "user_priority": 1,
            "auto_pause_eligible": 1
        }
        self.sub_essential = {
            "id": "I-ESSENTIAL01",
            "name": "Power Grid Electric",
            "vendor": "Power Utility",
            "category": "Utilities",
            "amount": 120.00,
            "next_billing_date": (today + timedelta(days=5)).strftime("%Y-%m-%d"),
            "status": "ACTIVE",
            "usage_days_last_30": 30,
            "hours_used_last_30": 720.0,
            "essentiality": "essential",
            "user_priority": 5,
            "auto_pause_eligible": 0
        }
        self.sub_active_valuable = {
            "id": "I-ACTIVE01",
            "name": "Spotify Family",
            "vendor": "Spotify",
            "category": "Streaming",
            "amount": 16.99,
            "next_billing_date": (today + timedelta(days=10)).strftime("%Y-%m-%d"),
            "status": "ACTIVE",
            "usage_days_last_30": 28,
            "hours_used_last_30": 60.0,
            "essentiality": "negotiable",
            "user_priority": 4,
            "auto_pause_eligible": 1
        }

    def test_dormant_subscription_gets_high_pause_score(self):
        metrics = SubscriptionClassifier.calculate_metrics(self.sub_dormant)
        self.assertEqual(metrics["drain_category"], "CRITICAL_DRAIN")
        self.assertEqual(metrics["recommended_action"], "SUSPEND")
        self.assertGreater(metrics["pause_score"], 40.0)
        self.assertEqual(metrics["urgency_level"], "CRITICAL")
        self.assertEqual(metrics["underutilization_score"], 1.0)

    def test_essential_subscription_is_protected(self):
        metrics = SubscriptionClassifier.calculate_metrics(self.sub_essential)
        self.assertEqual(metrics["pause_score"], 0.0)
        self.assertEqual(metrics["recommended_action"], "RETAIN")

    def test_ranking_orders_dormant_before_active(self):
        subs = [self.sub_active_valuable, self.sub_essential, self.sub_dormant]
        ranked = SubscriptionClassifier.rank_for_interception(subs)
        self.assertEqual(ranked[0]["id"], "I-DORMANT01")

if __name__ == "__main__":
    unittest.main()
