from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from .models import CreditAccount


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
    return PLANS.get(code, PLANS["free"])


def apply_plan_allowance(user, plan_code: str):
    plan = get_plan(plan_code)
    with transaction.atomic():
        account, _ = CreditAccount.objects.select_for_update().get_or_create(user=user)
        account.monthly_allowance = plan.monthly_credits
        account.save(update_fields=["monthly_allowance", "updated_at"])
    return plan
