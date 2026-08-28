import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from decimal import Decimal

import requests
from django.db import transaction
from django.utils import timezone

from .models import BillingEvent, CreditAccount, CreditTransaction, Subscription


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    monthly_price_usd: Decimal
    monthly_credits: int
    max_duration: int


PLANS = {
    "free": Plan("free", "Free", Decimal("0"), 100, 10),
    "creator": Plan("creator", "Creator", Decimal("9.99"), 500, 30),
    "pro": Plan("pro", "Pro", Decimal("24.99"), 1500, 60),
}


def get_plan(code: str) -> Plan:
    if code not in PLANS:
        raise ValueError("Unknown plan.")
    return PLANS[code]


def stripe_configured() -> bool:
    return bool(os.getenv("STRIPE_SECRET_KEY") and os.getenv("STRIPE_WEBHOOK_SECRET"))


def stripe_price_id(plan_code: str) -> str:
    value = os.getenv(f"STRIPE_PRICE_{plan_code.upper()}", "").strip()
    if not value:
        raise RuntimeError(f"Stripe price is not configured for the {plan_code} plan.")
    return value


def ensure_subscription(user) -> Subscription:
    subscription, _ = Subscription.objects.get_or_create(user=user)
    return subscription


def apply_plan_allowance(user, plan_code: str, *, grant: bool = False, idempotency_key: str | None = None):
    plan = get_plan(plan_code)
    with transaction.atomic():
        account, _ = CreditAccount.objects.select_for_update().get_or_create(user=user)
        account.monthly_allowance = plan.monthly_credits
        if grant:
            key = idempotency_key or f"allowance:{user.pk}:{plan_code}"
            if not CreditTransaction.objects.filter(idempotency_key=key).exists():
                account.balance += plan.monthly_credits
                CreditTransaction.objects.create(account=account, kind=CreditTransaction.Kind.GRANT, amount=plan.monthly_credits, idempotency_key=key, note=f"{plan.name} monthly allowance")
        account.save(update_fields=["monthly_allowance", "balance", "updated_at"])
    return plan


def create_checkout_session(user, plan_code: str) -> str:
    if plan_code == "free":
        raise ValueError("The free plan does not require checkout.")
    if not stripe_configured():
        raise RuntimeError("Stripe is not configured. Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET.")
    price_id = stripe_price_id(plan_code)
    subscription = ensure_subscription(user)
    customer = subscription.provider_customer_id
    headers = {"Authorization": f"Bearer {os.environ['STRIPE_SECRET_KEY']}", "Idempotency-Key": f"checkout:{user.pk}:{plan_code}:{int(time.time() // 300)}"}
    data = {"mode": "subscription", "line_items[0][price]": price_id, "line_items[0][quantity]": "1", "success_url": os.getenv("STRIPE_SUCCESS_URL", "http://localhost:3000/dashboard?billing=success"), "cancel_url": os.getenv("STRIPE_CANCEL_URL", "http://localhost:3000/dashboard?billing=cancelled"), "client_reference_id": str(user.pk), "metadata[user_id]": str(user.pk), "metadata[plan_code]": plan_code, "subscription_data[metadata[user_id]]": str(user.pk), "subscription_data[metadata[plan_code]]": plan_code}
    if customer:
        data["customer"] = customer
    else:
        data["customer_email"] = user.email
    response = requests.post("https://api.stripe.com/v1/checkout/sessions", headers=headers, data=data, timeout=15)
    response.raise_for_status()
    return response.json()["url"]


def verify_stripe_signature(payload: bytes, signature: str, secret: str) -> None:
    timestamp = None
    signatures = []
    for part in signature.split(","):
        key, _, value = part.partition("=")
        if key == "t": timestamp = value
        elif key == "v1": signatures.append(value)
    if not timestamp or not signatures:
        raise ValueError("Invalid Stripe signature.")
    try:
        timestamp_int = int(timestamp)
    except ValueError as exc:
        raise ValueError("Invalid Stripe signature timestamp.") from exc
    if abs(time.time() - timestamp_int) > 300:
        raise ValueError("Invalid or expired Stripe signature.")
    signed = f"{timestamp}.{payload.decode('utf-8')}".encode()
    expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise ValueError("Invalid Stripe signature.")


def _unix_datetime(value):
    return timezone.datetime.fromtimestamp(int(value), tz=timezone.utc) if value else None


def handle_stripe_event(event: dict):
    event_id = event.get("id")
    event_type = event.get("type", "")
    payload = event.get("data", {}).get("object", {})
    if not event_id:
        raise ValueError("Stripe event ID is required.")
    raw = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
    payload_hash = hashlib.sha256(raw).hexdigest()
    with transaction.atomic():
        existing = BillingEvent.objects.filter(event_id=event_id).first()
        if existing:
            return False
        BillingEvent.objects.create(event_id=event_id, event_type=event_type, payload_hash=payload_hash)
        if event_type == "checkout.session.completed":
            user_id = payload.get("metadata", {}).get("user_id") or payload.get("client_reference_id")
            plan_code = payload.get("metadata", {}).get("plan_code")
            if user_id and plan_code in PLANS:
                subscription = Subscription.objects.select_for_update().get(user_id=int(user_id))
                subscription.plan_code = plan_code
                subscription.status = Subscription.Status.ACTIVE
                subscription.provider = "stripe"
                subscription.provider_customer_id = payload.get("customer") or subscription.provider_customer_id
                subscription.provider_subscription_id = payload.get("subscription") or subscription.provider_subscription_id
                subscription.save()
                apply_plan_allowance(subscription.user, plan_code, grant=True, idempotency_key=f"stripe:checkout:{event_id}")
        elif event_type in {"invoice.paid", "invoice.payment_succeeded"}:
            subscription_id = payload.get("subscription")
            subscription = Subscription.objects.select_for_update().filter(provider_subscription_id=subscription_id).first()
            if subscription:
                subscription.status = Subscription.Status.ACTIVE
                subscription.save(update_fields=["status", "updated_at"])
                apply_plan_allowance(subscription.user, subscription.plan_code, grant=True, idempotency_key=f"stripe:invoice:{event_id}")
        elif event_type == "invoice.payment_failed":
            subscription_id = payload.get("subscription")
            subscription = Subscription.objects.select_for_update().filter(provider_subscription_id=subscription_id).first()
            if subscription:
                subscription.status = Subscription.Status.PAST_DUE
                subscription.save(update_fields=["status", "updated_at"])
        elif event_type in {"customer.subscription.updated", "customer.subscription.deleted"}:
            subscription_id = payload.get("id")
            subscription = Subscription.objects.select_for_update().filter(provider_subscription_id=subscription_id).first()
            if subscription:
                status_map = {"active": Subscription.Status.ACTIVE, "trialing": Subscription.Status.TRIALING, "past_due": Subscription.Status.PAST_DUE, "canceled": Subscription.Status.CANCELLED, "unpaid": Subscription.Status.PAST_DUE}
                subscription.status = status_map.get(payload.get("status"), Subscription.Status.CANCELLED if event_type.endswith("deleted") else subscription.status)
                subscription.cancel_at_period_end = bool(payload.get("cancel_at_period_end", subscription.cancel_at_period_end))
                subscription.current_period_start = _unix_datetime(payload.get("current_period_start"))
                subscription.current_period_end = _unix_datetime(payload.get("current_period_end"))
                subscription.save()
        return True
