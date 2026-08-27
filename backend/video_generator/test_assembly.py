from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .ai_views import ProjectAssembleView
from .models import VideoProject, VideoScene


class ProjectAssemblyTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.project = VideoProject.objects.create(
            title="Assembly Test", prompt="A short story", duration=10, aspect_ratio="9:16"
        )

    def add_scene(self, number, status, url=None):
        return VideoScene.objects.create(
            project=self.project,
            scene_number=number,
            duration=5,
            prompt=f"Scene {number}",
            status=status,
            video_url=url,
        )

    def test_assembly_rejects_incomplete_scenes(self):
        self.add_scene(1, VideoScene.Status.COMPLETED, "https://example.com/1.mp4")
        self.add_scene(2, VideoScene.Status.PROCESSING)
        request = self.factory.post("/assemble/", {}, format="json")
        response = ProjectAssembleView.as_view()(request, project_id=self.project.id)
        self.assertEqual(response.status_code, 400)

    @patch("video_generator.ai_views.JSON2VideoService.create_movie_from_clips")
    def test_assembly_submits_only_completed_scene_clips(self, create_movie):
        self.add_scene(1, VideoScene.Status.COMPLETED, "https://example.com/1.mp4")
        self.add_scene(2, VideoScene.Status.COMPLETED, "https://example.com/2.mp4")
        create_movie.return_value = {"project": "assembly-job"}

        request = self.factory.post("/assemble/", {}, format="json")
        response = ProjectAssembleView.as_view()(request, project_id=self.project.id)

        self.assertEqual(response.status_code, 202)
        create_movie.assert_called_once()
        kwargs = create_movie.call_args.kwargs
        self.assertEqual(
            kwargs["clips"],
            [
                {"scene_number": 1, "video_url": "https://example.com/1.mp4"},
                {"scene_number": 2, "video_url": "https://example.com/2.mp4"},
            ],
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.provider_project_id, "assembly-job")
        self.assertEqual(self.project.status, VideoProject.Status.PROCESSING)
