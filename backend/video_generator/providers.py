import os
from abc import ABC, abstractmethod


class VideoProviderError(RuntimeError):
    """Raised when an AI video provider cannot generate a scene."""


class VideoProvider(ABC):
    name = "base"

    @abstractmethod
    def generate_scene(self, *, prompt, duration, aspect_ratio, reference_image_url=None):
        raise NotImplementedError


class JSON2VideoProvider(VideoProvider):
    name = "json2video"

    def generate_scene(self, *, prompt, duration, aspect_ratio, reference_image_url=None):
        raise VideoProviderError(
            "JSON2Video is an assembly provider; an AI scene clip is required first."
        )


class FalPixVerseC1Provider(VideoProvider):
    """Reference-to-video adapter isolated from the application domain."""

    name = "fal_pixverse_c1"
    endpoint = "fal-ai/pixverse/c1/reference-to-video"

    def __init__(self):
        self.api_key = os.getenv("FAL_KEY")
        if not self.api_key:
            raise VideoProviderError("FAL_KEY is not configured.")

    def generate_scene(self, *, prompt, duration, aspect_ratio, reference_image_url=None):
        if not reference_image_url:
            raise VideoProviderError(
                "PixVerse C1 requires a reference_image_url for character-consistent scenes."
            )
        if duration < 1 or duration > 15:
            raise VideoProviderError("PixVerse C1 scene duration must be between 1 and 15 seconds.")
        if aspect_ratio not in {"9:16", "16:9", "1:1"}:
            raise VideoProviderError("Unsupported aspect ratio.")

        return {
            "provider": self.name,
            "model": self.endpoint,
            "prompt": prompt,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "reference_image_url": reference_image_url,
        }


def get_video_provider(name=None):
    provider_name = name or os.getenv("AI_VIDEO_PROVIDER", "json2video")
    providers = {
        "json2video": JSON2VideoProvider,
        "fal_pixverse_c1": FalPixVerseC1Provider,
    }
    try:
        return providers[provider_name]()
    except KeyError as exc:
        raise VideoProviderError(f"Unsupported AI video provider: {provider_name}") from exc
