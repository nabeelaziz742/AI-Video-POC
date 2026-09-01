from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import CreditAccount, CreditTransaction, UsageEvent, VideoProject, Workspace

FREE_MONTHLY_CREDITS = 10


def generation_cost(duration: int) -> int:
    """Charge one credit per generated video second; project totals remain 10/30/60 credits."""
    duration = int(duration)
    if duration < 1 or duration > 60:
        return 0
    return duration


def get_or_create_credit_account(user=None, workspace=None):
    """
    Returns the designated CreditAccount for a user or workspace, atomically locking it if inside a transaction.
    """
    with transaction.atomic():
        if workspace:
            # If workspace has its own direct credit_pool, use it
            pool = getattr(workspace, "credit_pool", None)
            if pool:
                return CreditAccount.objects.select_for_update().get(pk=pool.pk)
            # Otherwise use workspace owner's credit account
            if workspace.owner:
                return get_or_create_credit_account(user=workspace.owner)
        if user:
            account, _ = CreditAccount.objects.select_for_update().get_or_create(
                user=user,
                defaults={"balance": 0, "monthly_allowance": FREE_MONTHLY_CREDITS}
            )
            return account
        raise ValueError("Either user or workspace must be specified.")


def resolve_credit_account(user, project=None, workspace=None):
    """
    Resolves the authoritative credit account to charge:
    - If project is associated with a workspace: charges the workspace credit pool / owner.
    - If workspace is explicitly passed: charges the workspace credit pool / owner.
    - Otherwise: charges the authenticated user's account.
    """
    if project and getattr(project, "workspace", None):
        return get_or_create_credit_account(workspace=project.workspace)
    if workspace:
        return get_or_create_credit_account(workspace=workspace)
    return get_or_create_credit_account(user=user)


def grant_free_allowance(user) -> int:
    with transaction.atomic():
        account = get_or_create_credit_account(user=user)
        account = CreditAccount.objects.select_for_update().get(pk=account.pk)
        idempotency_key = f"signup-grant:{user.pk}"
        if CreditTransaction.objects.filter(idempotency_key=idempotency_key).exists():
            return account.balance
        account.balance += FREE_MONTHLY_CREDITS
        account.monthly_allowance = FREE_MONTHLY_CREDITS
        account.save(update_fields=["balance", "monthly_allowance", "updated_at"])
        CreditTransaction.objects.create(
            account=account,
            kind=CreditTransaction.Kind.GRANT,
            amount=FREE_MONTHLY_CREDITS,
            idempotency_key=idempotency_key,
            note="Free plan verification grant"
        )
        return account.balance


def reserve_credits(user, amount: int, *, idempotency_key: str, project=None, workspace=None, note="Generation reserved") -> int:
    if amount <= 0:
        raise ValidationError("Credit amount must be positive.")
    with transaction.atomic():
        account = resolve_credit_account(user, project=project, workspace=workspace)
        account = CreditAccount.objects.select_for_update().get(pk=account.pk)
        existing = CreditTransaction.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing.amount
        if account.balance < amount:
            raise ValidationError({"detail": "Insufficient credits to start this generation.", "required": amount, "available": account.balance})
        account.balance -= amount
        account.save(update_fields=["balance", "updated_at"])
        CreditTransaction.objects.create(
            account=account,
            kind=CreditTransaction.Kind.RESERVE,
            amount=amount,
            project=project,
            idempotency_key=idempotency_key,
            note=note
        )
    return amount


def reserve_generation(user, project: VideoProject, *, idempotency_key: str) -> int:
    return reserve_credits(user, generation_cost(project.duration), idempotency_key=idempotency_key, project=project)


def record_usage(user, *, kind, credits, idempotency_key, project=None, scene=None, character=None):
    with transaction.atomic():
        existing = UsageEvent.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing
        return UsageEvent.objects.create(
            user=user,
            kind=kind,
            quantity=1,
            credits=credits,
            project=project,
            scene=scene,
            character=character,
            idempotency_key=idempotency_key
        )


def refund_transaction(*, reservation_key: str, idempotency_key: str) -> int:
    with transaction.atomic():
        reservation = CreditTransaction.objects.select_related("account").filter(
            idempotency_key=reservation_key,
            kind=CreditTransaction.Kind.RESERVE
        ).first()
        if not reservation or CreditTransaction.objects.filter(idempotency_key=idempotency_key).exists():
            return 0
        account = CreditAccount.objects.select_for_update().get(pk=reservation.account_id)
        account.balance += reservation.amount
        account.save(update_fields=["balance", "updated_at"])
        CreditTransaction.objects.create(
            account=account,
            kind=CreditTransaction.Kind.REFUND,
            amount=reservation.amount,
            project=reservation.project,
            idempotency_key=idempotency_key,
            note="Generation failed before completion"
        )
        return reservation.amount


CHARACTER_REFERENCE_COST = 5
ASSEMBLY_COST = 5


def reserve_job_credits(job) -> int:
    """
    Atomically reserves credits for a VideoJob based on its type and target:
    - Full generation: charges generation_cost(project.duration)
    - Scene regeneration: charges generation_cost(target_scene.duration)
    - Assembly: charges ASSEMBLY_COST
    """
    if job.credits_reserved > 0 and job.reservation_key:
        return job.credits_reserved

    if job.job_type == "scene_regeneration" and job.target_scene:
        cost = generation_cost(job.target_scene.duration)
    elif job.job_type == "assembly":
        cost = ASSEMBLY_COST
    else:
        cost = generation_cost(job.project.duration)

    if cost <= 0:
        cost = 10

    reservation_key = f"video-job:{job.id}:{job.retry_count}"
    reserve_credits(
        user=job.user,
        amount=cost,
        idempotency_key=reservation_key,
        project=job.project,
        workspace=job.workspace,
        note=f"Video Job #{job.id} ({job.job_type})"
    )
    job.reservation_key = reservation_key
    job.credits_reserved = cost
    job.save(update_fields=["reservation_key", "credits_reserved", "updated_at"])
    return cost


def consume_job_credits(job) -> int:
    """
    Marks the reserved credits for a VideoJob as consumed and writes an immutable UsageEvent.
    """
    if not job.reservation_key or job.credits_reserved <= 0:
        return 0

    kind = UsageEvent.Kind.SCENE if job.job_type == "scene_regeneration" else UsageEvent.Kind.PROJECT
    record_usage(
        user=job.user,
        kind=kind,
        credits=job.credits_reserved,
        idempotency_key=f"usage:{job.reservation_key}",
        project=job.project,
        scene=job.target_scene,
    )
    job.credits_consumed = job.credits_reserved
    job.save(update_fields=["credits_consumed", "updated_at"])
    return job.credits_consumed


def refund_job_credits(job) -> int:
    """
    Releases/refunds reserved credits if a job terminates abnormally (failed or cancelled).
    """
    if not job.reservation_key or job.credits_reserved <= 0:
        return 0
    return refund_transaction(
        reservation_key=job.reservation_key,
        idempotency_key=f"refund:{job.reservation_key}",
    )

