"""
Prompt templates and Natural Language Explanation Generator for the Smart Auto-Pay Agent.
Supports both LLM agent prompting and offline rule-based natural language generation.
"""

from typing import Dict, Any, List

SYSTEM_PROMPT = """
You are "Antigravity Smart Auto-Pay & Guardrail Agent", an autonomous financial protection assistant.
Your mission is to continuously monitor the user's available balance and upcoming recurring PayPal subscriptions,
predict overdraft hazards, and proactively intercept draining, forgotten, or under-utilized autopays before fees hit.

Guidelines:
1. Balance Safety: Always defend the user's Safety Threshold and Overdraft Buffer.
2. Prioritize Interception: Target luxury, zero-usage, and low-ROI subscriptions first. Never pause essential utilities or services marked non-eligible.
3. Be Actionable & Clear: Quantify exact dollars saved, upcoming billing dates, and days until overdraft avoided.
4. Transparency: Provide concise rationales explaining why each subscription was prioritized for pause or tier downgrade.
"""

class PromptGenerator:
    @staticmethod
    def generate_scan_prompt(account: Dict[str, Any], subscriptions: List[Dict[str, Any]], forecast: Dict[str, Any]) -> str:
        subs_text = "\n".join([
            f"- {s['name']} (${s['amount']:.2f}/mo, Next: {s['next_billing_date']}, Usage: {s.get('usage_days_last_30', 0)} days/mo, Priority: {s.get('user_priority', 3)}/5, Category: {s.get('category')})"
            for s in subscriptions if s.get("status") == "ACTIVE"
        ])
        return f"""
Account Balance: ${account.get('balance', 0.0):.2f}
Safety Threshold: ${account.get('safety_threshold', 300.0):.2f}
Overdraft Buffer: ${account.get('overdraft_buffer', 100.0):.2f}

Forecast Summary:
- Lowest Projected Balance: ${forecast.get('lowest_projected_balance', 0.0):.2f} on {forecast.get('lowest_balance_date')}
- Overdraft Risk Probability: {forecast.get('overdraft_risk_percentage', 0)}%
- Total Upcoming Autopay Drain: ${forecast.get('total_autopay_drain', 0.0):.2f}

Active PayPal Subscriptions:
{subs_text}

Evaluate which subscriptions must be paused or revised immediately to maintain balance guardrails.
"""

    @staticmethod
    def generate_rule_explanation(
        sub: Dict[str, Any],
        deficit: float,
        current_balance: float,
        safety_threshold: float,
        overdraft_buffer: float
    ) -> str:
        """
        Generates high-precision natural language reasoning for intercepted subscriptions
        using the Python predictive model.
        """
        name = sub["name"]
        amount = sub["amount"]
        days = sub.get("days_until_billing", 0)
        usage_days = sub.get("usage_days_last_30", 0)
        hours = sub.get("hours_used_last_30", 0.0)
        category = sub.get("category", "Service")
        cost_per_hr = sub.get("cost_per_hour", amount)

        # Contextual explanation logic
        if current_balance < overdraft_buffer:
            urgency_str = f"URGENT: Available balance (${current_balance:.2f}) is in the DANGER ZONE below your ${overdraft_buffer:.2f} overdraft buffer."
        elif current_balance < safety_threshold:
            urgency_str = f"ALERT: Available balance (${current_balance:.2f}) has dropped below your ${safety_threshold:.2f} safety guardrail."
        else:
            urgency_str = f"PREDICTIVE INTERCEPTION: Cashflow forecast indicates balance will breach safety thresholds within {days} days."

        if usage_days == 0:
            usage_str = f"Zero activity detected in the last 30 days (0 logins, 0.0 hours used). This is a completely dormant draining autopay."
        elif usage_days <= 2:
            usage_str = f"Extremely low utilization ({usage_days} day(s) used in last 30 days, ~{hours:.1f} hrs total), driving effective cost to ${cost_per_hr:.2f}/hour."
        else:
            usage_str = f"Moderate utilization ({usage_days} active days), but non-essential classification makes it optimal for temporary deferral."

        timing_str = f"Upcoming charge of ${amount:.2f} scheduled in {days} day(s)." if days > 0 else f"Charge of ${amount:.2f} is scheduled for TODAY."
        saving_str = f"Pausing this PayPal subscription immediately defends ${amount:.2f} towards your ${deficit:.2f} required reserve."

        return f"{urgency_str}\n• Subscription: {name} (${amount:.2f}/mo, {category})\n• Schedule: {timing_str}\n• Utilization: {usage_str}\n• Guardrail Impact: {saving_str}"
