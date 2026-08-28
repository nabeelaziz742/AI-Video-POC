from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import CreditAccount, CreditTransaction, UsageEvent, VideoProject

FREE_MONTHLY_CREDITS = 100


def generation_cost(duration: int) -> int:
    return {10: 10, 30: 30, 60: 60}.get(int(duration), 0)


def get_or_create_credit_account(user):
    with transaction.atomic():
        account, created = CreditAccount.objects.select_for_update().get_or_create(user=user, defaults={"balance": FREE_MONTHLY_CREDITS, "monthly_allowance": FREE_MONTHLY_CREDITS})
        if created:
            CreditTransaction.objects.create(account=account, kind=CreditTransaction.Kind.GRANT, amount=FREE_MONTHLY_CREDITS, idempotency_key=f"signup-grant:{user.pk}", note="Initial free allowance")
        return account


def reserve_credits(user, amount: int, *, idempotency_key: str, project=None, note="Generation reserved") -> int:
    if amount <= 0:
        raise ValidationError("Credit amount must be positive.")
    with transaction.atomic():
        account = get_or_create_credit_account(user)
        account = CreditAccount.objects.select_for_update().get(pk=account.pk)
        existing = CreditTransaction.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing.amount
        if account.balance < amount:
            raise ValidationError({"detail": "Insufficient credits to start this generation.", "required": amount, "available": account.balance})
        account.balance -= amount
        account.save(update_fields=["balance", "updated_at"])
        CreditTransaction.objects.create(account=account, kind=CreditTransaction.Kind.RESERVE, amount=amount, project=project, idempotency_key=idempotency_key, note=note)
    return amount


def reserve_generation(user, project: VideoProject, *, idempotency_key: str) -> int:
    return reserve_credits(user, generation_cost(project.duration), idempotency_key=idempotency_key, project=project)


def record_usage(user, *, kind, credits, idempotency_key, project=None, scene=None, character=None):
    with transaction.atomic():
        existing = UsageEvent.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing
        return UsageEvent.objects.create(user=user, kind=kind, quantity=1, credits=credits, project=project, scene=scene, character=character, idempotency_key=idempotency_key)


def refund_transaction(project, *, idempotency_key: str) -> int:
    with transaction.atomic():
        reservation = CreditTransaction.objects.select_related("account").filter(project=project, kind=CreditTransaction.Kind.RESERVE).order_by("-created_at").first()
        if not reservation or CreditTransaction.objects.filter(idempotency_key=idempotency_key).exists():
            return 0
        account = CreditAccount.objects.select_for_update().get(pk=reservation.account_id)
        account.balance += reservation.amount
        account.save(update_fields=["balance", "updated_at"])
        CreditTransaction.objects.create(account=account, kind=CreditTransaction.Kind.REFUND, amount=reservation.amount, project=project, idempotency_key=idempotency_key, note="Generation failed before completion")
        return reservation.amount


def refund_generation(project: VideoProject, *, idempotency_key: str) -> int:
    return refund_transaction(project, idempotency_key=idempotency_key)
