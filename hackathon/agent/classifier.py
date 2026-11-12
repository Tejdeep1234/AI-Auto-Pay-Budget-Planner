"""
Subscription Utilization and Essentiality Classifier.
Calculates ROI, usage efficiency, and pause recommendation priority.
"""

from datetime import datetime
from typing import Dict, Any, List
from paypal.models import InterceptRecommendation

class SubscriptionClassifier:
    """
    Analyzes subscription usage metrics to detect draining, forgotten,
    or under-utilized recurring charges.
    """

    ESSENTIALITY_WEIGHTS = {
        "luxury": 2.0,       # High priority to pause when low on cash
        "negotiable": 1.4,   # Medium priority to pause
        "essential": 0.0     # Never auto-pause (e.g. utilities, medical, servers)
    }

    @classmethod
    def calculate_metrics(cls, sub: Dict[str, Any]) -> Dict[str, Any]:
        amount = float(sub.get("amount", 0.0))
        usage_days = int(sub.get("usage_days_last_30", 0))
        hours_used = float(sub.get("hours_used_last_30", 0.0))
        essentiality = sub.get("essentiality", "negotiable").lower()
        priority = int(sub.get("user_priority", 3))  # 1 to 5 (5 = most important)
        next_billing_str = sub.get("next_billing_date", "")

        # Days until next charge
        days_until_billing = 14
        if next_billing_str:
            try:
                billing_date = datetime.strptime(next_billing_str, "%Y-%m-%d").date()
                today = datetime.now().date()
                days_until_billing = max(0, (billing_date - today).days)
            except Exception:
                days_until_billing = 7

        # 1. Usage rate (0.0 to 1.0)
        usage_rate = min(1.0, usage_days / 30.0)

        # 2. Cost per hour of usage
        cost_per_hour = amount / max(1.0, hours_used) if hours_used > 0 else amount

        # 3. Under-utilization score (0.0 = heavily used, 1.0 = completely dormant)
        underutilization_score = 1.0 - (usage_rate * 0.7 + min(1.0, hours_used / 20.0) * 0.3)
        underutilization_score = max(0.0, min(1.0, underutilization_score))

        # 4. Urgency weight: upcoming charges within 1-5 days get highest urgency
        if days_until_billing <= 2:
            urgency_factor = 2.2
            urgency_level = "CRITICAL"
        elif days_until_billing <= 5:
            urgency_factor = 1.8
            urgency_level = "HIGH"
        elif days_until_billing <= 10:
            urgency_factor = 1.3
            urgency_level = "MODERATE"
        else:
            urgency_factor = 1.0
            urgency_level = "LOW"

        # 5. Essentiality & User Priority penalty
        ess_weight = cls.ESSENTIALITY_WEIGHTS.get(essentiality, 1.0)
        # Priority 1 (least important) -> factor 2.0; Priority 5 -> factor 0.2
        priority_factor = max(0.2, (6 - priority) / 3.0)

        # 6. Final Intercept / Pause Recommendation Score
        if sub.get("auto_pause_eligible", 1) == 0 or essentiality == "essential":
            pause_score = 0.0
        else:
            pause_score = round(amount * (underutilization_score ** 1.2) * ess_weight * priority_factor * urgency_factor, 2)

        # Categorization tags
        if sub.get("auto_pause_eligible", 1) == 0 or essentiality == "essential":
            drain_category = "PROTECTED_ESSENTIAL"
            action = "RETAIN"
        elif pause_score > 40.0:
            drain_category = "CRITICAL_DRAIN"
            action = "SUSPEND"
        elif pause_score > 15.0:
            drain_category = "MODERATE_DRAIN"
            action = "SUSPEND"
        elif hours_used > 15 and amount > 30.0:
            drain_category = "HIGH_VALUE_HIGH_COST"
            action = "DOWNGRADE"
        else:
            drain_category = "HEALTHY_USAGE"
            action = "RETAIN"

        return {
            "days_until_billing": days_until_billing,
            "usage_rate": round(usage_rate, 2),
            "cost_per_hour": round(cost_per_hour, 2),
            "underutilization_score": round(underutilization_score, 2),
            "urgency_level": urgency_level,
            "pause_score": pause_score,
            "drain_category": drain_category,
            "recommended_action": action
        }

    @classmethod
    def rank_for_interception(cls, subscriptions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ranks active subscriptions from highest drain/pause priority to lowest."""
        evaluated = []
        for s in subscriptions:
            if s.get("status") != "ACTIVE":
                continue
            metrics = cls.calculate_metrics(s)
            item = {**s, **metrics}
            evaluated.append(item)

        # Sort descending by pause recommendation score, then by billing proximity
        return sorted(evaluated, key=lambda x: (x["pause_score"], -x["days_until_billing"]), reverse=True)
