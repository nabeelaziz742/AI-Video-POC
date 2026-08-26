from django.test import TestCase

from .scene_planner import (
    SUPPORTED_DURATIONS,
    build_scene_plan,
    get_dimensions,
    validate_generation_options,
)


class ScenePlannerTests(TestCase):
    def test_supported_durations(self):
        self.assertEqual(SUPPORTED_DURATIONS, (10, 30, 60))

    def test_scene_plan_duration_matches_project_duration(self):
        for duration in SUPPORTED_DURATIONS:
            scenes = build_scene_plan("A farmer visits the village market.", duration)
            self.assertEqual(sum(scene["duration"] for scene in scenes), duration)
            self.assertEqual(len(scenes), max(1, (duration + 5) // 6))

    def test_scene_numbers_are_sequential(self):
        scenes = build_scene_plan("A short story.", 30)
        self.assertEqual(
            [scene["scene_number"] for scene in scenes],
            list(range(1, len(scenes) + 1)),
        )

    def test_generation_options(self):
        self.assertEqual(validate_generation_options(30, "9:16"), (30, "9:16"))
        self.assertEqual(get_dimensions("9:16"), (1080, 1920))
        self.assertEqual(get_dimensions("16:9"), (1920, 1080))
        self.assertEqual(get_dimensions("1:1"), (1080, 1080))

    def test_invalid_duration_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_generation_options(20, "9:16")

    def test_invalid_aspect_ratio_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_generation_options(30, "4:3")
