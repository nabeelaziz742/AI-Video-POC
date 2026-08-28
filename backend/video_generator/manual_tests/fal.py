import os

import fal_client
from dotenv import load_dotenv


load_dotenv()

if not os.getenv("FAL_KEY"):
    raise RuntimeError("FAL_KEY is missing from .env")

prompt = """
Create a 5-second vertical 9:16 high-quality 3D animated video.

A kind farmer is standing beside his buffalo in a beautiful rural
village during the early morning. The farmer smiles and gently pats
the buffalo.

Keep the farmer and buffalo visually consistent throughout the clip.
Use cinematic camera movement, detailed 3D cartoon animation,
natural body movement, beautiful morning sunlight and realistic shadows.

No text, no subtitles, no logos and no watermark.
"""

print("Starting generation...")
result = fal_client.subscribe("fal-ai/ltx-2.3/text-to-video/fast", arguments={"prompt": prompt}, with_logs=True)
print("\nGeneration completed:")
print(result)
