"""
Unit tests for CashflowPredictor.
"""

import unittest
from datetime import datetime, timedelta
from agent.predictor import CashflowPredictor

class TestCashflowPredictor(unittest.TestCase):
    def setUp(self):
        self.predictor = CashflowPredictor(daily_discretionary_spend=10.0)
        today = datetime.now()
        self.today_str = today.strftime("%Y-%m-%d")

        self.subscriptions = [
            {
                "id": "SUB-1",
                "name": "Gym",
                "amount": 90.0,
                "next_billing_date": (today + timedelta(days=3)).strftime("%Y-%m-%d"),
                "status": "ACTIVE"
            },
            {
                "id": "SUB-2",
                "name": "Software",
                "amount": 60.0,
                "next_billing_date": (today + timedelta(days=5)).strftime("%Y-%m-%d"),
                "status": "ACTIVE"
            }
        ]

        self.cashflow_events = [
            {
                "title": "Paycheck",
                "event_type": "INCOME",
                "amount": 1000.0,
                "expected_date": (today + timedelta(days=10)).strftime("%Y-%m-%d")
            }
        ]

    def test_project_cashflow_detects_threshold_breach(self):
        # Starting with 200, threshold 300, buffer 50
        # In 3 days, sub 1 takes 90 -> balance dips significantly
        result = self.predictor.project_cashflow(
            current_balance=200.0,
            safety_threshold=300.0,
            overdraft_buffer=50.0,
            subscriptions=self.subscriptions,
            cashflow_events=self.cashflow_events,
            horizon_days=14
        )

        self.assertLess(result["lowest_projected_balance"], 50.0)
        self.assertGreater(result["overdraft_risk_percentage"], 70)
        self.assertGreater(result["threshold_deficit"], 0)

    def test_counterfactual_simulation_prevents_overdraft(self):
        sim = self.predictor.simulate_interventions(
            current_balance=180.0,
            safety_threshold=250.0,
            overdraft_buffer=50.0,
            subscriptions=self.subscriptions,
            cashflow_events=self.cashflow_events,
            candidate_ids_to_pause=["SUB-1", "SUB-2"]
        )

        self.assertGreater(sim["dollar_benefit"], 100.0)
        self.assertGreater(sim["risk_reduction_pct"], 0)
        self.assertGreaterEqual(sim["protected"]["lowest_projected_balance"], sim["baseline"]["lowest_projected_balance"])

if __name__ == "__main__":
    unittest.main()
