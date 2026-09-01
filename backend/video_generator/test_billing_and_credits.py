import hashlib
import hmac
import json
import time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .billing import (
    PLANS,
    apply_plan_allowance,
    ensure_subscription,
    get_plan,
    handle_stripe_event,
    verify_stripe_signature,
)
from .credits import (
    get_or_create_credit_account,
    grant_free_allowance,
    refund_transaction,
    reserve_credits,
)
from .models import (
    BillingEvent,
    Character,
    CreditAccount,
    CreditTransaction,
    Subscription,
    VideoProject,
    VideoScene,
    Workspace,
    WorkspaceMembership,
)

User = get_user_model()


class BillingAndCreditsTests(TestCase):
    def setUp(self):
        self.client_a = APIClient()
        self.user_a = User.objects.create_user(username="alice", email="alice@test.com", password="Password123!")
        self.client_a.force_authenticate(user=self.user_a)

        self.client_b = APIClient()
        self.user_b = User.objects.create_user(username="bob", email="bob@test.com", password="Password123!")
        self.client_b.force_authenticate(user=self.user_b)

    def test_plan_specifications_and_capabilities(self):
        """Validates all tiers: Free, Creator, Studio, Enterprise against specifications."""
        free_plan = get_plan("free")
        self.assertEqual(free_plan.monthly_credits, 10)
        self.assertEqual(free_plan.max_duration, 10)
        self.assertEqual(free_plan.max_team_members, 1)
        self.assertEqual(free_plan.monthly_price_usd, Decimal("0"))

        creator_plan = get_plan("creator")
        self.assertEqual(creator_plan.monthly_credits, 150)
        self.assertEqual(creator_plan.max_duration, 30)
        self.assertEqual(creator_plan.max_team_members, 3)
        self.assertEqual(creator_plan.monthly_price_usd, Decimal("29.00"))

        studio_plan = get_plan("studio")
        self.assertEqual(studio_plan.monthly_credits, 600)
        self.assertEqual(studio_plan.max_duration, 60)
        self.assertEqual(studio_plan.max_team_members, 10)
        self.assertEqual(studio_plan.monthly_price_usd, Decimal("99.00"))
        self.assertTrue(studio_plan.priority_render)

        enterprise_plan = get_plan("enterprise")
        self.assertGreaterEqual(enterprise_plan.monthly_credits, 5000)
        self.assertEqual(enterprise_plan.max_duration, 60)
        self.assertGreaterEqual(enterprise_plan.max_team_members, 100)

    def test_plans_api_listing(self):
        """Plans API returns clean JSON list with all capabilities."""
        resp = self.client_a.get("/api/video/billing/plans/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        codes = [p["code"] for p in resp.data["plans"]]
        self.assertIn("free", codes)
        self.assertIn("creator", codes)
        self.assertIn("studio", codes)
        self.assertIn("enterprise", codes)

    def test_stripe_signature_verification(self):
        """Stripe webhook signature validation passes with valid signature and rejects forged ones."""
        secret = "whsec_test_secret_key"
        payload = b'{"id": "evt_test123", "type": "checkout.session.completed"}'
        timestamp = int(time.time())
        signed = f"{timestamp}.{payload.decode('utf-8')}".encode()
        sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        valid_header = f"t={timestamp},v1={sig}"

        # Valid signature should not raise
        verify_stripe_signature(payload, valid_header, secret)

        # Forged signature must raise ValueError
        invalid_header = f"t={timestamp},v1=wrong_hex_digest"
        with self.assertRaises(ValueError):
            verify_stripe_signature(payload, invalid_header, secret)

        # Expired timestamp must raise ValueError
        expired_header = f"t={timestamp - 600},v1={sig}"
        with self.assertRaises(ValueError):
            verify_stripe_signature(payload, expired_header, secret)

    def test_stripe_webhook_checkout_session_completed(self):
        """Processing checkout.session.completed activates subscription and grants plan allowance."""
        sub = ensure_subscription(self.user_a)
        self.assertEqual(sub.plan_code, "free")

        event = {
            "id": "evt_checkout_123",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "client_reference_id": str(self.user_a.id),
                    "customer": "cus_stripe_alice",
                    "subscription": "sub_stripe_alice",
                    "metadata": {
                        "user_id": str(self.user_a.id),
                        "plan_code": "creator",
                    }
                }
            }
        }
        handled = handle_stripe_event(event)
        self.assertTrue(handled)

        sub.refresh_from_db()
        self.assertEqual(sub.plan_code, "creator")
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        self.assertEqual(sub.provider_customer_id, "cus_stripe_alice")
        self.assertEqual(sub.provider_subscription_id, "sub_stripe_alice")

        account = get_or_create_credit_account(user=self.user_a)
        self.assertEqual(account.monthly_allowance, 150)
        self.assertGreaterEqual(account.balance, 150)

    def test_stripe_webhook_idempotency(self):
        """Sending identical webhook event twice does not double-grant credits."""
        account = get_or_create_credit_account(user=self.user_a)
        initial_balance = account.balance

        event = {
            "id": "evt_idempotent_999",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "client_reference_id": str(self.user_a.id),
                    "customer": "cus_stripe_alice",
                    "subscription": "sub_stripe_alice",
                    "metadata": {
                        "user_id": str(self.user_a.id),
                        "plan_code": "creator",
                    }
                }
            }
        }
        first_handled = handle_stripe_event(event)
        self.assertTrue(first_handled)

        account.refresh_from_db()
        balance_after_first = account.balance

        # Send exact same webhook again
        second_handled = handle_stripe_event(event)
        self.assertFalse(second_handled)  # Correctly detected as duplicate

        account.refresh_from_db()
        self.assertEqual(account.balance, balance_after_first)
        self.assertEqual(BillingEvent.objects.filter(event_id="evt_idempotent_999").count(), 1)

    def test_stripe_webhook_invoice_paid_auto_replenishment(self):
        """Invoice payment succeeded event auto-replenishes the monthly credit allowance."""
        sub = ensure_subscription(self.user_a)
        sub.plan_code = "studio"
        sub.provider = "stripe"
        sub.provider_subscription_id = "sub_studio_alice_001"
        sub.save()

        account = get_or_create_credit_account(user=self.user_a)
        account.balance = 50
        account.save()

        event = {
            "id": "evt_inv_paid_555",
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "subscription": "sub_studio_alice_001",
                }
            }
        }
        handle_stripe_event(event)

        account.refresh_from_db()
        self.assertEqual(account.balance, 50 + 600)
        self.assertEqual(account.monthly_allowance, 600)

    def test_stripe_webhook_subscription_lifecycle(self):
        """Subscription updated, past_due on invoice failure, and cancelled on deletion."""
        sub = ensure_subscription(self.user_a)
        sub.plan_code = "creator"
        sub.provider = "stripe"
        sub.provider_subscription_id = "sub_lifecycle_001"
        sub.status = Subscription.Status.ACTIVE
        sub.save()

        # Invoice payment fails -> PAST_DUE
        event_fail = {
            "id": "evt_inv_fail_001",
            "type": "invoice.payment_failed",
            "data": {"object": {"subscription": "sub_lifecycle_001"}}
        }
        handle_stripe_event(event_fail)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.PAST_DUE)

        # Subscription deleted -> CANCELLED, downgraded to FREE
        event_del = {
            "id": "evt_sub_del_001",
            "type": "customer.subscription.deleted",
            "data": {"object": {"id": "sub_lifecycle_001"}}
        }
        handle_stripe_event(event_del)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.CANCELLED)
        self.assertEqual(sub.plan_code, "free")

    def test_credit_reservation_and_refund_ledger(self):
        """Credits are atomically reserved on start and refunded on failure."""
        account = get_or_create_credit_account(user=self.user_a)
        account.balance = 100
        account.save()

        # Reserve 30 credits
        reserved = reserve_credits(self.user_a, 30, idempotency_key="res_test_1")
        self.assertEqual(reserved, 30)
        account.refresh_from_db()
        self.assertEqual(account.balance, 70)

        tx_reserve = CreditTransaction.objects.get(idempotency_key="res_test_1")
        self.assertEqual(tx_reserve.kind, CreditTransaction.Kind.RESERVE)
        self.assertEqual(tx_reserve.amount, 30)

        # Re-attempting same reservation is idempotent
        reserved_again = reserve_credits(self.user_a, 30, idempotency_key="res_test_1")
        self.assertEqual(reserved_again, 30)
        account.refresh_from_db()
        self.assertEqual(account.balance, 70)

        # Refund reservation
        refunded = refund_transaction(reservation_key="res_test_1", idempotency_key="ref_test_1")
        self.assertEqual(refunded, 30)
        account.refresh_from_db()
        self.assertEqual(account.balance, 100)

        tx_refund = CreditTransaction.objects.get(idempotency_key="ref_test_1")
        self.assertEqual(tx_refund.kind, CreditTransaction.Kind.REFUND)
        self.assertEqual(tx_refund.amount, 30)

        # Duplicate refund request is a no-op
        refunded_dup = refund_transaction(reservation_key="res_test_1", idempotency_key="ref_test_1")
        self.assertEqual(refunded_dup, 0)
        account.refresh_from_db()
        self.assertEqual(account.balance, 100)

    def test_workspace_credit_pool_shared_usage(self):
        """Workspace members draw credits from the workspace credit pool."""
        # Alice creates a team workspace and has 200 credits
        ws = Workspace.objects.create(name="Studio Pool WS", owner=self.user_a, is_personal=False)
        WorkspaceMembership.objects.create(workspace=ws, user=self.user_a, role=WorkspaceMembership.Role.OWNER)
        WorkspaceMembership.objects.create(workspace=ws, user=self.user_b, role=WorkspaceMembership.Role.EDITOR)

        alice_acc = get_or_create_credit_account(user=self.user_a)
        alice_acc.balance = 200
        alice_acc.save()

        bob_acc = get_or_create_credit_account(user=self.user_b)
        bob_acc.balance = 0
        bob_acc.save()

        # Project belongs to ws
        project = VideoProject.objects.create(
            user=self.user_b,
            workspace=ws,
            title="Shared Project",
            prompt="A futuristic racing drone navigating a metropolis.",
            duration=30,
            aspect_ratio="9:16",
        )
        scene = VideoScene.objects.create(project=project, scene_number=1, duration=30, prompt="Scene 1")
        char = Character.objects.create(project=project, name="Pilot Ace")

        # Bob (EDITOR with 0 personal credits) triggers credit reservation in workspace project
        reserved = reserve_credits(self.user_b, 30, idempotency_key="bob_gen_1", project=project)
        self.assertEqual(reserved, 30)

        # Alice's workspace credit pool was charged, Bob's remains 0
        alice_acc.refresh_from_db()
        bob_acc.refresh_from_db()
        self.assertEqual(alice_acc.balance, 170)
        self.assertEqual(bob_acc.balance, 0)

    def test_team_member_limit_enforcement(self):
        """Creator plan allows up to 3 members; 4th member invitation is rejected."""
        sub = ensure_subscription(self.user_a)
        sub.plan_code = "creator"  # max 3 team members
        sub.save()

        ws = Workspace.objects.create(name="Creator Workspace", owner=self.user_a, is_personal=False)
        WorkspaceMembership.objects.create(workspace=ws, user=self.user_a, role=WorkspaceMembership.Role.OWNER)

        # Add 2nd member (Bob) -> OK (count = 2)
        resp_bob = self.client_a.post(f"/api/video/workspaces/{ws.id}/members/", {
            "username_or_email": "bob",
            "role": "editor",
        }, format="json")
        self.assertEqual(resp_bob.status_code, status.HTTP_201_CREATED)

        # Create user 3 and 4
        user_c = User.objects.create_user(username="charlie", email="charlie@test.com", password="Password123!")
        user_d = User.objects.create_user(username="david", email="david@test.com", password="Password123!")

        # Add 3rd member (Charlie) -> OK (count = 3)
        resp_c = self.client_a.post(f"/api/video/workspaces/{ws.id}/members/", {
            "username_or_email": "charlie",
            "role": "editor",
        }, format="json")
        self.assertEqual(resp_c.status_code, status.HTTP_201_CREATED)

        # Add 4th member (David) -> Exceeds Creator plan max_team_members=3 -> 403 Forbidden
        resp_d = self.client_a.post(f"/api/video/workspaces/{ws.id}/members/", {
            "username_or_email": "david",
            "role": "editor",
        }, format="json")
        self.assertEqual(resp_d.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Upgrade your plan", resp_d.data["detail"])
