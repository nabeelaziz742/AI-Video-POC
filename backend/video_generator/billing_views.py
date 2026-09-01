import json
import os

from django.db import transaction
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .billing import PLANS, apply_plan_allowance, cancel_paid_subscription, create_checkout_session, ensure_subscription, handle_stripe_event, stripe_configured, verify_stripe_signature
from .models import CreditAccount, Subscription


class PlansView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        configured = stripe_configured()
        plans = [
            {
                "code": plan.code,
                "name": plan.name,
                "monthly_price_usd": str(plan.monthly_price_usd),
                "monthly_credits": plan.monthly_credits,
                "max_duration": plan.max_duration,
                "max_team_members": plan.max_team_members,
                "max_workspaces": plan.max_workspaces,
                "export_quality": plan.export_quality,
                "priority_render": plan.priority_render,
                "support_tier": plan.support_tier,
                "available": plan.code == "free" or configured,
            }
            for plan in PLANS.values()
            if plan.code != "pro"  # Hide legacy alias from primary plan listings
        ]
        return Response({"plans": plans})


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
        subscription = ensure_subscription(request.user)
        if code == "free":
            if subscription.plan_code == Subscription.Plan.FREE:
                return Response({"plan_code": "free", "status": subscription.status})
            if subscription.provider != "stripe" or not subscription.provider_subscription_id:
                return Response({"detail": "Paid subscription cannot be changed to free until its billing provider is cancelled."}, status=409)
            if not stripe_configured():
                return Response({"detail": "Billing is not configured. Configure Stripe before cancelling the paid subscription."}, status=503)
            try:
                cancel_paid_subscription(request.user)
            except Exception:
                return Response({"detail": "Unable to schedule the paid subscription cancellation."}, status=502)
            return Response({"plan_code": subscription.plan_code, "status": subscription.status, "cancel_at_period_end": True})
        if not stripe_configured():
            return Response({"detail": "Billing is not configured. Configure Stripe keys and price IDs before accepting paid subscriptions."}, status=503)
        try:
            url = create_checkout_session(request.user, code)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        except RuntimeError as exc:
            return Response({"detail": str(exc)}, status=503)
        except Exception:
            return Response({"detail": "Unable to create a secure checkout session."}, status=502)
        return Response({"checkout_url": url, "plan_code": code})


class BillingWebhookView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        signature = request.headers.get("Stripe-Signature", "")
        if not secret or not signature:
            return Response({"detail": "Webhook verification is not configured."}, status=503)
        try:
            verify_stripe_signature(request.body, signature, secret)
            event = json.loads(request.body.decode("utf-8"))
            handle_stripe_event(event)
        except (ValueError, json.JSONDecodeError):
            return Response({"detail": "Invalid billing webhook."}, status=400)
        except Exception:
            return Response({"detail": "Unable to process billing webhook."}, status=500)
        return Response({"received": True})
