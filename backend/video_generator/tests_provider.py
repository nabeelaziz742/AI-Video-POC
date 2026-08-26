import os
from unittest import mock

from django.test import SimpleTestCase

from .ai_providers import (
    FalPixVerseProvider,
    ProviderConfigurationError,
    get_ai_video_provider,
)


class ProviderConfigurationTests(SimpleTestCase):
    def test_default_provider_keeps_json2video_path(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_VIDEO_PROVIDER", None)
            self.assertIsNone(get_ai_video_provider())

    def test_unknown_provider_is_rejected(self):
        with mock.patch.dict(os.environ, {"AI_VIDEO_PROVIDER": "unknown"}):
            with self.assertRaises(ProviderConfigurationError):
                get_ai_video_provider()

    def test_fal_provider_requires_key(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FAL_KEY", None)
            with self.assertRaises(ProviderConfigurationError):
                FalPixVerseProvider()
