"""
Configuration settings for The Smart Auto-Pay & Balance Budget Planner.
Supports environment variables or local defaults for PayPal Sandbox and AI Agent settings.
"""

import os
from pathlib import Path
from dataclasses import dataclass

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("BUDGET_AGENT_DB", str(BASE_DIR / "budget_agent.db"))

@dataclass
class AppConfig:
    # PayPal Configuration
    PAYPAL_CLIENT_ID: str = os.environ.get("PAYPAL_CLIENT_ID", "mock_paypal_client_id_sandbox")
    PAYPAL_CLIENT_SECRET: str = os.environ.get("PAYPAL_CLIENT_SECRET", "mock_paypal_secret_key")
    PAYPAL_ENV: str = os.environ.get("PAYPAL_ENV", "sandbox")  # 'sandbox' or 'live'
    PAYPAL_API_BASE: str = (
        "https://api-m.paypal.com" if PAYPAL_ENV == "live" else "https://api-m.sandbox.paypal.com"
    )
    MOCK_PAYPAL: bool = os.environ.get("MOCK_PAYPAL", "true").lower() in ("true", "1", "yes")

    # AI & Threshold Defaults
    DEFAULT_SAFETY_THRESHOLD: float = float(os.environ.get("DEFAULT_SAFETY_THRESHOLD", "300.00"))
    DEFAULT_OVERDRAFT_BUFFER: float = float(os.environ.get("DEFAULT_OVERDRAFT_BUFFER", "100.00"))
    AUTONOMOUS_INTERCEPT_MODE: bool = os.environ.get("AUTONOMOUS_MODE", "false").lower() in ("true", "1", "yes")
    
    # LLM / AI Integration
    OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
    AI_MODEL: str = os.environ.get("AI_MODEL", "gpt-4o-mini")

    # Server settings
    WEBHOOK_PORT: int = int(os.environ.get("WEBHOOK_PORT", "8000"))
    WEBHOOK_HOST: str = os.environ.get("WEBHOOK_HOST", "127.0.0.1")

config = AppConfig()
