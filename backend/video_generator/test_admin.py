from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from .credits import get_or_create_credit_account
from .models import (
    CreditAccount,
    CreditTransaction,
    Subscription,
    VideoProject,
    VideoScene,
)
from .security import mask_secret


class AdminPermissionAndSecurityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.normal_user = User.objects.create_user(username="normaluser", password="password123", email="user@example.com")
        self.staff_user = User.objects.create_user(username="adminuser", password="adminpassword123", email="admin@example.com", is_staff=True)

    def test_unauthenticated_requests_are_rejected(self):
        endpoints = [
            "/api/video/admin/stats/",
            "/api/video/admin/users/",
            f"/api/video/admin/users/{self.normal_user.id}/credits/",
            "/api/video/admin/projects/",
            "/api/video/admin/system/",
        ]
        for url in endpoints:
            res = self.client.get(url)
            self.assertIn(res.status_code, [401, 403], f"Endpoint {url} should require authentication")

    def test_non_staff_users_are_forbidden(self):
        self.client.force_authenticate(user=self.normal_user)
        endpoints = [
            "/api/video/admin/stats/",
            "/api/video/admin/users/",
            "/api/video/admin/projects/",
            "/api/video/admin/system/",
        ]
        for url in endpoints:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 403, f"Endpoint {url} should reject non-staff users with 403")

        post_res = self.client.post(f"/api/video/admin/users/{self.normal_user.id}/credits/", {"amount": 50})
        self.assertEqual(post_res.status_code, 403)

    def test_staff_user_can_access_admin_stats(self):
        self.client.force_authenticate(user=self.staff_user)
        project = VideoProject.objects.create(user=self.normal_user, title="Test Project", status=VideoProject.Status.COMPLETED)
        VideoScene.objects.create(project=project, scene_number=1, duration=10, prompt="Scene 1", status=VideoScene.Status.COMPLETED)

        res = self.client.get("/api/video/admin/stats/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("users", data)
        self.assertIn("subscriptions", data)
        self.assertIn("projects", data)
        self.assertIn("scenes", data)
        self.assertIn("credits", data)
        self.assertEqual(data["users"]["total"], 2)
        self.assertEqual(data["projects"]["completed"], 1)

    def test_staff_user_can_list_and_search_users(self):
        self.client.force_authenticate(user=self.staff_user)
        res = self.client.get("/api/video/admin/users/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["users"]), 2)

        # Search query
        search_res = self.client.get("/api/video/admin/users/?q=normal")
        self.assertEqual(search_res.status_code, 200)
        self.assertEqual(len(search_res.json()["users"]), 1)
        self.assertEqual(search_res.json()["users"][0]["username"], "normaluser")

    def test_admin_credit_adjustment_is_auditable_and_idempotent(self):
        self.client.force_authenticate(user=self.staff_user)
        account = get_or_create_credit_account(self.normal_user)
        account.balance = 50
        account.save()

        # Grant credits
        idempotency_key = "admin-grant-test-123"
        res = self.client.post(
            f"/api/video/admin/users/{self.normal_user.id}/credits/",
            {"amount": 100, "note": "Bonus credits", "idempotency_key": idempotency_key},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["balance"], 150)
        self.assertEqual(data["replayed"], False)

        # Replay with same idempotency key
        res_replay = self.client.post(
            f"/api/video/admin/users/{self.normal_user.id}/credits/",
            {"amount": 100, "note": "Bonus credits", "idempotency_key": idempotency_key},
            format="json",
        )
        self.assertEqual(res_replay.status_code, 200)
        self.assertEqual(res_replay.json()["replayed"], True)
        self.assertEqual(res_replay.json()["balance"], 150)

        # Verify audit transaction
        tx = CreditTransaction.objects.get(idempotency_key=idempotency_key)
        self.assertEqual(tx.amount, 100)
        self.assertIn("adminuser", tx.note)

        # Deduct credits
        res_deduct = self.client.post(
            f"/api/video/admin/users/{self.normal_user.id}/credits/",
            {"amount": -50, "note": "Correction", "idempotency_key": "admin-deduct-test-456"},
            format="json",
        )
        self.assertEqual(res_deduct.status_code, 200)
        self.assertEqual(res_deduct.json()["balance"], 100)

        # Deduct more than available balance should fail
        res_excess = self.client.post(
            f"/api/video/admin/users/{self.normal_user.id}/credits/",
            {"amount": -500, "note": "Excess"},
            format="json",
        )
        self.assertEqual(res_excess.status_code, 400)

    def test_admin_system_health_masks_secrets(self):
        self.client.force_authenticate(user=self.staff_user)
        res = self.client.get("/api/video/admin/system/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("database", data)
        self.assertIn("providers", data)
        self.assertIn("storage", data)
        self.assertIn("environment", data)

        # Ensure secrets are never exposed in plaintext
        providers = data["providers"]
        for prov_name, prov_info in providers.items():
            for key, val in prov_info.items():
                if "key" in key or "secret" in key:
                    if val:
                        self.assertIn("...", str(val))
                        self.assertNotIn("sk_live_1234567890abcdef", str(val))

    def test_user_serializer_includes_staff_flags(self):
        self.client.force_authenticate(user=self.staff_user)
        me_res = self.client.get("/api/video/auth/me/")
        self.assertEqual(me_res.status_code, 200)
        user_data = me_res.json()["user"]
        self.assertTrue(user_data["is_staff"])
        self.assertIn("is_superuser", user_data)
