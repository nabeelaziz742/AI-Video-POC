from unittest.mock import patch

from django.test import SimpleTestCase

from .character_generation import CharacterGenerationError, generate_character_reference
from .providers import FalPixVerseC1Provider, VideoProviderError


class FalProviderContractTests(SimpleTestCase):
    @patch.dict("os.environ", {"FAL_KEY": "test-key"})
    @patch("video_generator.providers.fal_client.submit")
    def test_submit_scene_returns_provider_request_id(self, submit):
        submit.return_value.request_id = "req-123"
        provider = FalPixVerseC1Provider()
        result = provider.submit_scene(
            prompt="@character1 walks",
            duration=10,
            aspect_ratio="9:16",
            references=[{"image_url": "https://example.com/a.png", "ref_name": "character1"}],
        )
        self.assertEqual(result["request_id"], "req-123")

    @patch.dict("os.environ", {"FAL_KEY": "test-key"})
    def test_scene_requires_reference(self):
        provider = FalPixVerseC1Provider()
        with self.assertRaises(VideoProviderError):
            provider.submit_scene(prompt="scene", duration=10, aspect_ratio="9:16", references=[])

    @patch.dict("os.environ", {}, clear=True)
    def test_scene_requires_fal_key(self):
        with self.assertRaises(VideoProviderError):
            FalPixVerseC1Provider()


class CharacterProviderContractTests(SimpleTestCase):
    @patch.dict("os.environ", {"FAL_KEY": "test-key"})
    @patch("video_generator.character_generation.fal_client.subscribe")
    def test_character_generation_reads_image_url(self, subscribe):
        subscribe.return_value = {"images": [{"url": "https://example.com/character.png"}]}
        class Character:
            consistency_prompt = "blue jacket, brown hair"
            reference_image_url = None
            def save(self, **kwargs): pass
        self.assertEqual(generate_character_reference(Character()), "https://example.com/character.png")

    @patch.dict("os.environ", {"FAL_KEY": "test-key"})
    @patch("video_generator.character_generation.fal_client.subscribe", return_value={"images": []})
    def test_character_generation_rejects_missing_image(self, subscribe):
        class Character:
            consistency_prompt = "test"
        with self.assertRaises(CharacterGenerationError):
            generate_character_reference(Character())
