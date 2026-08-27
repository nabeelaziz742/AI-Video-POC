from unittest.mock import Mock, patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .models import VideoProject
from .views import VideoProjectStatusView


class ProjectStatusTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.project = VideoProject.objects.create(
            title="Status Test", prompt="A short story", duration=10, aspect_ratio="9:16",
            provider="json2video", provider_project_id="assembly-123",
        )

    @patch("video_generator.views.JSON2VideoService.get_movie")
    def test_done_movie_marks_project_completed(self, get_movie):
        get_movie.return_value = {"movie": {"status": "done", "url": "https://example.com/final.mp4"}}
        response = VideoProjectStatusView.as_view()(self.factory.get("/status/"), project_id=self.project.id)
        self.assertEqual(response.status_code, 200)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, VideoProject.Status.COMPLETED)
        self.assertEqual(self.project.video_url, "https://example.com/final.mp4")

    @patch("video_generator.views.JSON2VideoService.get_movie")
    def test_provider_error_marks_project_failed(self, get_movie):
        get_movie.return_value = {"movie": {"status": "error", "message": "render failed"}}
        VideoProjectStatusView.as_view()(self.factory.get("/status/"), project_id=self.project.id)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, VideoProject.Status.FAILED)
        self.assertEqual(self.project.error_message, "render failed")

    @patch("video_generator.views.JSON2VideoService.get_movie")
    def test_running_movie_keeps_project_processing(self, get_movie):
        get_movie.return_value = {"movie": {"status": "running"}}
        VideoProjectStatusView.as_view()(self.factory.get("/status/"), project_id=self.project.id)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, VideoProject.Status.PROCESSING)
