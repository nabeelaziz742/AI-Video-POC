from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from django.core.cache import cache
from .credits import get_or_create_credit_account, grant_free_allowance
from .models import CreditTransaction, UsageEvent, VideoProject


class UsageApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(username="usage-user", password="pass12345")
        grant_free_allowance(self.user)
        self.client.force_authenticate(self.user)

    def test_credit_balance_bootstraps_without_charging(self):
        response = self.client.get("/api/video/credits/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["balance"], 10)
        self.assertEqual(CreditTransaction.objects.filter(kind=CreditTransaction.Kind.RESERVE).count(), 0)

    def test_project_creation_does_not_consume_credits(self):
        payload = {
            "title": "Usage test",
            "prompt": "A farmer walks through a village.",
            "duration": 10,
            "aspect_ratio": "9:16",
            "characters": [{"name": "Farmer", "role": "lead"}],
        }
        response = self.client.post("/api/video/projects/", payload, format="json")
        self.assertEqual(response.status_code, 201)
        account = get_or_create_credit_account(self.user)
        self.assertEqual(account.balance, 10)
        self.assertEqual(CreditTransaction.objects.filter(kind=CreditTransaction.Kind.RESERVE).count(), 0)

    def test_usage_summary_is_user_scoped(self):
        project = VideoProject.objects.create(user=self.user, title="Usage project", prompt="test", duration=10)
        UsageEvent.objects.create(user=self.user, kind=UsageEvent.Kind.SCENE, quantity=1, credits=10, project=project, idempotency_key="usage-api-scene")
        response = self.client.get("/api/video/usage/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["scenes"], 1)
        self.assertEqual(response.data["credits_consumed"], 10)
