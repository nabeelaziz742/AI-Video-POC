from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .models import Character, VideoProject, VideoScene
from .views import VideoProjectVersionsView


class ProjectVersioningTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(username="version-user", password="StrongPass123")
        self.other = User.objects.create_user(username="other-user", password="StrongPass123")
        self.project = VideoProject.objects.create(user=self.user, title="Farmer", prompt="A farmer walks home", duration=10, aspect_ratio="9:16", status=VideoProject.Status.COMPLETED, video_url="https://example.com/v1.mp4", provider="json2video")
        self.character = Character.objects.create(project=self.project, name="Farmer", appearance="same face", clothing="green vest", reference_image_url="https://example.com/farmer-ref.png")
        scene = VideoScene.objects.create(project=self.project, scene_number=1, duration=5, prompt="Farmer walks")
        scene.characters.add(self.character)

    def request(self, method, path, data=None, user=None):
        request = getattr(self.factory, method)(path, data or {}, format="json")
        request.user = user or self.user
        return request

    def test_create_version_preserves_previous_video_and_reference(self):
        response = VideoProjectVersionsView.as_view()(self.request("post", "/versions/", {"prompt": "A farmer walks home during a storm"}), project_id=self.project.id)
        self.assertEqual(response.status_code, 201)
        version = VideoProject.objects.get(id=response.data["id"])
        self.project.refresh_from_db()
        self.assertEqual(version.version_number, 2)
        self.assertEqual(version.version_group, self.project.version_group)
        self.assertEqual(self.project.video_url, "https://example.com/v1.mp4")
        self.assertEqual(version.characters.first().reference_image_url, "https://example.com/farmer-ref.png")
        self.assertNotEqual(version.id, self.project.id)

    def test_changed_character_definition_gets_fresh_reference(self):
        response = VideoProjectVersionsView.as_view()(self.request("post", "/versions/", {"prompt": "New story", "characters": [{"name": "Farmer", "appearance": "different face", "clothing": "blue jacket"}]}), project_id=self.project.id)
        self.assertEqual(response.status_code, 201)
        version = VideoProject.objects.get(id=response.data["id"])
        self.assertIsNone(version.characters.first().reference_image_url)

    def test_versions_are_isolated(self):
        response = VideoProjectVersionsView.as_view()(self.request("post", "/versions/", {"prompt": "Version two"}), project_id=self.project.id)
        version = VideoProject.objects.get(id=response.data["id"])
        version.scenes.first().status = VideoScene.Status.FAILED
        version.scenes.first().save(update_fields=["status"])
        self.assertEqual(self.project.scenes.first().status, VideoScene.Status.PLANNED)
        self.assertEqual(self.project.video_url, "https://example.com/v1.mp4")

    def test_history_is_owner_scoped(self):
        response = VideoProjectVersionsView.as_view()(self.request("get", "/versions/", user=self.other), project_id=self.project.id)
        self.assertEqual(response.status_code, 404)

    def test_history_returns_all_versions_in_order(self):
        VideoProjectVersionsView.as_view()(self.request("post", "/versions/", {"prompt": "Version two"}), project_id=self.project.id)
        response = VideoProjectVersionsView.as_view()(self.request("get", "/versions/"), project_id=self.project.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["version_number"] for item in response.data], [1, 2])
