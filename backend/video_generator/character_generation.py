import os

import fal_client

from .models import Character


class CharacterGenerationError(RuntimeError):
    pass


def build_character_reference_prompt(character: Character) -> str:
    description = character.consistency_prompt
    return (
        "Create a clean 3D animated character reference sheet for a recurring story character. "
        "Show the full character clearly, centered, with a simple neutral background. "
        "Use a polished family-friendly 3D cartoon film aesthetic. Keep the face, body proportions, "
        "hair, clothing, colors, accessories and distinctive features extremely clear and consistent. "
        "No text, no watermark, no extra characters. Character specification: "
        f"{description}"
    )[:2048]


def generate_character_reference(character: Character) -> str:
    if not os.getenv("FAL_KEY"):
        raise CharacterGenerationError("FAL_KEY is not configured.")

    result = fal_client.subscribe(
        os.getenv("FAL_IMAGE_MODEL", "fal-ai/flux/schnell"),
        arguments={
            "prompt": build_character_reference_prompt(character),
            "image_size": "portrait_4_3",
            "num_images": 1,
            "output_format": "png",
            "enable_safety_checker": True,
        },
    )

    images = result.get("images", []) if isinstance(result, dict) else []
    if not images or not images[0].get("url"):
        raise CharacterGenerationError(f"Character reference generation returned no image: {result}")

    character.reference_image_url = images[0]["url"]
    character.save(update_fields=["reference_image_url"])
    return character.reference_image_url
