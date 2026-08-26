import os
from dataclasses import dataclass


class ProviderConfigurationError(RuntimeError):
    """Raised when an AI video provider is not configured."""


class ProviderGenerationError(RuntimeError):
    """Raised when an AI video provider cannot generate a clip."""


@dataclass(frozen=True)
class GeneratedClip:
    provider: str
    video_url: str
    provider_request_id: str | None = None


class FalPixVerseProvider:
    """Character/reference-to-video adapter for PixVerse C1 on fal.ai.

    This adapter deliberately stays isolated from Django views so the provider
    can be replaced without changing the project's scene/database architecture.
    """

    name = "fal_pixverse_c1"
    model = "fal-ai/pixverse/c1/reference-to-video"

    def __init__(self):
        if not os.getenv("FAL_KEY"):
            raise ProviderConfigurationError("FAL_KEY is not configured.")

    @staticmethod
    def _result_url(result):
        video = result.get("video") if isinstance(result, dict) else None
        if isinstance(video, dict) and video.get("url"):
            return video["url"]
        if isinstance(video, str) and video:
            return video
        raise ProviderGenerationError("AI provider returned no video URL.")

    def generate_scene(self, *, prompt, reference_images, duration, aspect_ratio):
        if not reference_images:
            raise ProviderGenerationError(
                "At least one character reference image is required for character-consistent generation."
            )
        if not 1 <= int(duration) <= 15:
            raise ProviderGenerationError("PixVerse scene duration must be between 1 and 15 seconds.")

        import fal_client

        image_references = []
        for index, image_url in enumerate(reference_images, start=1):
            image_references.append(
                {
                    "image_url": image_url,
                    "type": "subject",
                    "ref_name": f"character{index}",
                }
            )

        result = fal_client.subscribe(
            self.model,
            arguments={
                "prompt": prompt,
                "image_references": image_references,
                "aspect_ratio": aspect_ratio,
                "resolution": "720p",
                "duration": int(duration),
                "style": "3d_animation",
            },
            with_logs=False,
        )

        return GeneratedClip(
            provider=self.name,
            video_url=self._result_url(result),
            provider_request_id=result.get("request_id") if isinstance(result, dict) else None,
        )


def get_ai_video_provider(name=None):
    provider_name = name or os.getenv("AI_VIDEO_PROVIDER", "json2video")
    if provider_name == "fal_pixverse_c1":
        return FalPixVerseProvider()
    if provider_name == "json2video":
        return None
    raise ProviderConfigurationError(f"Unsupported AI_VIDEO_PROVIDER: {provider_name}")
