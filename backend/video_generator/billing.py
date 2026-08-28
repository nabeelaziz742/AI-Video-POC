from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from .models import CreditAccount, CreditTransaction, Subscription


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
