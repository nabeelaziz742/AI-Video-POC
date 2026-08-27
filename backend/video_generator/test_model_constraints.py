from django.db import IntegrityError
from django.test import TestCase

from .models import VideoProject, VideoScene


class VideoSceneConstraintTests(TestCase):
    def test_scene_number_is_unique_per_project(self):
        project = VideoProject.objects.create(
            title="Constraint Test", prompt="A short story", duration=10, aspect_ratio="9:16"
        )
        VideoScene.objects.create(project=project, scene_number=1, duration=5, prompt="First")
        with self.assertRaises(IntegrityError):
            VideoScene.objects.create(project=project, scene_number=1, duration=5, prompt="Duplicate")

    def test_same_scene_number_is_allowed_in_different_projects(self):
        project_a = VideoProject.objects.create(title="A", prompt="Story A", duration=10, aspect_ratio="9:16")
        project_b = VideoProject.objects.create(title="B", prompt="Story B", duration=10, aspect_ratio="9:16")
        VideoScene.objects.create(project=project_a, scene_number=1, duration=5, prompt="A1")
        VideoScene.objects.create(project=project_b, scene_number=1, duration=5, prompt="B1")
        self.assertEqual(VideoScene.objects.filter(scene_number=1).count(), 2)
