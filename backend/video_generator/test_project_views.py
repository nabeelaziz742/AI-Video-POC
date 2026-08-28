from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .models import VideoProject
from .views import VideoProjectCreateView


class ProjectCreationTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="creator", password="StrongPass123")

    def payload(self, duration=10):
        return {
            "title": "Farmer Story",
            "prompt": "A farmer walks through a village.",
            "input_type": "story",
            "duration": duration,
            "aspect_ratio": "9:16",
            "characters": [{"name": "Farmer", "appearance": "kind rural farmer"}],
        }

    def request(self, data):
        request = self.factory.post("/projects/", data, format="json")
        self.factory.force_authenticate(request, user=self.user)
        return request

    def test_project_creation_validates_duration_and_creates_scenes(self):
        response = VideoProjectCreateView.as_view()(self.request(self.payload()))
        self.assertEqual(response.status_code, 201)
        project = VideoProject.objects.get(id=response.data["id"])
        self.assertEqual(project.duration, 10)
        self.assertEqual(project.scenes.count(), 2)
        self.assertEqual(project.scenes.first().characters.count(), 1)
        self.assertEqual(project.user, self.user)

    def test_project_creation_rejects_missing_prompt(self):
        data = self.payload()
        data["prompt"] = ""
        response = VideoProjectCreateView.as_view()(self.request(data))
        self.assertEqual(response.status_code, 400)

    def test_project_creation_requires_recurring_character(self):
        data = self.payload()
        data["characters"] = []
        response = VideoProjectCreateView.as_view()(self.request(data))
        self.assertEqual(response.status_code, 400)

    def test_project_creation_rejects_unsupported_duration(self):
        data = self.payload(duration=20)
        response = VideoProjectCreateView.as_view()(self.request(data))
        self.assertEqual(response.status_code, 400)
