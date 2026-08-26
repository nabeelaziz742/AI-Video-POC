import os
import time

import requests
from dotenv import load_dotenv


load_dotenv()

API_KEY = os.getenv("RENDERFUL_API_KEY")

if not API_KEY:
    raise RuntimeError("RENDERFUL_API_KEY is missing from .env")


BASE_URL = "https://api.renderful.ai/api/v1"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}


prompt = """
A cinematic 3D animated video of a red sports car driving on a
beautiful mountain road during sunrise.

The camera smoothly follows the car from behind.
Warm golden sunlight, detailed environment, realistic shadows,
smooth motion, high-quality 3D animation.

Vertical 9:16 composition.
No people, no children, no text, no subtitles, no logos.
"""


payload = {
    "type": "text-to-video",
    "model": "seedance-1.5-pro",
    "prompt": prompt,
    "aspect_ratio": "9:16",
    "duration": 5,
    "resolution": "480P",
    "generate_audio": False,
}

print("Submitting AI video generation request...")

response = requests.post(
    f"{BASE_URL}/generations",
    headers=HEADERS,
    json=payload,
    timeout=60,
)

print("HTTP Status:", response.status_code)

data = response.json()

print("Response:")
print(data)

if not response.ok:
    raise RuntimeError(data)


generation_id = data["id"]

print("\nGeneration ID:", generation_id)
print("Waiting for AI video...")


while True:

    response = requests.get(
        f"{BASE_URL}/generations/{generation_id}",
        headers=HEADERS,
        timeout=60,
    )

    response.raise_for_status()

    result = response.json()

    status = result.get("status")

    print("Status:", status)

    if status == "completed":

        outputs = result.get("outputs", [])

        if not outputs:
            raise RuntimeError(
                f"Generation completed but no output found: {result}"
            )

        print("\n================================")
        print("AI VIDEO GENERATED SUCCESSFULLY")
        print("================================")

        print("Video URL:")
        print(outputs[0])

        break

    if status == "failed":

        raise RuntimeError(
            f"AI video generation failed: "
            f"{result.get('error')}"
        )

    time.sleep(5)