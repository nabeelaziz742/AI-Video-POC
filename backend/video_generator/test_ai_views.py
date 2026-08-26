from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .ai_views import SceneGenerateView, SceneRegenerateView
from .models import Character, VideoProject, VideoScene
from .providers import VideoProviderError


class SceneGenerationSafetyTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.project = VideoProject.objects.create(
            title="Test Project", prompt="A farmer story", duration=10, aspect_ratio="9:16"
        )
        self.character = Character.objects.create(
            project=self.project,
            name="Farmer",
            appearance="friendly farmer",
            reference_image_url="https://example.com/farmer.png",
        )
        self.scene = VideoScene.objects.create(
            project=self.project, scene_number=1, duration=5, prompt="The farmer walks."
        )
        self.scene.characters.add(self.character)

    def test_duplicate_processing_generation_is_not_submitted(self):
        self.scene.status = VideoScene.Status.PROCESSING
        self.scene.provider_project_id = "existing-job"
        self.scene.save(update_fields=["status", "provider_project_id"])
        request = self.factory.post("/generate/", {}, format="json")
        response = SceneGenerateView.as_view()(request, project_id=self.project.id, scene_id=self.scene.id)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["provider_project_id"], "existing-job")

    def test_generation_requires_reference_images(self):
        self.character.reference_image_url = None
        self.character.save(update_fields=["reference_image_url"])
        request = self.factory.post("/generate/", {}, format="json")
        response = SceneGenerateView.as_view()(request, project_id=self.project.id, scene_id=self.scene.id)
        self.assertEqual(response.status_code, 400)
        self.assertIn("reference", response.data["detail"].lower())

    def test_regeneration_resets_previous_failure_before_submission(self):
        self.scene.status = VideoScene.Status.FAILED
        self.scene.provider_project_id = "old-job"
        self.scene.video_url = "https://example.com/old.mp4"
        self.scene.error_message = "old error"
        self.scene.save()

        request = self.factory.post("/regenerate/", {}, format="json")
        try:
            response = SceneRegenerateView.as_view()(request, project_id=self.project.id, scene_id=self.scene.id)
        except VideoProviderError:
            response = None
        self.scene.refresh_from_db()
        self.assertNotEqual(self.scene.provider_project_id, "old-job")
        self.assertIsNone(self.scene.video_url)
        self.assertIsNone(self.scene.error_message)
