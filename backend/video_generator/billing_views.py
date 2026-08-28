from django.db import transaction
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing import PLANS, apply_plan_allowance, ensure_subscription, get_plan
from .models import CreditAccount, Subscription


class PlansView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"plans": [{"code": p.code, "name": p.name, "monthly_price_usd": str(p.monthly_price_usd), "monthly_credits": p.monthly_credits, "max_duration": p.max_duration} for p in PLANS.values()]})


class SubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscription = ensure_subscription(request.user)
        if subscription.plan_code == Subscription.Plan.FREE and not CreditAccount.objects.filter(user=request.user).exists():
            apply_plan_allowance(request.user, "free", grant=True, idempotency_key=f"free-grant:{request.user.pk}")
        return Response({"plan_code": subscription.plan_code, "status": subscription.status, "provider": subscription.provider, "current_period_start": subscription.current_period_start, "current_period_end": subscription.current_period_end, "cancel_at_period_end": subscription.cancel_at_period_end})


class SubscriptionChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = str(request.data.get("plan_code", "")).lower().strip()
        if code not in PLANS:
            return Response({"detail": "Unknown plan."}, status=400)
        if code != "free":
            return Response({"detail": "Paid checkout is unavailable until a verified payment provider is configured. No payment or subscription has been created."}, status=503)
        with transaction.atomic():
            subscription = ensure_subscription(request.user)
            subscription.plan_code = Subscription.Plan.FREE
            subscription.status = Subscription.Status.ACTIVE
            subscription.provider = "manual"
            subscription.provider_customer_id = ""
            subscription.provider_subscription_id = ""
            subscription.current_period_start = None
            subscription.current_period_end = None
            subscription.cancel_at_period_end = False
            subscription.save()
            apply_plan_allowance(request.user, "free", grant=False)
        return Response({"plan_code": "free", "status": "active"})


class BillingWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        return Response({"detail": "Billing webhook is disabled until a verified provider signing secret is configured."}, status=503)
