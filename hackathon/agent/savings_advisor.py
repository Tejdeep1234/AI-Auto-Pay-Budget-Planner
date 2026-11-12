"""
Savings Advisor & Shortfall Analyzer.
Detects when available balance is less than upcoming daily/monthly recurring commitments,
specifically pinpoints unwanted/dormant payments, and formulates actionable ways to save.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List

class SavingsAdvisor:
    """
    Analyzes cash commitments vs. liquid balance to detect payment shortfalls
    and delivers tailored cost-reduction tactics.
    """

    @classmethod
    def analyze_commitments_and_shortfall(
        cls,
        available_balance: float,
        subscriptions: List[Dict[str, Any]],
        safety_threshold: float = 300.0,
        daily_baseline_spend: float = 12.0
    ) -> Dict[str, Any]:
        today = datetime.now().date()
        
        active_subs = [s for s in subscriptions if s.get("status") == "ACTIVE"]

        due_in_3d = []
        due_in_7d = []
        due_in_14d = []
        due_in_30d = []

        total_due_3d = 0.0
        total_due_7d = 0.0
        total_due_14d = 0.0
        total_due_30d = 0.0

        for s in active_subs:
            amt = float(s.get("amount", 0.0))
            date_str = s.get("next_billing_date")
            days_away = 14
            if date_str:
                try:
                    b_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    days_away = max(0, (b_date - today).days)
                except Exception:
                    days_away = 10
            
            sub_copy = {**s, "days_away": days_away}
            if days_away <= 3:
                due_in_3d.append(sub_copy)
                total_due_3d += amt
            if days_away <= 7:
                due_in_7d.append(sub_copy)
                total_due_7d += amt
            if days_away <= 14:
                due_in_14d.append(sub_copy)
                total_due_14d += amt
            due_in_30d.append(sub_copy)
            total_due_30d += amt

        # Daily baseline living expenses over 14 days
        projected_living_14d = daily_baseline_spend * 14.0
        total_required_14d = round(total_due_14d + projected_living_14d, 2)
        total_required_30d = round(total_due_30d + (daily_baseline_spend * 30.0), 2)

        # Shortfall calculations
        shortfall_7d = max(0.0, round(total_due_7d - available_balance, 2))
        shortfall_14d = max(0.0, round(total_required_14d - available_balance, 2))
        shortfall_30d = max(0.0, round(total_required_30d - available_balance, 2))

        has_immediate_shortfall = available_balance < total_due_7d
        has_runway_shortfall = available_balance < total_required_14d

        if has_immediate_shortfall:
            severity = "CRITICAL_DEFICIT"
            status_msg = f"URGENT DEFICIT: Balance (${available_balance:.2f}) cannot cover payments due in 7 days (${total_due_7d:.2f}). Deficit: ${shortfall_7d:.2f}"
        elif has_runway_shortfall:
            severity = "PROJECTED_DEFICIT"
            status_msg = f"RUNWAY DEFICIT: Balance (${available_balance:.2f}) will fall short of 14-day obligations (${total_required_14d:.2f}). Deficit: ${shortfall_14d:.2f}"
        elif available_balance < safety_threshold:
            severity = "GUARDRAIL_WARNING"
            status_msg = f"GUARDRAIL ALERT: Balance (${available_balance:.2f}) covers bills but violates your ${safety_threshold:.2f} safety floor."
        else:
            severity = "SOLVENT"
            status_msg = f"SOLVENT: Available balance (${available_balance:.2f}) covers upcoming commitments."

        # Identify unwanted / non-essential payments
        unwanted_payments = cls.identify_unwanted_payments(active_subs)

        # Formulate actionable ways to save
        ways_to_save = cls.formulate_ways_to_save(
            available_balance=available_balance,
            shortfall_14d=shortfall_14d,
            active_subs=active_subs,
            unwanted_payments=unwanted_payments
        )

        return {
            "available_balance": available_balance,
            "severity": severity,
            "status_message": status_msg,
            "has_shortfall": has_immediate_shortfall or has_runway_shortfall,
            "total_due_7d": round(total_due_7d, 2),
            "total_due_14d": round(total_due_14d, 2),
            "total_due_30d": round(total_due_30d, 2),
            "total_required_14d": total_required_14d,
            "shortfall_7d": shortfall_7d,
            "shortfall_14d": shortfall_14d,
            "shortfall_30d": shortfall_30d,
            "upcoming_7d_payments": due_in_7d,
            "unwanted_payments": unwanted_payments,
            "ways_to_save": ways_to_save
        }

    @classmethod
    def identify_unwanted_payments(cls, active_subs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Pinpoints unwanted, forgotten, and low-ROI recurring charges:
        1. Zero usage in last 30 days
        2. High cost per usage hour (> $25/hr)
        3. Luxury / discretionary category
        """
        flagged = []
        for s in active_subs:
            usage_days = int(s.get("usage_days_last_30", 0))
            hours_used = float(s.get("hours_used_last_30", 0.0))
            amount = float(s.get("amount", 0.0))
            essentiality = s.get("essentiality", "negotiable").lower()
            name = s.get("name", "Unknown")

            if essentiality == "essential" or s.get("auto_pause_eligible", 1) == 0:
                continue  # Never flag essential utility/infrastructure

            reasons = []
            cost_per_hr = amount / max(1.0, hours_used) if hours_used > 0 else amount

            if usage_days == 0:
                reasons.append("Zero usage detected in last 30 days (100% wasted money)")
            elif usage_days <= 2 and hours_used < 4.0:
                reasons.append(f"Extremely poor ROI: used only {usage_days} time(s) (~${cost_per_hr:.2f}/hour)")

            if essentiality == "luxury":
                reasons.append("Discretionary luxury classification")

            if reasons:
                flagged.append({
                    "id": s["id"],
                    "name": name,
                    "vendor": s.get("vendor", ""),
                    "amount": amount,
                    "category": s.get("category", ""),
                    "next_billing_date": s.get("next_billing_date"),
                    "reasons": reasons,
                    "primary_reason": reasons[0],
                    "recommendation": f"Pause via PayPal API to instantly save ${amount:.2f}/month"
                })

        # Sort by highest amount savings first
        return sorted(flagged, key=lambda x: x["amount"], reverse=True)

    @classmethod
    def formulate_ways_to_save(
        cls,
        available_balance: float,
        shortfall_14d: float,
        active_subs: List[Dict[str, Any]],
        unwanted_payments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Creates actionable, concrete ways to save amount and eliminate shortfalls:
        1. Instant Pausing of Dormant Subscriptions
        2. Tier Downgrading
        3. Billing Date Rescheduling
        4. Annual Discount Switching
        5. Discretionary Daily Spending Cap
        """
        tactics = []

        # Tactic 1: Immediate Autopay Interception
        if unwanted_payments:
            potential_pause_savings = sum(p["amount"] for p in unwanted_payments)
            tactics.append({
                "tactic": "⚡ Instant Subscription Interception",
                "savings_estimate": f"${potential_pause_savings:.2f}/month",
                "difficulty": "1-Click (Immediate)",
                "description": f"Pause {len(unwanted_payments)} dormant or under-utilized subscriptions ({', '.join(p['name'] for p in unwanted_payments[:3])}).",
                "impact": f"Instantly frees up ${potential_pause_savings:.2f} liquid cash to wipe out your ${shortfall_14d:.2f} shortfall." if shortfall_14d > 0 else f"Preserves ${potential_pause_savings:.2f}/mo into your emergency savings guardrail."
            })

        # Tactic 2: Tier Downgrade Optimization
        downgrade_candidates = []
        for s in active_subs:
            amt = float(s.get("amount", 0.0))
            if amt > 18.0 and s.get("essentiality") != "essential":
                est_savings = round(amt * 0.35, 2)
                downgrade_candidates.append((s["name"], est_savings))

        if downgrade_candidates:
            total_downgrade_savings = sum(s[1] for s in downgrade_candidates)
            c_names = ", ".join(s[0] for s in downgrade_candidates[:2])
            tactics.append({
                "tactic": "📉 Subscription Tier Downgrade",
                "savings_estimate": f"${total_downgrade_savings:.2f}/month",
                "difficulty": "Easy (Keep account, downgrade plan)",
                "description": f"Switch premium tiers to standard on services like {c_names} (e.g. 4K to HD, Family to Individual).",
                "impact": f"Saves up to ${total_downgrade_savings:.2f} every month without losing service access."
            })

        # Tactic 3: Billing Date Rescheduling
        tactics.append({
            "tactic": "📅 Paycheck-Aligned Billing Rescheduling",
            "savings_estimate": "$0 cost / Overdraft Prevention",
            "difficulty": "Moderate (Update billing date in PayPal)",
            "description": "Shift recurring billing dates of large charges to 2-3 days AFTER your scheduled paycheck arrives.",
            "impact": "Eliminates cashflow dips between paychecks and permanently prevents overdraft penalties ($35/incident)."
        })

        # Tactic 4: Annual Switch Discount
        essential_candidates = [s for s in active_subs if s.get("essentiality") == "essential"]
        if essential_candidates:
            est_annual_discount = round(sum(float(s["amount"]) for s in essential_candidates) * 0.18, 2)
            tactics.append({
                "tactic": "🏷️ Annual Billing Switch (15-20% Off)",
                "savings_estimate": f"${est_annual_discount * 12:.2f}/year (~${est_annual_discount:.2f}/mo)",
                "difficulty": "Planned",
                "description": "Convert essential subscriptions you keep year-round (Cloud hosting, productivity) to annual upfront billing.",
                "impact": "Vendors typically offer 2 months free, locking in recurring baseline savings."
            })

        # Tactic 5: Daily Discretionary Budget Cap
        if shortfall_14d > 0:
            suggested_cap = max(5.0, round((available_balance * 0.4) / 14.0, 2))
            tactics.append({
                "tactic": "🎯 Dynamic Daily Spend Guardrail",
                "savings_estimate": f"Defends ${shortfall_14d:.2f} runway",
                "difficulty": "Behavioral",
                "description": f"Cap non-essential daily debit spending at ${suggested_cap:.2f}/day until your next income deposit.",
                "impact": "Guarantees your account stays in the safe zone until new funds arrive."
            })

        return tactics
