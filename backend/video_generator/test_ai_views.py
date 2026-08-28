from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .ai_views import SceneGenerateView, SceneRegenerateView, SceneStatusView
from .credits import get_or_create_credit_account
from .models import Character, CreditTransaction, VideoProject, VideoScene


class FakeProvider:
    def submit_scene(self, **kwargs): return {"request_id": "fake-job", "provider": "fake"}

    def get_scene_result(self, request_id): return {"status": "processing"}


class FailingSubmitProvider:
    def submit_scene(self, **kwargs): raise RuntimeError("provider unavailable")


class FailingStatusProvider:
    def get_scene_result(self, request_id): return {"status": "failed", "error": "generation failed"}


class SceneGenerationSafetyTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="creator", password="StrongPass123")
        account = get_or_create_credit_account(self.user)
        account.balance = 100
        account.save(update_fields=["balance", "updated_at"])
        self.project = VideoProject.objects.create(user=self.user, title="Test Project", prompt="A farmer story", duration=10, aspect_ratio="9:16")
        self.character = Character.objects.create(project=self.project, name="Farmer", appearance="friendly farmer", reference_image_url="https://example.com/farmer.png")
        self.scene = VideoScene.objects.create(project=self.project, scene_number=1, duration=10, prompt="The farmer walks.")
        self.scene.characters.add(self.character)

    def request(self, path):
        request = self.factory.post(path, {}, format="json")
        request.user = self.user
        return request

    def get_request(self):
        request = self.factory.get("/status/")
        request.user = self.user
        return request

    def test_duplicate_processing_generation_is_not_submitted(self):
        self.scene.status = VideoScene.Status.PROCESSING; self.scene.provider_project_id = "existing-job"; self.scene.save(update_fields=["status", "provider_project_id"])
        response = SceneGenerateView.as_view()(self.request("/generate/"), project_id=self.project.id, scene_id=self.scene.id)
        self.assertEqual(response.status_code, 202); self.assertEqual(response.data["provider_project_id"], "existing-job")

    def test_generation_requires_reference_images(self):
        self.character.reference_image_url = None; self.character.save(update_fields=["reference_image_url"])
        response = SceneGenerateView.as_view()(self.request("/generate/"), project_id=self.project.id, scene_id=self.scene.id)
        self.assertEqual(response.status_code, 400); self.assertIn("reference", response.data["detail"].lower())

    @patch("video_generator.ai_views.get_video_provider", return_value=FakeProvider())
    def test_generation_uses_provider_without_calling_real_api(self, mock_provider):
        response = SceneGenerateView.as_view()(self.request("/generate/"), project_id=self.project.id, scene_id=self.scene.id)
        self.assertEqual(response.status_code, 202); self.scene.refresh_from_db(); self.assertEqual(self.scene.status, VideoScene.Status.PROCESSING); self.assertEqual(self.scene.provider_project_id, "fake-job"); self.assertEqual(self.scene.generation_attempt, 1); mock_provider.assert_called_once_with("fal_pixverse_c1")

    @patch("video_generator.ai_views.get_video_provider", return_value=FailingSubmitProvider())
    def test_provider_submission_failure_refunds_and_increments_attempt(self, mock_provider):
        response = SceneGenerateView.as_view()(self.request("/generate/"), project_id=self.project.id, scene_id=self.scene.id)
        self.assertEqual(response.status_code, 502)
        self.scene.refresh_from_db()
        self.assertEqual(self.scene.generation_attempt, 1)
        self.assertEqual(self.scene.status, VideoScene.Status.FAILED)
        self.assertEqual(self.user.credit_account.balance, 100)
        self.assertTrue(CreditTransaction.objects.filter(kind=CreditTransaction.Kind.REFUND).exists())
        mock_provider.assert_called_once_with("fal_pixverse_c1")

    @patch("video_generator.ai_views.get_video_provider", return_value=FailingStatusProvider())
    def test_async_failure_refunds_exact_scene_reservation(self, mock_provider):
        self.scene.status = VideoScene.Status.PROCESSING
        self.scene.provider = "fal_pixverse_c1"
        self.scene.provider_project_id = "provider-job"
        self.scene.generation_attempt = 1
        self.scene.save(update_fields=["status", "provider", "provider_project_id", "generation_attempt"])
        from .credits import reserve_credits
        reserve_credits(self.user, 10, idempotency_key=f"scene-generation:{self.scene.id}:1", project=self.project)
        response = SceneStatusView.as_view()(self.get_request(), project_id=self.project.id, scene_id=self.scene.id)
        self.assertEqual(response.status_code, 200)
        self.scene.refresh_from_db()
        self.assertEqual(self.scene.status, VideoScene.Status.FAILED)
        self.assertEqual(self.user.credit_account.balance, 100)
        self.assertTrue(CreditTransaction.objects.filter(kind=CreditTransaction.Kind.REFUND, idempotency_key=f"refund:scene-generation:{self.scene.id}:1").exists())
        mock_provider.assert_called_once_with("fal_pixverse_c1")

    @patch("video_generator.ai_views.get_video_provider", return_value=FakeProvider())
    def test_regeneration_replaces_previous_provider_job(self, mock_provider):
        self.scene.status = VideoScene.Status.FAILED; self.scene.provider_project_id = "old-job"; self.scene.video_url = "https://example.com/old.mp4"; self.scene.error_message = "old error"; self.scene.save()
        response = SceneRegenerateView.as_view()(self.request("/regenerate/"), project_id=self.project.id, scene_id=self.scene.id)
        self.assertEqual(response.status_code, 202); self.scene.refresh_from_db(); self.assertEqual(self.scene.provider_project_id, "fake-job"); self.assertIsNone(self.scene.video_url); self.assertIsNone(self.scene.error_message)
