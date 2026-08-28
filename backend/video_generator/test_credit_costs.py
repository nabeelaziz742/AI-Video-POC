from django.test import SimpleTestCase

from .credits import generation_cost


class GenerationCostTests(SimpleTestCase):
    def test_scene_cost_matches_duration(self):
        self.assertEqual(generation_cost(4), 4)
        self.assertEqual(generation_cost(6), 6)
        self.assertEqual(generation_cost(10), 10)
        self.assertEqual(generation_cost(15), 15)

    def test_unsupported_scene_duration_has_no_charge(self):
        self.assertEqual(generation_cost(0), 0)
        self.assertEqual(generation_cost(16), 0)
