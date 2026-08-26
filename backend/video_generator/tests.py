from django.test import TestCase
from rest_framework.test import APIRequestFactory

from .models import Character, VideoProject, VideoScene
from .providers import FalPixVerseC1Provider, VideoProviderError
from .scene_planner import build_scene_plan, get_dimensions, validate_generation_options
from .views import VideoProjectCreateView


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

    def test_scene_plan_uses_short_ai_video_clips(self):
        for duration in (10, 30, 60):
            scenes = build_scene_plan("A farmer walks with his buffalo.", duration)
            self.assertTrue(all(1 <= scene["duration"] <= 15 for scene in scenes))
            self.assertEqual(len(scenes), {10: 2, 30: 5, 60: 10}[duration])


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


class ProjectPlanningAPITests(TestCase):
    def test_project_creation_only_plans_scenes(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/projects/",
            {
                "title": "Farmer Story",
                "prompt": "A farmer walks with his buffalo.",
                "duration": 10,
                "aspect_ratio": "9:16",
                "characters": [{"name": "Farmer", "appearance": "friendly 3D cartoon farmer"}],
            },
            format="json",
        )
        response = VideoProjectCreateView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        project = VideoProject.objects.get(id=response.data["id"])
        self.assertEqual(project.status, VideoProject.Status.QUEUED)
        self.assertIsNone(project.provider_project_id)
        self.assertEqual(project.scenes.count(), 2)

    def test_project_requires_character(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/projects/",
            {"title": "Story", "prompt": "A farmer story", "duration": 10, "characters": []},
            format="json",
        )
        response = VideoProjectCreateView.as_view()(request)
        self.assertEqual(response.status_code, 400)

    def test_every_planned_scene_contains_all_recurring_characters(self):
        factory = APIRequestFactory()
        request = factory.post(
            "/projects/",
            {
                "title": "Farmer Story",
                "prompt": "A farmer talks to his friend.",
                "duration": 30,
                "aspect_ratio": "9:16",
                "characters": [
                    {"name": "Farmer", "appearance": "friendly farmer"},
                    {"name": "Friend", "appearance": "friendly village friend"},
                ],
            },
            format="json",
        )
        response = VideoProjectCreateView.as_view()(request)
        self.assertEqual(response.status_code, 201)
        project = VideoProject.objects.get(id=response.data["id"])
        self.assertEqual(project.scenes.count(), 5)
        self.assertTrue(all(scene.characters.count() == 2 for scene in project.scenes.all()))


class PixVerseProviderValidationTests(TestCase):
    def test_reference_is_required(self):
        provider = object.__new__(FalPixVerseC1Provider)
        with self.assertRaises(VideoProviderError):
            provider._arguments(prompt="walk", duration=5, aspect_ratio="9:16", reference_image_url=None)

    def test_scene_duration_is_limited_to_provider_range(self):
        provider = object.__new__(FalPixVerseC1Provider)
        with self.assertRaises(VideoProviderError):
            provider._arguments(
                prompt="walk",
                duration=16,
                aspect_ratio="9:16",
                references=[{"image_url": "https://example.com/farmer.png", "ref_name": "character1"}],
            )

    def test_prompt_references_character(self):
        provider = object.__new__(FalPixVerseC1Provider)
        args = provider._arguments(
            prompt="The farmer walks through the village.",
            duration=5,
            aspect_ratio="9:16",
            reference_image_url="https://example.com/farmer.png",
        )
        self.assertIn("@character", args["prompt"])
        self.assertEqual(args["image_references"][0]["type"], "subject")

    def test_multiple_character_references_are_preserved(self):
        provider = object.__new__(FalPixVerseC1Provider)
        references = [
            {"image_url": "https://example.com/farmer.png", "type": "subject", "ref_name": "character1"},
            {"image_url": "https://example.com/friend.png", "type": "subject", "ref_name": "character2"},
        ]
        args = provider._arguments(
            prompt="The farmer talks to his friend.",
            duration=5,
            aspect_ratio="9:16",
            references=references,
        )
        self.assertEqual(len(args["image_references"]), 2)
        self.assertIn("@character1", args["prompt"])
        self.assertIn("@character2", args["prompt"])
