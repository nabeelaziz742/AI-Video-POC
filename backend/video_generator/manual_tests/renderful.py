import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("RENDERFUL_API_KEY")
if not API_KEY: raise RuntimeError("RENDERFUL_API_KEY is missing from .env")
BASE_URL = "https://api.renderful.ai/api/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
payload = {"type": "text-to-video", "model": "seedance-1.5-pro", "prompt": "A cinematic 3D animated red sports car driving on a mountain road at sunrise. Vertical 9:16 composition. No text, logos or watermark.", "aspect_ratio": "9:16", "duration": 5, "resolution": "480P", "generate_audio": False}
print("Submitting AI video generation request...")
response = requests.post(f"{BASE_URL}/generations", headers=HEADERS, json=payload, timeout=60); response.raise_for_status(); generation_id = response.json()["id"]
while True:
    response = requests.get(f"{BASE_URL}/generations/{generation_id}", headers=HEADERS, timeout=60); response.raise_for_status(); result = response.json(); status = result.get("status"); print("Status:", status)
    if status == "completed": print("Video URL:", result.get("outputs", [None])[0]); break
    if status == "failed": raise RuntimeError(f"AI video generation failed: {result.get('error')}")
    time.sleep(5)
