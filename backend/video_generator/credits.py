from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import CreditAccount, CreditTransaction, VideoProject


def generation_cost(duration: int) -> int:
    return {10: 10, 30: 30, 60: 60}.get(int(duration), 0)


def reserve_generation(user, project: VideoProject, *, idempotency_key: str) -> int:
    cost = generation_cost(project.duration)
    if not cost:
        raise ValidationError("Unsupported generation duration.")
    with transaction.atomic():
        account, _ = CreditAccount.objects.select_for_update().get_or_create(user=user)
        existing = CreditTransaction.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing.amount
        if account.balance < cost:
            raise ValidationError({"detail": "Insufficient credits to start this generation.", "required": cost, "available": account.balance})
        account.balance -= cost
        account.save(update_fields=["balance", "updated_at"])
        CreditTransaction.objects.create(account=account, kind=CreditTransaction.Kind.RESERVE, amount=cost, project=project, idempotency_key=idempotency_key, note="Generation reserved")
    return cost


def refund_generation(project: VideoProject, *, idempotency_key: str) -> int:
    with transaction.atomic():
        reservation = CreditTransaction.objects.select_related("account").filter(project=project, kind=CreditTransaction.Kind.RESERVE).order_by("-created_at").first()
        if not reservation:
            return 0
        account = CreditAccount.objects.select_for_update().get(pk=reservation.account_id)
        if CreditTransaction.objects.filter(idempotency_key=idempotency_key).exists():
            return 0
        account.balance += reservation.amount
        account.save(update_fields=["balance", "updated_at"])
        CreditTransaction.objects.create(account=account, kind=CreditTransaction.Kind.REFUND, amount=reservation.amount, project=project, idempotency_key=idempotency_key, note="Generation failed before completion")
        return reservation.amount
