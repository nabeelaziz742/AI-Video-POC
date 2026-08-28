from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .ai_views import ProjectAssembleView
from .models import VideoProject, VideoScene


class ProjectAssemblyTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="assembler", password="StrongPass123")
        self.project = VideoProject.objects.create(user=self.user, title="Assembly Test", prompt="A short story", duration=10, aspect_ratio="9:16")

    def request(self):
        request = self.factory.post("/assemble/", {}, format="json"); request.user = self.user; return request

    def add_scene(self, number, status, url=None):
        return VideoScene.objects.create(project=self.project, scene_number=number, duration=5, prompt=f"Scene {number}", status=status, video_url=url)

    def test_assembly_rejects_incomplete_scenes(self):
        self.add_scene(1, VideoScene.Status.COMPLETED, "https://example.com/1.mp4"); self.add_scene(2, VideoScene.Status.PROCESSING)
        response = ProjectAssembleView.as_view()(self.request(), project_id=self.project.id); self.assertEqual(response.status_code, 400)

    def test_assembly_rejects_completed_scene_without_video_url(self):
        self.add_scene(1, VideoScene.Status.COMPLETED)
        response = ProjectAssembleView.as_view()(self.request(), project_id=self.project.id); self.assertEqual(response.status_code, 400); self.assertIn("video URLs", response.data["detail"])

    @patch("video_generator.ai_views.JSON2VideoService.create_movie_from_clips")
    def test_assembly_submits_completed_scene_clips_in_scene_order(self, create_movie):
        self.add_scene(2, VideoScene.Status.COMPLETED, "https://example.com/2.mp4"); self.add_scene(1, VideoScene.Status.COMPLETED, "https://example.com/1.mp4"); create_movie.return_value = {"project": "assembly-job"}
        response = ProjectAssembleView.as_view()(self.request(), project_id=self.project.id); self.assertEqual(response.status_code, 202)
        kwargs = create_movie.call_args.kwargs; self.assertEqual(kwargs["clips"], [{"scene_number": 1, "video_url": "https://example.com/1.mp4"}, {"scene_number": 2, "video_url": "https://example.com/2.mp4"}]); self.project.refresh_from_db(); self.assertEqual(self.project.provider_project_id, "assembly-job"); self.assertEqual(self.project.status, VideoProject.Status.PROCESSING)

    @patch("video_generator.ai_views.JSON2VideoService.create_movie_from_clips")
    def test_assembly_provider_failure_marks_project_failed(self, create_movie):
        create_movie.side_effect = RuntimeError("JSON2Video unavailable"); self.add_scene(1, VideoScene.Status.COMPLETED, "https://example.com/1.mp4")
        response = ProjectAssembleView.as_view()(self.request(), project_id=self.project.id); self.assertEqual(response.status_code, 502); self.project.refresh_from_db(); self.assertEqual(self.project.status, VideoProject.Status.FAILED); self.assertEqual(self.project.error_message, "Video assembly provider failed.")
