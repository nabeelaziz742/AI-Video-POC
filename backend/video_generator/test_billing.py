from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient


class BillingApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="billing-user", password="pass12345")
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
        self.assertFalse(hasattr(self.user, "subscription"))
