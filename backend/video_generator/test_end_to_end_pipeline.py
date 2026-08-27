from unittest.mock import Mock, patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .ai_views import ProjectAssembleView, SceneGenerateView, SceneStatusView
from .models import Character, VideoProject, VideoScene
from .views import VideoProjectStatusView


class EndToEndPipelineTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.project = VideoProject.objects.create(
            title="Pipeline Test", prompt="A character walks home", duration=10, aspect_ratio="9:16"
        )
        self.character = Character.objects.create(
            project=self.project,
            name="Hero",
            appearance="friendly adult",
            reference_image_url="https://example.com/hero.png",
        )
        self.scene = VideoScene.objects.create(
            project=self.project, scene_number=1, duration=10,
            prompt="Hero walks home", status=VideoScene.Status.PLANNED,
        )
        self.scene.characters.add(self.character)

    @patch("video_generator.ai_views.get_video_provider")
    def test_scene_submission_and_completion_lifecycle(self, provider_factory):
        provider = Mock()
        provider.submit_scene.return_value = {"request_id": "scene-job"}
        provider.get_scene_result.return_value = {
            "status": "completed", "video_url": "https://example.com/scene.mp4"
        }
        provider_factory.return_value = provider

        response = SceneGenerateView.as_view()(self.factory.post("/generate/", {}, format="json"), project_id=self.project.id, scene_id=self.scene.id)
        self.assertEqual(response.status_code, 202)
        self.scene.refresh_from_db()
        self.assertEqual(self.scene.status, VideoScene.Status.PROCESSING)

        response = SceneStatusView.as_view()(self.factory.get("/status/"), project_id=self.project.id, scene_id=self.scene.id)
        self.assertEqual(response.status_code, 200)
        self.scene.refresh_from_db()
        self.assertEqual(self.scene.status, VideoScene.Status.COMPLETED)
        self.assertEqual(self.scene.video_url, "https://example.com/scene.mp4")

    @patch("video_generator.ai_views.JSON2VideoService.create_movie_from_clips")
    def test_assembly_then_final_status_completes_project(self, create_movie):
        self.scene.status = VideoScene.Status.COMPLETED
        self.scene.video_url = "https://example.com/scene.mp4"
        self.scene.save(update_fields=["status", "video_url"])
        create_movie.return_value = {"project": "movie-job"}

        response = ProjectAssembleView.as_view()(self.factory.post("/assemble/", {}, format="json"), project_id=self.project.id)
        self.assertEqual(response.status_code, 202)

        with patch("video_generator.views.JSON2VideoService.get_movie") as get_movie:
            get_movie.return_value = {"movie": {"status": "done", "url": "https://example.com/final.mp4"}}
            response = VideoProjectStatusView.as_view()(self.factory.get("/status/"), project_id=self.project.id)

        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, VideoProject.Status.COMPLETED)
        self.assertEqual(self.project.video_url, "https://example.com/final.mp4")
