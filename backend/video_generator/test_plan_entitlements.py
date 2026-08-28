from django.contrib.auth import get_user_model
from django.test import TestCase

from .billing import PLANS
from .models import Subscription
from .ai_views import _plan_generation_error


class PlanEntitlementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="entitlement-user", password="pass12345")

    def test_free_plan_allows_ten_seconds_but_not_thirty(self):
        self.assertIsNone(_plan_generation_error(self.user, 10))
        self.assertIn("10 seconds", _plan_generation_error(self.user, 30))

    def test_creator_plan_allows_thirty_seconds(self):
        subscription = Subscription.objects.create(user=self.user, plan_code=Subscription.Plan.CREATOR)
        self.assertEqual(PLANS[subscription.plan_code].max_duration, 30)
        self.assertIsNone(_plan_generation_error(self.user, 30))
        self.assertIn("30 seconds", _plan_generation_error(self.user, 60))

    def test_pro_plan_allows_sixty_seconds(self):
        Subscription.objects.create(user=self.user, plan_code=Subscription.Plan.PRO)
        self.assertIsNone(_plan_generation_error(self.user, 60))

    def test_inactive_subscription_blocks_generation(self):
        Subscription.objects.create(user=self.user, plan_code=Subscription.Plan.PRO, status=Subscription.Status.PAST_DUE)
        self.assertIn("subscription is not active", _plan_generation_error(self.user, 10).lower())
