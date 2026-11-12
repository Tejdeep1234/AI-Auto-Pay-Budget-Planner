"""
Data classes and models for PayPal Subscriptions API and Webhooks.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime

@dataclass
class PayPalSubscription:
    id: str
    status: str  # ACTIVE, SUSPENDED, CANCELLED, EXPIRED
    status_update_time: str
    plan_id: str
    start_time: str
    quantity: str = "1"
    shipping_amount: Dict[str, str] = field(default_factory=lambda: {"currency_code": "USD", "value": "0.00"})
    subscriber: Dict[str, Any] = field(default_factory=lambda: {
        "email_address": "alex.morgan@example.com",
        "payer_id": "PAYER-MOCK-9988",
        "name": {"given_name": "Alex", "surname": "Morgan"}
    })
    billing_info: Dict[str, Any] = field(default_factory=dict)
    custom_id: Optional[str] = None

@dataclass
class PayPalWebhookEvent:
    id: str
    event_version: str
    create_time: str
    resource_type: str
    event_type: str
    summary: str
    resource: Dict[str, Any]

@dataclass
class InterceptRecommendation:
    subscription_id: str
    subscription_name: str
    vendor: str
    monthly_amount: float
    next_billing_date: str
    urgency_level: str  # CRITICAL, HIGH, MODERATE, LOW
    underutilization_score: float  # 0.0 to 1.0 (1.0 = completely unused/wasted)
    priority_score: float  # overall pause recommendation ranking
    reasoning: str
    action_type: str  # SUSPEND, DOWNGRADE, NOTIFY
    auto_executable: bool
