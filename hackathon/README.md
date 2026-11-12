# 🛡️ The Smart Auto-Pay & Balance Budget Planner

> **An autonomous financial protection agent that continuously reviews account thresholds to intercept draining subscriptions and build dynamic savings guardrails before overdraft fees hit.**

---

## 🌟 Executive Summary

* **What it does:** Continuously reviews user account thresholds, predicts upcoming overdraft hazards, and proactively intercepts draining or forgotten subscriptions to defend dynamic savings guardrails.
* **How it works:** The model actively checks the user's available balance and upcoming recurring cycles. If the balance drops below a set threshold (or is forecasted to plunge into overdraft), the AI identifies under-utilized or non-essential autopays and prompts the user (or automatically acts) to pause them via the PayPal Subscriptions API before overdraft fees occur.
* **The Tech Stack:**
  * **AI Layer:** Hybrid rule-based predictive system featuring a Python-based analysis model, dynamic 14-day cashflow forecast simulation, multi-factor utilization classifier, and customizable LLM agent prompt.
  * **PayPal Integration:** PayPal Subscriptions API (`/v1/billing/subscriptions/{id}/suspend`, `activate`, `revise`) combined with real-time Webhooks for balance drop alerts and payment lifecycle events.
  * **Interface & Tooling:** Interactive Streamlit Dashboard, Asynchronous Starlette/Uvicorn REST & Webhook Server, and Command-Line Interface (`agent_cli.py`).

---

## 📐 Architecture Overview

```
                               ┌────────────────────────────────────────────────────────┐
                               │                    PAYPAL ECOSYSTEM                    │
                               │  - PayPal Subscriptions API (v1)                       │
                               │  - PayPal Webhook Alerts (BALANCE.DROPPED, SALE.COMPL) │
                               └──────────────┬────────────────────────▲────────────────┘
                                              │ Inbound                │ Outbound
                                              │ Webhooks               │ Suspend/Revise
                                              ▼                        │ API Calls
┌──────────────────────────────────────────────────────────────────────┴─────────────────────────────────┐
│                           SMART AUTO-PAY & BALANCE BUDGET PLANNER AGENT                                 │
│                                                                                                        │
│   ┌────────────────────────────────┐         ┌─────────────────────────────────────────────────────┐   │
│   │   Real-Time Ingestion Engine   │         │                  AI AGENT BRAIN                     │   │
│   │   - Webhook Signature Verifier │────────▶│  1. Cashflow Forecaster (14-Day Trajectory)         │   │
│   │   - Balance Drop Interceptor   │         │  2. Overdraft Risk Probability Calculator           │   │
│   │   - Transaction Sync Router    │         │  3. Subscription Utilization & Essentiality Model   │   │
│   └────────────────────────────────┘         │  4. Interception Prioritization Algorithm           │   │
│                                              │  5. Autonomous / Human-in-the-Loop Interceptor      │   │
│                                              └──────────────────────────┬──────────────────────────┘   │
│                                                                         │                              │
│   ┌────────────────────────────────┐         ┌──────────────────────────▼──────────────────────────┐   │
│   │       SQLite Data Store        │         │              Multi-Modal Interfaces                 │   │
│   │   - User Balance & Thresholds  │◀────────│  • Interactive Streamlit Dashboard (app.py)         │   │
│   │   - PayPal Subscriptions Sync  │         │  • REST API & Webhook Server (server.py)            │   │
│   │   - Agent Audit & Decision Log │         │  • CLI Command & Simulation Suite (agent_cli.py)    │   │
│   └────────────────────────────────┘         └─────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🧠 How the AI Layer Works

### 1. Utilization & Drain Scoring
Each recurring subscription is evaluated on multiple behavioral and financial dimensions:

$$\text{Underutilization Score} = 1.0 - \left( \frac{\text{Usage Days}}{30} \times 0.7 + \min\left(1.0, \frac{\text{Hours Used}}{20}\right) \times 0.3 \right)$$

$$\text{Cost Per Hour} = \frac{\text{Monthly Amount}}{\max(1.0, \text{Hours Used})}$$

$$\text{Pause Priority Score} = \text{Amount} \times (\text{Underutilization})^{1.2} \times \text{Essentiality Weight} \times \text{Priority Factor} \times \text{Urgency Factor}$$

* **Classification Tiers:**
  * **Critical Drain:** High cost, near-zero utilization, non-essential (e.g., *Adobe Creative Cloud* at \$54.99/mo with 0 hours, *Metro Elite Gym* at \$89.00/mo with 1 visit).
  * **Moderate Drain:** Discretionary services with declining usage (e.g., *Gourmet Meal Kit*).
  * **Protected Essential:** Core utilities and critical hosting infrastructure (e.g., *City Electric Power*, *AWS/Database Backup*) are strictly protected from pauses (`auto_pause_eligible = 0`).

### 2. Predictive 14-Day Cashflow Forecaster
The model projects running daily balances $B(t)$ across a 14-to-30 day horizon:

$$B(t) = B(t-1) + \text{Income}(t) - \sum \text{ActiveSubscriptions}(t) - \text{FixedDebits}(t) - \text{BaselineSpend}(t)$$

* Identifies the exact day when balances will breach the **Safety Threshold** ($300 default) or dip below the **Overdraft Buffer** ($100 default).
* Calculates the exact **Target Deficit** required to stay solvent until the next scheduled income (e.g., paycheck).

### 3. Counterfactual Simulation
The AI compares the baseline trajectory against a counterfactual timeline where candidate subscriptions are paused, providing quantifiable proof of overdraft prevention:
* Lowest projected balance before: `-$225.45` ❌
* Lowest projected balance after AI interception: `+$203.04` ✅
* **Overdraft fee avoided: 100%**

---

## 💳 PayPal Integration

### Supported Endpoints & Actions
1. **List & Query Subscriptions:** Syncs metadata, billing cycle, status, and plans.
2. **Suspend / Pause Subscription:**
   * Endpoint: `POST /v1/billing/subscriptions/{id}/suspend`
   * Reason: `"Paused by Smart Auto-Pay Guardrail: Balance below threshold"`
3. **Activate / Resume Subscription:**
   * Endpoint: `POST /v1/billing/subscriptions/{id}/activate`
   * Reason: `"Resumed by Smart Auto-Pay Agent: Account balance restored"`
4. **Revise Subscription Tier (Downgrade):**
   * Endpoint: `POST /v1/billing/subscriptions/{id}/revise`
5. **Real-Time Webhook Events:**
   * `CUSTOMER.BALANCE.DROPPED`: Triggers immediate re-evaluation.
   * `PAYMENT.SALE.COMPLETED`: Updates balance and checks remaining buffer.
   * `BILLING.SUBSCRIPTION.SUSPENDED` / `ACTIVATED`: Keeps local state in sync.

> **Zero-Config Sandbox Emulation:** Works immediately out of the box with realistic PayPal responses and HTTP 204 status codes. When live sandbox credentials (`PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`) are configured, it connects directly to `https://api-m.sandbox.paypal.com`.

