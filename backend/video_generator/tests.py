from django.test import TestCase

from .models import Character, VideoProject, VideoScene
from .scene_planner import build_scene_plan, get_dimensions, validate_generation_options


class GenerationOptionsTests(TestCase):
    def test_supported_durations(self):
        for duration in (10, 30, 60):
            self.assertEqual(validate_generation_options(duration, "9:16"), (duration, "9:16"))

    def test_invalid_duration(self):
        with self.assertRaises(ValueError):
            validate_generation_options(20, "9:16")

    def test_aspect_dimensions(self):
        self.assertEqual(get_dimensions("9:16"), (1080, 1920))
        self.assertEqual(get_dimensions("16:9"), (1920, 1080))
        self.assertEqual(get_dimensions("1:1"), (1080, 1080))

    def test_scene_plan_matches_requested_duration(self):
        for duration in (10, 30, 60):
            scenes = build_scene_plan("A farmer walks with his buffalo.", duration)
            self.assertEqual(sum(scene["duration"] for scene in scenes), duration)
            self.assertEqual([scene["scene_number"] for scene in scenes], list(range(1, len(scenes) + 1)))


class CharacterSceneModelTests(TestCase):
    def test_character_and_scene_are_linked_to_project(self):
        project = VideoProject.objects.create(title="Farmer Story", prompt="A farmer story")
        character = Character.objects.create(
            project=project,
            name="Farmer",
            role="Main character",
            appearance="Friendly 3D cartoon farmer",
            clothing="Blue shalwar kameez",
        )
        scene = VideoScene.objects.create(
            project=project,
            scene_number=1,
            duration=10,
            prompt="The farmer walks through the village.",
        )
        scene.characters.add(character)

        self.assertEqual(project.characters.count(), 1)
        self.assertEqual(project.scenes.count(), 1)
        self.assertEqual(scene.characters.first(), character)

    def test_scene_numbers_are_unique_per_project(self):
        project = VideoProject.objects.create(title="Story", prompt="Story")
        VideoScene.objects.create(project=project, scene_number=1, duration=10, prompt="Scene one")
        with self.assertRaises(Exception):
            VideoScene.objects.create(project=project, scene_number=1, duration=10, prompt="Duplicate")
