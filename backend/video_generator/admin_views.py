import os
import uuid
from django.conf import settings
from django.contrib.auth.models import User
from django.db import connection, transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing import PLANS, stripe_configured
from .credits import get_or_create_credit_account
from .models import (
    Character,
    CreditAccount,
    CreditTransaction,
    Subscription,
    UsageEvent,
    VideoProject,
    VideoScene,
)
from .security import mask_secret


class IsAdminUser(BasePermission):
    """Allows access only to authenticated staff users."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)


class AdminStatsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        total_users = User.objects.count()
        staff_users = User.objects.filter(is_staff=True).count()
        total_projects = VideoProject.objects.count()

        project_status_counts = dict(
            VideoProject.objects.values("status").annotate(count=Count("id")).values_list("status", "count")
        )
        total_scenes = VideoScene.objects.count()
        scene_status_counts = dict(
            VideoScene.objects.values("status").annotate(count=Count("id")).values_list("status", "count")
        )

        total_credits_balance = CreditAccount.objects.aggregate(total=Sum("balance"))["total"] or 0
        total_credits_consumed = UsageEvent.objects.aggregate(total=Sum("credits"))["total"] or 0
        total_credits_granted = CreditTransaction.objects.filter(
            kind__in=[CreditTransaction.Kind.GRANT, CreditTransaction.Kind.ADJUSTMENT]
        ).aggregate(total=Sum("amount"))["total"] or 0

        active_subscriptions = Subscription.objects.filter(
            status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING]
        ).count()
        subscriptions_by_plan = dict(
            Subscription.objects.values("plan_code").annotate(count=Count("id")).values_list("plan_code", "count")
        )

        usage_by_kind = dict(
            UsageEvent.objects.values("kind").annotate(total=Sum("quantity")).values_list("kind", "total")
        )

        return Response({
            "users": {
                "total": total_users,
                "staff": staff_users,
            },
            "subscriptions": {
                "active_total": active_subscriptions,
                "by_plan": {code: subscriptions_by_plan.get(code, 0) for code in PLANS.keys()},
            },
            "projects": {
                "total": total_projects,
                "completed": project_status_counts.get(VideoProject.Status.COMPLETED, 0),
                "processing": project_status_counts.get(VideoProject.Status.PROCESSING, 0),
                "queued": project_status_counts.get(VideoProject.Status.QUEUED, 0),
                "failed": project_status_counts.get(VideoProject.Status.FAILED, 0),
                "draft": project_status_counts.get(VideoProject.Status.DRAFT, 0),
            },
            "scenes": {
                "total": total_scenes,
                "completed": scene_status_counts.get(VideoScene.Status.COMPLETED, 0),
                "processing": scene_status_counts.get(VideoScene.Status.PROCESSING, 0),
                "failed": scene_status_counts.get(VideoScene.Status.FAILED, 0),
                "planned": scene_status_counts.get(VideoScene.Status.PLANNED, 0),
            },
            "credits": {
                "total_circulating_balance": total_credits_balance,
                "total_granted": total_credits_granted,
                "total_consumed": total_credits_consumed,
            },
            "usage": {
                "projects": usage_by_kind.get(UsageEvent.Kind.PROJECT, 0),
                "scenes": usage_by_kind.get(UsageEvent.Kind.SCENE, 0),
                "character_references": usage_by_kind.get(UsageEvent.Kind.CHARACTER_REFERENCE, 0),
                "assemblies": usage_by_kind.get(UsageEvent.Kind.ASSEMBLY, 0),
            },
        })


class AdminUsersView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        query = str(request.query_params.get("q", "")).strip()
        users_qs = User.objects.all().select_related("credit_account", "subscription").order_by("-date_joined")
        if query:
            users_qs = users_qs.filter(Q(username__icontains=query) | Q(email__icontains=query))

        limit = min(int(request.query_params.get("limit", 100)), 200)
        users_page = users_qs[:limit]

        user_project_counts = dict(
            VideoProject.objects.values("user_id").annotate(count=Count("id")).values_list("user_id", "count")
        )

        data = []
        for u in users_page:
            account = getattr(u, "credit_account", None)
            sub = getattr(u, "subscription", None)
            data.append({
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "is_staff": u.is_staff,
                "is_active": u.is_active,
                "date_joined": u.date_joined,
                "credits_balance": account.balance if account else 0,
                "monthly_allowance": account.monthly_allowance if account else 0,
                "plan_code": sub.plan_code if sub else "free",
                "subscription_status": sub.status if sub else "active",
                "total_projects": user_project_counts.get(u.id, 0),
            })
        return Response({"users": data, "count": len(data)})


class AdminUserCreditsView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request, user_id):
        target_user = get_object_or_404(User, id=user_id)
        try:
            amount = int(request.data.get("amount", 0))
        except (TypeError, ValueError):
            return Response({"detail": "Amount must be a valid integer."}, status=status.HTTP_400_BAD_REQUEST)

        if amount == 0:
            return Response({"detail": "Amount must be non-zero."}, status=status.HTTP_400_BAD_REQUEST)

        note = str(request.data.get("note", "Admin credit adjustment")).strip() or "Admin credit adjustment"
        idempotency_key = str(request.data.get("idempotency_key", "")).strip() or f"admin-adj:{user_id}:{uuid.uuid4()}"

        with transaction.atomic():
            account = get_or_create_credit_account(target_user)
            if CreditTransaction.objects.filter(idempotency_key=idempotency_key).exists():
                return Response({
                    "user_id": target_user.id,
                    "balance": account.balance,
                    "idempotency_key": idempotency_key,
                    "replayed": True,
                })

            if amount < 0 and account.balance < abs(amount):
                return Response(
                    {"detail": f"Cannot deduct {abs(amount)} credits; user only has {account.balance}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            account.balance += amount
            account.save(update_fields=["balance", "updated_at"])

            kind = CreditTransaction.Kind.ADJUSTMENT if amount < 0 else CreditTransaction.Kind.GRANT
            CreditTransaction.objects.create(
                account=account,
                kind=kind,
                amount=abs(amount),
                idempotency_key=idempotency_key,
                note=f"{note} (by {request.user.username})",
            )

        return Response({
            "user_id": target_user.id,
            "balance": account.balance,
            "adjusted_by": amount,
            "idempotency_key": idempotency_key,
            "replayed": False,
        })


class AdminProjectsView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        status_filter = request.query_params.get("status")
        projects_qs = VideoProject.objects.all().select_related("user").prefetch_related("scenes").order_by("-created_at")
        if status_filter and status_filter in VideoProject.Status.values:
            projects_qs = projects_qs.filter(status=status_filter)

        limit = min(int(request.query_params.get("limit", 50)), 100)
        projects = projects_qs[:limit]

        data = []
        for p in projects:
            data.append({
                "id": p.id,
                "title": p.title,
                "user": {
                    "id": p.user_id,
                    "username": p.user.username if p.user else "Anonymous",
                    "email": p.user.email if p.user else "",
                },
                "version_number": p.version_number,
                "status": p.status,
                "input_type": p.input_type,
                "duration": p.duration,
                "aspect_ratio": p.aspect_ratio,
                "provider": p.provider,
                "scene_count": p.scenes.count(),
                "video_url": p.video_url,
                "error_message": p.error_message,
                "generation_attempt": p.generation_attempt,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            })
        return Response({"projects": data, "count": len(data)})


class AdminSystemHealthView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        db_ok = False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            db_ok = True
        except Exception:
            db_ok = False

        storage_root = getattr(settings, "MEDIA_ROOT", None)
        storage_writable = False
        if storage_root:
            try:
                os.makedirs(storage_root, exist_ok=True)
                test_file = os.path.join(storage_root, ".write_test")
                with open(test_file, "w") as f:
                    f.write("ok")
                if os.path.exists(test_file):
                    os.remove(test_file)
                storage_writable = True
            except Exception:
                storage_writable = False

        fal_key = os.getenv("FAL_KEY")
        json2video_key = os.getenv("JSON2VIDEO_API_KEY")
        stripe_key = os.getenv("STRIPE_SECRET_KEY")
        stripe_webhook = os.getenv("STRIPE_WEBHOOK_SECRET")

        return Response({
            "status": "healthy" if db_ok else "degraded",
            "database": {
                "connected": db_ok,
                "engine": settings.DATABASES["default"]["ENGINE"].split(".")[-1],
            },
            "storage": {
                "media_root_configured": bool(storage_root),
                "media_root_writable": storage_writable,
                "static_root_configured": bool(getattr(settings, "STATIC_ROOT", None)),
            },
            "providers": {
                "fal_pixverse": {
                    "configured": bool(fal_key),
                    "key_preview": mask_secret(fal_key),
                    "image_model": os.getenv("FAL_IMAGE_MODEL", "fal-ai/flux/schnell"),
                    "resolution": os.getenv("FAL_VIDEO_RESOLUTION", "720p"),
                },
                "json2video": {
                    "configured": bool(json2video_key),
                    "key_preview": mask_secret(json2video_key),
                },
                "stripe": {
                    "configured": stripe_configured(),
                    "secret_key_preview": mask_secret(stripe_key),
                    "webhook_configured": bool(stripe_webhook),
                    "webhook_preview": mask_secret(stripe_webhook),
                },
            },
            "environment": {
                "debug": settings.DEBUG,
                "allowed_hosts": settings.ALLOWED_HOSTS,
                "cors_origins": getattr(settings, "CORS_ALLOWED_ORIGINS", []),
            },
        })
