import hashlib
import hmac
import time

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .billing import handle_stripe_event, verify_stripe_signature
from .models import BillingEvent, CreditAccount, CreditTransaction, Subscription


class BillingLifecycleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="billing-user", email="billing@example.com", password="pass12345")
        self.subscription = Subscription.objects.create(user=self.user)

    def test_stripe_signature_verification(self):
        payload = b'{"id":"evt_test","type":"invoice.paid"}'
        secret = "whsec_test"
        timestamp = str(int(time.time()))
        digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, hashlib.sha256).hexdigest()
        verify_stripe_signature(payload, f"t={timestamp},v1={digest}", secret)
        with self.assertRaises(ValueError):
            verify_stripe_signature(payload, f"t={timestamp},v1=bad", secret)

    def test_checkout_activates_subscription_and_is_idempotent(self):
        event = {"id": "evt_checkout_1", "type": "checkout.session.completed", "data": {"object": {"metadata": {"user_id": str(self.user.pk), "plan_code": "creator"}, "customer": "cus_1", "subscription": "sub_1"}}}
        self.assertTrue(handle_stripe_event(event))
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.plan_code, "creator")
        self.assertEqual(self.subscription.provider_subscription_id, "sub_1")
        self.assertFalse(handle_stripe_event(event))
        self.assertEqual(BillingEvent.objects.count(), 1)

    def test_invoice_paid_grants_monthly_credits_once(self):
        self.subscription.plan_code = "creator"
        self.subscription.provider_subscription_id = "sub_2"
        self.subscription.provider = "stripe"
        self.subscription.save()
        event = {"id": "evt_invoice_1", "type": "invoice.paid", "data": {"object": {"subscription": "sub_2"}}}
        self.assertTrue(handle_stripe_event(event))
        self.assertFalse(handle_stripe_event(event))
        account = CreditAccount.objects.get(user=self.user)
        self.assertEqual(account.balance, 500)
        self.assertEqual(CreditTransaction.objects.filter(kind=CreditTransaction.Kind.GRANT).count(), 1)

    def test_payment_failed_marks_past_due(self):
        self.subscription.provider_subscription_id = "sub_3"
        self.subscription.provider = "stripe"
        self.subscription.save()
        event = {"id": "evt_failed_1", "type": "invoice.payment_failed", "data": {"object": {"subscription": "sub_3"}}}
        handle_stripe_event(event)
        self.subscription.refresh_from_db()
        self.assertEqual(self.subscription.status, Subscription.Status.PAST_DUE)


class BillingApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="api-billing", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_plans_are_exposed(self):
        response = self.client.get("/api/video/billing/plans/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({p["code"] for p in response.data["plans"]}, {"free", "creator", "pro"})

    def test_subscription_defaults_to_free(self):
        response = self.client.get("/api/video/billing/subscription/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["plan_code"], "free")
        self.assertEqual(response.data["status"], "active")

    def test_paid_change_is_safe_without_payment_provider(self):
        response = self.client.post("/api/video/billing/subscription/change/", {"plan_code": "pro"}, format="json")
        self.assertEqual(response.status_code, 503)
        self.assertFalse(Subscription.objects.filter(user=self.user, plan_code="pro").exists())
