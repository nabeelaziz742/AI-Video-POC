import os
from abc import ABC, abstractmethod

import fal_client


class VideoProviderError(RuntimeError):
    """Raised when an AI video provider cannot generate a scene."""


class VideoProvider(ABC):
    name = "base"

    @abstractmethod
    def generate_scene(self, *, prompt, duration, aspect_ratio, reference_image_url=None):
        raise NotImplementedError

    @abstractmethod
    def submit_scene(self, *, prompt, duration, aspect_ratio, reference_image_url=None):
        raise NotImplementedError

    @abstractmethod
    def get_scene_result(self, request_id):
        raise NotImplementedError


class JSON2VideoProvider(VideoProvider):
    name = "json2video"

    def generate_scene(self, *, prompt, duration, aspect_ratio, reference_image_url=None):
        raise VideoProviderError(
            "JSON2Video is an assembly provider; an AI scene clip is required first."
        )

    def submit_scene(self, **kwargs):
        raise VideoProviderError(
            "JSON2Video is an assembly provider; use it after AI scene clips are generated."
        )

    def get_scene_result(self, request_id):
        raise VideoProviderError("JSON2Video does not manage AI scene jobs.")


class FalPixVerseC1Provider(VideoProvider):
    """Reference-to-video adapter using fal.ai PixVerse C1."""

    name = "fal_pixverse_c1"
    endpoint = "fal-ai/pixverse/c1/reference-to-video"

    def __init__(self):
        if not os.getenv("FAL_KEY"):
            raise VideoProviderError("FAL_KEY is not configured.")

    @staticmethod
    def _validate(duration, aspect_ratio, reference_image_url):
        if not reference_image_url:
            raise VideoProviderError(
                "PixVerse C1 requires a reference_image_url for character-consistent scenes."
            )
        if duration < 1 or duration > 15:
            raise VideoProviderError("PixVerse C1 scene duration must be between 1 and 15 seconds.")
        if aspect_ratio not in {"9:16", "16:9", "1:1"}:
            raise VideoProviderError("Unsupported aspect ratio.")

    def _arguments(self, *, prompt, duration, aspect_ratio, reference_image_url):
        self._validate(duration, aspect_ratio, reference_image_url)
        return {
            "prompt": prompt[:2048],
            "aspect_ratio": aspect_ratio,
            "resolution": os.getenv("FAL_VIDEO_RESOLUTION", "720p"),
            "duration": duration,
            "generate_audio_switch": False,
            "image_references": [
                {
                    "image_url": reference_image_url,
                    "type": "subject",
                    "ref_name": "character",
                }
            ],
        }

    def generate_scene(self, *, prompt, duration, aspect_ratio, reference_image_url=None):
        result = fal_client.subscribe(
            self.endpoint,
            arguments=self._arguments(
                prompt=prompt,
                duration=duration,
                aspect_ratio=aspect_ratio,
                reference_image_url=reference_image_url,
            ),
        )
        video = result.get("video") if isinstance(result, dict) else None
        if not video or not video.get("url"):
            raise VideoProviderError(f"PixVerse returned no video: {result}")
        return {"request_id": None, "video_url": video["url"], "raw": result}

    def submit_scene(self, *, prompt, duration, aspect_ratio, reference_image_url=None):
        handle = fal_client.submit(
            self.endpoint,
            arguments=self._arguments(
                prompt=prompt,
                duration=duration,
                aspect_ratio=aspect_ratio,
                reference_image_url=reference_image_url,
            ),
        )
        return {"request_id": handle.request_id, "provider": self.name}

    def get_scene_result(self, request_id):
        status = fal_client.status(self.endpoint, request_id, with_logs=False)
        if isinstance(status, fal_client.Completed):
            result = fal_client.result(self.endpoint, request_id)
            video = result.get("video") if isinstance(result, dict) else None
            if not video or not video.get("url"):
                raise VideoProviderError(f"PixVerse completed without a video: {result}")
            return {"status": "completed", "video_url": video["url"], "raw": result}
        if isinstance(status, fal_client.Queued):
            return {"status": "queued"}
        if isinstance(status, fal_client.InProgress):
            return {"status": "processing"}
        return {"status": "processing"}


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
