from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .billing import PLANS
from .models import Subscription, VideoProject
from .views import _validate_plan_duration


class PlanEntitlementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="entitlement-user", password="pass12345")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def payload(self, duration):
        return {
            "title": "Entitlement test",
            "prompt": "A farmer walks through a quiet village.",
            "input_type": "story",
            "duration": duration,
            "aspect_ratio": "9:16",
            "characters": [{"name": "Farmer", "role": "main", "appearance": "3D animated farmer"}],
        }

    def test_free_plan_allows_ten_seconds_but_not_thirty(self):
        self.assertIsNone(_validate_plan_duration(self.user, 10))
        self.assertIn("10 seconds", _validate_plan_duration(self.user, 30))

        allowed = self.client.post("/api/video/projects/", self.payload(10), format="json")
        self.assertEqual(allowed.status_code, 201)

        blocked = self.client.post("/api/video/projects/", self.payload(30), format="json")
        self.assertEqual(blocked.status_code, 402)
        self.assertEqual(VideoProject.objects.filter(user=self.user).count(), 1)

    def test_creator_plan_allows_thirty_seconds(self):
        subscription = Subscription.objects.create(user=self.user, plan_code=Subscription.Plan.CREATOR)
        self.assertEqual(PLANS[subscription.plan_code].max_duration, 30)
        self.assertIsNone(_validate_plan_duration(self.user, 30))
        self.assertIn("30 seconds", _validate_plan_duration(self.user, 60))

    def test_pro_plan_allows_sixty_seconds(self):
        Subscription.objects.create(user=self.user, plan_code=Subscription.Plan.PRO)
        self.assertIsNone(_validate_plan_duration(self.user, 60))

    def test_inactive_subscription_blocks_generation(self):
        Subscription.objects.create(user=self.user, plan_code=Subscription.Plan.PRO, status=Subscription.Status.PAST_DUE)
        self.assertIn("subscription is not active", _validate_plan_duration(self.user, 10).lower())