---

## 🚀 Quick Start Guide

### 1. Requirements
* Python 3.10+
* Standard libraries: `sqlite3`, `json`, `datetime`
* Pre-installed packages: `streamlit`, `starlette`, `uvicorn`, `requests`, `pandas`

### 2. Launch the Streamlit Dashboard
```bash
streamlit run app.py
```
Open your browser to `http://localhost:8501`.

### 3. Launch the REST API & Webhook Server
```bash
python server.py
```
Webhook receiver is live at `http://127.0.0.1:8000/api/webhook/paypal`.

### 4. Run CLI Commands & Simulations
```bash
# Evaluate current account thresholds & cashflow
python agent_cli.py scan

# List all active PayPal subscriptions
python agent_cli.py subs

# Ask the AI agent natural language questions
python agent_cli.py ask "Why should I pause Metro Gym and Adobe?"

# Simulate a PayPal balance drop webhook to $175
python agent_cli.py webhook-drop 175.00

# Pause a subscription via PayPal API
python agent_cli.py pause I-ADOBECC9921

# Resume a paused subscription
python agent_cli.py resume I-ADOBECC9921

# Reset demonstration state
python agent_cli.py reset
```

### 5. Run the Automated Test Suite
```bash
python -m unittest discover -s tests -v
```
All 11 unit tests verify:
* Utilization and essentiality scoring algorithms
* Predictive 14-day cashflow simulation and deficit calculations
* PayPal API client suspension/activation/revision routines
* Real-time balance drop webhook ingestion and AI agent auto-triggers
* Conversational AI queries and audit trails

---

## 📁 Repository Structure

```
hackathon/
├── app.py                     # High-fidelity Streamlit Web Application
├── server.py                  # Starlette Webhook Server & REST API
├── agent_cli.py               # CLI tool for terminal-based control & simulations
├── config.py                  # System configuration & environment settings
├── requirements.txt           # Project dependencies
├── README.md                  # Comprehensive documentation
├── agent/
│   ├── __init__.py
│   ├── brain.py               # AI Agent Brain & Autonomous Decision Engine
│   ├── predictor.py           # Predictive Cashflow & Overdraft Risk Calculator
│   ├── classifier.py          # Subscription Utilization & Essentiality Classifier
│   └── prompt_templates.py    # LLM Prompts & Rule Explanations
├── paypal/
│   ├── __init__.py
│   ├── client.py              # PayPal Subscriptions API Client (Live + Mock Sandbox)
│   ├── webhook_handler.py     # Real-time Webhook listener & event dispatcher
│   └── models.py              # PayPal data structures (Subscription, WebhookEvent)
├── database/
│   ├── __init__.py
│   ├── db.py                  # SQLite database engine, migrations & queries
│   └── seed_data.py           # Realistic seed data (8 subscriptions, cashflow events)
└── tests/
    ├── __init__.py
    ├── test_classifier.py     # Tests for utilization & pause recommendation ranking
    ├── test_predictor.py      # Tests for cashflow forecasting & overdraft detection
    ├── test_paypal.py         # Tests for PayPal API client & webhook handler
    └── test_agent.py          # End-to-end tests for AI agent evaluation & auto-pause
```

---

## 🏆 Key Innovations

1. **Continuous Predictive Guardrails:** Instead of reacting after an account is overdrafted, the agent predicts future cashflow breaches up to 14 days in advance.
2. **Behavioral ROI Scoring:** Distinguishes between frequently used high-value subscriptions (e.g., *Netflix*, *Spotify*) and dormant wallet drains (e.g., *unused gym memberships*, *forgotten software suites*).
3. **Direct PayPal Subscriptions API Actions:** Pauses subscriptions directly via standard PayPal REST API endpoints without permanently cancelling account history.
4. **Dual Autonomous / Human-in-the-Loop Modes:** Users can either review and approve 1-click recommendations or let the AI autonomously intervene to defend their overdraft buffer.
