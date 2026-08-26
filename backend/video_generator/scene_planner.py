import math


SUPPORTED_DURATIONS = (10, 30, 60)
SUPPORTED_ASPECT_RATIOS = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
}


def validate_generation_options(duration, aspect_ratio):
    duration = int(duration)
    if duration not in SUPPORTED_DURATIONS:
        raise ValueError("Duration must be 10, 30, or 60 seconds.")
    if aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
        raise ValueError("Aspect ratio must be 9:16, 16:9, or 1:1.")
    return duration, aspect_ratio


def get_dimensions(aspect_ratio):
    return SUPPORTED_ASPECT_RATIOS[aspect_ratio]


def build_scene_plan(prompt, duration):
    """Create deterministic scene slots until an AI scene planner is connected."""
    scene_count = max(1, math.ceil(duration / 6))
    base_duration, remainder = divmod(duration, scene_count)
    scenes = []

    for index in range(scene_count):
        scene_duration = base_duration + (1 if index < remainder else 0)
        scenes.append(
            {
                "scene_number": index + 1,
                "duration": scene_duration,
                "prompt": (
                    f"Scene {index + 1} of {scene_count}. Maintain the same recurring "
                    f"characters, appearance, clothing, environment style, and visual "
                    f"continuity throughout the story. Original story/script: {prompt}"
                ),
            }
        )

    return scenes
