from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .models import VideoProject
from .views import VideoProjectCreateView


class ProjectCreationTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def payload(self, duration=10):
        return {
            "title": "Farmer Story",
            "prompt": "A farmer walks through a village.",
            "input_type": "story",
            "duration": duration,
            "aspect_ratio": "9:16",
            "characters": [{"name": "Farmer", "appearance": "kind rural farmer"}],
        }

    @patch("video_generator.views.build_scene_plan")
    def test_project_creation_validates_duration_and_creates_scenes(self, planner):
        planner.return_value = [
            {"scene_number": 1, "duration": 5, "prompt": "Opening scene"},
            {"scene_number": 2, "duration": 5, "prompt": "Closing scene"},
        ]
        request = self.factory.post("/projects/", self.payload(), format="json")
        response = VideoProjectCreateView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        project = VideoProject.objects.get(id=response.data["id"])
        self.assertEqual(project.duration, 10)
        self.assertEqual(project.scenes.count(), 2)
        self.assertEqual(project.scenes.first().characters.count(), 1)

    def test_project_creation_rejects_missing_prompt(self):
        data = self.payload()
        data["prompt"] = ""
        request = self.factory.post("/projects/", data, format="json")
        response = VideoProjectCreateView.as_view()(request)
        self.assertEqual(response.status_code, 400)

    def test_project_creation_requires_recurring_character(self):
        data = self.payload()
        data["characters"] = []
        request = self.factory.post("/projects/", data, format="json")
        response = VideoProjectCreateView.as_view()(request)
        self.assertEqual(response.status_code, 400)

    def test_project_creation_rejects_unsupported_duration(self):
        data = self.payload(duration=20)
        request = self.factory.post("/projects/", data, format="json")
        response = VideoProjectCreateView.as_view()(request)
        self.assertEqual(response.status_code, 400)
