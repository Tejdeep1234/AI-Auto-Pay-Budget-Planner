"""
Predictive Cashflow Forecaster and Overdraft Risk Engine.
Projects daily balance trajectories over 14-30 days and assesses overdraft probabilities.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

class CashflowPredictor:
    """
    Simulates upcoming daily balances by evaluating current balance, scheduled income,
    and upcoming active PayPal subscription charges.
    """

    def __init__(self, daily_discretionary_spend: float = 12.0):
        self.daily_discretionary_spend = daily_discretionary_spend

    def project_cashflow(
        self,
        current_balance: float,
        safety_threshold: float,
        overdraft_buffer: float,
        subscriptions: List[Dict[str, Any]],
        cashflow_events: List[Dict[str, Any]],
        horizon_days: int = 14,
        paused_subscription_ids: List[str] = None
    ) -> Dict[str, Any]:
        """
        Runs a day-by-day cashflow simulation over the specified horizon.
        paused_subscription_ids allows what-if counterfactual simulation.
        """
        paused_set = set(paused_subscription_ids or [])
        today = datetime.now().date()
        daily_projection = []

        running_balance = current_balance
        lowest_balance = current_balance
        lowest_balance_date = today.strftime("%Y-%m-%d")
        days_to_threshold_breach = None
        days_to_overdraft = None
        total_autopay_drain = 0.0

        # Group subscriptions by next billing date
        sub_by_date = {}
        for sub in subscriptions:
            if sub["id"] in paused_set:
                continue
            if sub.get("status") != "ACTIVE":
                continue
            b_date = sub.get("next_billing_date")
            if b_date:
                sub_by_date.setdefault(b_date, []).append(sub)

        # Group cashflow events (paychecks, fixed bills) by date
        events_by_date = {}
        for ev in cashflow_events:
            e_date = ev.get("expected_date")
            if e_date:
                events_by_date.setdefault(e_date, []).append(ev)

        # Iterate through each day in the horizon
        for day_offset in range(horizon_days + 1):
            sim_date = today + timedelta(days=day_offset)
            date_str = sim_date.strftime("%Y-%m-%d")

            day_income = 0.0
            day_expenses = 0.0
            day_autopays = 0.0
            transactions_today = []

            # 1. Scheduled Income / Fixed events
            if date_str in events_by_date:
                for ev in events_by_date[date_str]:
                    amt = float(ev["amount"])
                    if ev["event_type"].upper() == "INCOME":
                        day_income += amt
                        transactions_today.append(f"+${amt:.2f} {ev['title']}")
                    else:
                        day_expenses += amt
                        transactions_today.append(f"-${amt:.2f} {ev['title']}")

            # 2. Upcoming PayPal Subscriptions
            if date_str in sub_by_date:
                for sub in sub_by_date[date_str]:
                    amt = float(sub["amount"])
                    day_autopays += amt
                    total_autopay_drain += amt
                    transactions_today.append(f"-${amt:.2f} {sub['name']} (Autopay)")

            # 3. Discretionary daily baseline (if not day 0)
            if day_offset > 0:
                day_expenses += self.daily_discretionary_spend

            running_balance = round(running_balance + day_income - day_expenses - day_autopays, 2)

            if running_balance < lowest_balance:
                lowest_balance = running_balance
                lowest_balance_date = date_str

            # Check threshold breaches
            if running_balance < safety_threshold and days_to_threshold_breach is None:
                days_to_threshold_breach = day_offset

            if running_balance < overdraft_buffer and days_to_overdraft is None:
                days_to_overdraft = day_offset

            daily_projection.append({
                "day_offset": day_offset,
                "date": date_str,
                "projected_balance": running_balance,
                "income": round(day_income, 2),
                "autopays": round(day_autopays, 2),
                "other_expenses": round(day_expenses, 2),
                "transactions": transactions_today,
                "breaches_threshold": running_balance < safety_threshold,
                "breaches_buffer": running_balance < overdraft_buffer
            })

        # Calculate overdraft risk probability (0% - 100%)
        risk_percentage = 0
        if lowest_balance <= 0:
            risk_percentage = 98
        elif lowest_balance < overdraft_buffer:
            # Scale from 70% to 95%
            deficit = overdraft_buffer - lowest_balance
            risk_percentage = min(95, int(70 + (deficit / max(1.0, overdraft_buffer)) * 25))
        elif lowest_balance < safety_threshold:
            # Scale from 30% to 69%
            deficit = safety_threshold - lowest_balance
            risk_percentage = min(69, int(30 + (deficit / max(1.0, safety_threshold - overdraft_buffer)) * 39))
        else:
            risk_percentage = 5

        # Deficit needed to stay above safety threshold
        threshold_deficit = max(0.0, round(safety_threshold - lowest_balance, 2))
        overdraft_deficit = max(0.0, round(overdraft_buffer - lowest_balance, 2))

        return {
            "daily_projection": daily_projection,
            "lowest_projected_balance": lowest_balance,
            "lowest_balance_date": lowest_balance_date,
            "days_to_threshold_breach": days_to_threshold_breach,
            "days_to_overdraft": days_to_overdraft,
            "overdraft_risk_percentage": risk_percentage,
            "threshold_deficit": threshold_deficit,
            "overdraft_deficit": overdraft_deficit,
            "total_autopay_drain": round(total_autopay_drain, 2)
        }

    def simulate_interventions(
        self,
        current_balance: float,
        safety_threshold: float,
        overdraft_buffer: float,
        subscriptions: List[Dict[str, Any]],
        cashflow_events: List[Dict[str, Any]],
        candidate_ids_to_pause: List[str]
    ) -> Dict[str, Any]:
        """
        Compares baseline forecast (no pauses) against counterfactual forecast (with candidates paused).
        """
        baseline = self.project_cashflow(
            current_balance=current_balance,
            safety_threshold=safety_threshold,
            overdraft_buffer=overdraft_buffer,
            subscriptions=subscriptions,
            cashflow_events=cashflow_events,
            paused_subscription_ids=[]
        )

        with_guardrail = self.project_cashflow(
            current_balance=current_balance,
            safety_threshold=safety_threshold,
            overdraft_buffer=overdraft_buffer,
            subscriptions=subscriptions,
            cashflow_events=cashflow_events,
            paused_subscription_ids=candidate_ids_to_pause
        )

        dollar_benefit = round(with_guardrail["lowest_projected_balance"] - baseline["lowest_projected_balance"], 2)
        risk_reduction = baseline["overdraft_risk_percentage"] - with_guardrail["overdraft_risk_percentage"]

        return {
            "baseline": baseline,
            "protected": with_guardrail,
            "dollar_benefit": dollar_benefit,
            "risk_reduction_pct": risk_reduction,
            "overdraft_prevented": (baseline["lowest_projected_balance"] < overdraft_buffer) and (with_guardrail["lowest_projected_balance"] >= overdraft_buffer)
        }
