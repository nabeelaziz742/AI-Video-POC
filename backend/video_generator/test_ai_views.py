from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .ai_views import SceneGenerateView, SceneRegenerateView
from .models import Character, VideoProject, VideoScene


class FakeProvider:
    def submit_scene(self, **kwargs):
        return {"request_id": "fake-job", "provider": "fake"}


class SceneGenerationSafetyTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="creator", password="StrongPass123")
        self.project = VideoProject.objects.create(user=self.user, title="Test Project", prompt="A farmer story", duration=10, aspect_ratio="9:16")
        self.character = Character.objects.create(project=self.project, name="Farmer", appearance="friendly farmer", reference_image_url="https://example.com/farmer.png")
        self.scene = VideoScene.objects.create(project=self.project, scene_number=1, duration=5, prompt="The farmer walks.")
        self.scene.characters.add(self.character)

    def request(self, path):
        request = self.factory.post(path, {}, format="json")
        self.factory.force_authenticate(request, user=self.user)
        return request

    def test_duplicate_processing_generation_is_not_submitted(self):
        self.scene.status = VideoScene.Status.PROCESSING
        self.scene.provider_project_id = "existing-job"
        self.scene.save(update_fields=["status", "provider_project_id"])
        response = SceneGenerateView.as_view()(self.request("/generate/"), project_id=self.project.id, scene_id=self.scene.id)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["provider_project_id"], "existing-job")

    def test_generation_requires_reference_images(self):
        self.character.reference_image_url = None
        self.character.save(update_fields=["reference_image_url"])
        response = SceneGenerateView.as_view()(self.request("/generate/"), project_id=self.project.id, scene_id=self.scene.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("reference", response.data["detail"].lower())

    @patch("video_generator.ai_views.get_video_provider", return_value=FakeProvider())
    def test_generation_uses_provider_without_calling_real_api(self, mock_provider):
        response = SceneGenerateView.as_view()(self.request("/generate/"), project_id=self.project.id, scene_id=self.scene.id)
        self.assertEqual(response.status_code, 202)
        self.scene.refresh_from_db()
        self.assertEqual(self.scene.status, VideoScene.Status.PROCESSING)
        self.assertEqual(self.scene.provider_project_id, "fake-job")
        mock_provider.assert_called_once_with("fal_pixverse_c1")

    @patch("video_generator.ai_views.get_video_provider", return_value=FakeProvider())
    def test_regeneration_replaces_previous_provider_job(self, mock_provider):
        self.scene.status = VideoScene.Status.FAILED
        self.scene.provider_project_id = "old-job"
        self.scene.video_url = "https://example.com/old.mp4"
        self.scene.error_message = "old error"
        self.scene.save()
        response = SceneRegenerateView.as_view()(self.request("/regenerate/"), project_id=self.project.id, scene_id=self.scene.id)
        self.assertEqual(response.status_code, 202)
        self.scene.refresh_from_db()
        self.assertEqual(self.scene.provider_project_id, "fake-job")
        self.assertIsNone(self.scene.video_url)
        self.assertIsNone(self.scene.error_message)
