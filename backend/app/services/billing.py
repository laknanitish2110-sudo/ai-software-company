"""
Billing service — Stripe integration for ARIA.

Plans:
- free: 5 pipeline runs/month, 50 employee messages/month
- pro ($29/mo): 50 pipeline runs/month, unlimited employee messages
- team ($79/mo): unlimited everything, priority models

When STRIPE_SECRET_KEY is not set, all users get free plan with limits enforced locally.
"""

import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PLANS = {
    "free": {
        "name": "Free",
        "price_monthly": 0,
        "pipeline_runs": 5,
        "employee_messages": 50,
        "employees": 6,
        "features": ["6 AI employees", "5 pipeline runs/mo", "50 messages/mo"],
    },
    "pro": {
        "name": "Pro",
        "price_monthly": 29,
        "pipeline_runs": 50,
        "employee_messages": -1,  # unlimited
        "employees": 6,
        "features": ["Unlimited messages", "50 pipeline runs/mo", "Priority support"],
    },
    "team": {
        "name": "Team",
        "price_monthly": 79,
        "pipeline_runs": -1,  # unlimited
        "employee_messages": -1,
        "employees": -1,
        "features": ["Unlimited everything", "Priority models", "Custom employees"],
    },
}


def get_stripe():
    from app.core.config import STRIPE_SECRET_KEY
    if not STRIPE_SECRET_KEY:
        return None
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
    return stripe


async def get_or_create_subscription(user_id: str) -> dict:
    from app.core.database import get_subscription, upsert_subscription
    sub = await get_subscription(user_id)
    if not sub:
        sub = await upsert_subscription(user_id, plan="free")
    return sub


async def get_plan_limits(user_id: str) -> dict:
    sub = await get_or_create_subscription(user_id)
    plan_key = sub.get("plan", "free")
    plan = PLANS.get(plan_key, PLANS["free"])
    return {
        "plan": plan_key,
        "plan_name": plan["name"],
        "limits": {
            "pipeline_runs": plan["pipeline_runs"],
            "employee_messages": plan["employee_messages"],
            "employees": plan["employees"],
        },
        "status": sub.get("status", "active"),
        "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
        "current_period_end": sub.get("current_period_end"),
    }


async def check_usage_limit(user_id: str, action: str) -> tuple[bool, str]:
    """Check if user is within their plan limits. Returns (allowed, reason)."""
    from app.core.database import get_usage_summary
    sub = await get_or_create_subscription(user_id)
    plan = PLANS.get(sub.get("plan", "free"), PLANS["free"])
    usage = await get_usage_summary(user_id, days=30)

    if action == "pipeline_run":
        limit = plan["pipeline_runs"]
        if limit == -1:
            return True, ""
        count = sum(r["count"] for r in usage["by_type"] if r["record_type"] == "pipeline_run")
        if count >= limit:
            return False, f"You've used {count}/{limit} pipeline runs this month. Upgrade to Pro for more."
        return True, ""

    if action == "employee_message":
        limit = plan["employee_messages"]
        if limit == -1:
            return True, ""
        count = sum(r["count"] for r in usage["by_type"] if r["record_type"] == "employee_message")
        if count >= limit:
            return False, f"You've used {count}/{limit} employee messages this month. Upgrade to Pro for unlimited."
        return True, ""

    return True, ""


async def create_checkout_session(user_id: str, user_email: str, plan: str) -> dict | None:
    """Create a Stripe Checkout session for upgrading."""
    stripe = get_stripe()
    if not stripe:
        return None

    from app.core.config import STRIPE_SECRET_KEY, OAUTH_FRONTEND_URL
    from app.core.database import get_subscription

    sub = await get_subscription(user_id)
    customer_id = sub.get("stripe_customer_id") if sub else None

    if not customer_id:
        customer = stripe.Customer.create(email=user_email, metadata={"user_id": user_id})
        customer_id = customer.id
        from app.core.database import upsert_subscription
        await upsert_subscription(user_id, plan="free", stripe_customer_id=customer_id)

    price_lookup = os.getenv(f"STRIPE_PRICE_{plan.upper()}", "")
    if not price_lookup:
        return None

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_lookup, "quantity": 1}],
        success_url=f"{OAUTH_FRONTEND_URL}/settings?billing=success",
        cancel_url=f"{OAUTH_FRONTEND_URL}/settings?billing=cancelled",
        metadata={"user_id": user_id, "plan": plan},
    )
    return {"url": session.url, "session_id": session.id}


async def create_portal_session(user_id: str) -> dict | None:
    """Create a Stripe Customer Portal session for managing subscription."""
    stripe = get_stripe()
    if not stripe:
        return None

    from app.core.database import get_subscription
    from app.core.config import OAUTH_FRONTEND_URL

    sub = await get_subscription(user_id)
    if not sub or not sub.get("stripe_customer_id"):
        return None

    session = stripe.billing_portal.Session.create(
        customer=sub["stripe_customer_id"],
        return_url=f"{OAUTH_FRONTEND_URL}/settings",
    )
    return {"url": session.url}


async def handle_webhook_event(event: dict):
    """Process Stripe webhook events."""
    event_type = event.get("type", "")
    data = event.get("data", {}).get("object", {})

    if event_type in ("customer.subscription.created", "customer.subscription.updated"):
        customer_id = data.get("customer")
        from app.core.database import get_subscription_by_stripe_customer, upsert_subscription

        sub = await get_subscription_by_stripe_customer(customer_id)
        if not sub:
            logger.warning(f"No subscription found for Stripe customer {customer_id}")
            return

        price_id = ""
        items = data.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id", "")

        plan = _price_to_plan(price_id)
        status = data.get("status", "active")
        period_start = data.get("current_period_start")
        period_end = data.get("current_period_end")
        cancel = data.get("cancel_at_period_end", False)

        if period_start:
            period_start = datetime.fromtimestamp(period_start, tz=timezone.utc).isoformat()
        if period_end:
            period_end = datetime.fromtimestamp(period_end, tz=timezone.utc).isoformat()

        await upsert_subscription(
            user_id=sub["user_id"],
            plan=plan,
            stripe_customer_id=customer_id,
            stripe_subscription_id=data.get("id"),
            status=status,
            current_period_start=period_start,
            current_period_end=period_end,
            cancel_at_period_end=cancel,
        )
        logger.info(f"Subscription updated: user={sub['user_id']} plan={plan} status={status}")

    elif event_type == "customer.subscription.deleted":
        customer_id = data.get("customer")
        from app.core.database import get_subscription_by_stripe_customer, upsert_subscription

        sub = await get_subscription_by_stripe_customer(customer_id)
        if sub:
            await upsert_subscription(
                user_id=sub["user_id"],
                plan="free",
                stripe_customer_id=customer_id,
                status="cancelled",
            )
            logger.info(f"Subscription cancelled: user={sub['user_id']}")

    elif event_type == "checkout.session.completed":
        metadata = data.get("metadata", {})
        user_id = metadata.get("user_id")
        plan = metadata.get("plan")
        if user_id and plan:
            customer_id = data.get("customer")
            subscription_id = data.get("subscription")
            from app.core.database import upsert_subscription
            await upsert_subscription(
                user_id=user_id,
                plan=plan,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                status="active",
            )
            logger.info(f"Checkout completed: user={user_id} plan={plan}")


def _price_to_plan(price_id: str) -> str:
    pro_price = os.getenv("STRIPE_PRICE_PRO", "")
    team_price = os.getenv("STRIPE_PRICE_TEAM", "")
    if price_id == pro_price:
        return "pro"
    if price_id == team_price:
        return "team"
    return "pro"
