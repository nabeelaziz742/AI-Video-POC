from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing import PLANS, apply_plan_allowance
from .models import Subscription


class PlansView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"plans": [{"code": p.code, "name": p.name, "monthly_price_usd": str(p.monthly_price_usd), "monthly_credits": p.monthly_credits, "max_duration": p.max_duration} for p in PLANS.values()]})


class SubscriptionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        subscription, created = Subscription.objects.get_or_create(user=request.user)
        if created:
            apply_plan_allowance(request.user, "free")
        return Response({"plan_code": subscription.plan_code, "status": subscription.status, "provider": subscription.provider, "current_period_start": subscription.current_period_start, "current_period_end": subscription.current_period_end, "cancel_at_period_end": subscription.cancel_at_period_end})


class SubscriptionChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = str(request.data.get("plan_code", "")).lower()
        if code not in PLANS:
            return Response({"detail": "Unknown plan."}, status=400)
        if code != "free":
            return Response({"detail": "Payment provider checkout is not configured yet. No paid subscription has been created or charged."}, status=503)
        subscription, _ = Subscription.objects.get_or_create(user=request.user)
        subscription.plan_code = "free"
        subscription.status = Subscription.Status.ACTIVE
        subscription.cancel_at_period_end = False
        subscription.save(update_fields=["plan_code", "status", "cancel_at_period_end", "updated_at"])
        apply_plan_allowance(request.user, "free")
        return Response({"plan_code": "free", "status": "active"})


class BillingWebhookView(APIView):
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        return Response({"detail": "Billing webhook endpoint is reserved for a configured payment provider."}, status=503)
