from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from .credits import get_or_create_credit_account, reserve_credits
from .middleware import ProductionErrorMiddleware, RequestIDMiddleware
from .models import Character, CreditAccount, CreditTransaction, VideoProject, VideoScene
from .security import mask_secret, validate_safe_url


class HealthAndInfrastructureTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", password="password123")

    def test_liveness_health_check(self):
        res = self.client.get("/api/video/health/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

        res_live = self.client.get("/api/video/health/live/")
        self.assertEqual(res_live.status_code, 200)
        self.assertEqual(res_live.json()["status"], "ok")

    def test_readiness_health_check(self):
        res = self.client.get("/api/video/health/ready/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["ready"])
        self.assertEqual(data["checks"]["database"], "ok")
        self.assertEqual(data["checks"]["cache"], "ok")

    def test_request_id_middleware_generates_and_propagates_id(self):
        res = self.client.get("/api/video/health/")
        self.assertIn("X-Request-ID", res.headers)
        generated_id = res.headers["X-Request-ID"]
        self.assertTrue(len(generated_id) > 10)

        # Incoming X-Request-ID is preserved
        custom_id = "custom-client-request-id-999"
        res_custom = self.client.get("/api/video/health/", HTTP_X_REQUEST_ID=custom_id)
        self.assertEqual(res_custom.headers["X-Request-ID"], custom_id)

    @override_settings(DEBUG=False)
    def test_production_error_middleware_handles_unhandled_exceptions(self):
        class DummyRequest:
            method = "GET"
            path = "/api/video/test-error/"
            id = "req-123"

        middleware = ProductionErrorMiddleware(lambda r: None)
        response = middleware.process_exception(DummyRequest(), RuntimeError("Something broke internally!"))
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response["X-Request-ID"], "req-123")
        self.assertNotIn("Traceback", response.content.decode())

    def test_validate_safe_url(self):
        self.assertTrue(validate_safe_url("https://cdn.fal.media/output.mp4"))
        self.assertTrue(validate_safe_url("http://api.json2video.com/video.mp4"))
        self.assertTrue(validate_safe_url(None, allow_empty=True))
        self.assertTrue(validate_safe_url("", allow_empty=True))

        self.assertFalse(validate_safe_url("javascript:alert(1)"))
        self.assertFalse(validate_safe_url("file:///etc/passwd"))
        self.assertFalse(validate_safe_url("data:text/html;base64,PHNjcmlwdD4="))
        self.assertFalse(validate_safe_url("not-a-url"))

    def test_mask_secret(self):
        self.assertEqual(mask_secret("sk_test_1234567890abcdef"), "sk_t...cdef")
        self.assertEqual(mask_secret("short"), "***")
        self.assertEqual(mask_secret(None), "")


class ProviderTimeoutAndRecoveryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.client.force_authenticate(user=self.user)
        account = get_or_create_credit_account(self.user)
        account.balance = 200
        account.save()

    def test_scene_processing_timeout_auto_fails_and_refunds(self):
        project = VideoProject.objects.create(user=self.user, title="Timeout Project", status=VideoProject.Status.PROCESSING)
        character = Character.objects.create(project=project, name="Alice", reference_image_url="https://example.com/alice.png")
        scene = VideoScene.objects.create(
            project=project,
            scene_number=1,
            duration=10,
            prompt="Alice walking",
            status=VideoScene.Status.PROCESSING,
            provider="fal_pixverse_c1",
            provider_project_id="fal-req-123",
            generation_attempt=1,
            processing_started_at=timezone.now() - timedelta(seconds=3600), # 1 hour ago (exceeds 1800s timeout)
        )
        scene.characters.add(character)

        # Reserve credits for this attempt
        charge_key = f"scene-generation:{scene.id}:1"
        reserve_credits(self.user, 10, idempotency_key=charge_key, project=project)
        self.user.credit_account.refresh_from_db()
        self.assertEqual(self.user.credit_account.balance, 190)

        # Status check should detect timeout and trigger refund
        res = self.client.get(f"/api/video/projects/{project.id}/scenes/{scene.id}/status/")
        self.assertEqual(res.status_code, 200)
        scene.refresh_from_db()
        self.assertEqual(scene.status, VideoScene.Status.FAILED)
        self.assertIn("timed out", scene.error_message.lower())

        # Verify credit refund
        self.user.credit_account.refresh_from_db()
        self.assertEqual(self.user.credit_account.balance, 200)

        # Subsequent status checks should remain failed and NOT refund again (idempotent)
        res2 = self.client.get(f"/api/video/projects/{project.id}/scenes/{scene.id}/status/")
        self.assertEqual(res2.status_code, 200)
        self.user.credit_account.refresh_from_db()
        self.assertEqual(self.user.credit_account.balance, 200)

    def test_project_assembly_timeout_auto_fails_and_refunds(self):
        project = VideoProject.objects.create(
            user=self.user,
            title="Assembly Timeout Project",
            status=VideoProject.Status.PROCESSING,
            provider="json2video",
            provider_project_id="j2v-assembly-456",
            generation_attempt=1,
            processing_started_at=timezone.now() - timedelta(seconds=3600), # 1 hour ago
        )

        charge_key = f"assembly:{project.id}:1"
        reserve_credits(self.user, 5, idempotency_key=charge_key, project=project)
        self.user.credit_account.refresh_from_db()
        self.assertEqual(self.user.credit_account.balance, 195)

        # Status check detects assembly timeout
        res = self.client.get(f"/api/video/projects/{project.id}/status/")
        self.assertEqual(res.status_code, 200)
        project.refresh_from_db()
        self.assertEqual(project.status, VideoProject.Status.FAILED)
        self.assertIn("timed out", project.error_message.lower())

        # Verify refund
        self.user.credit_account.refresh_from_db()
        self.assertEqual(self.user.credit_account.balance, 200)
