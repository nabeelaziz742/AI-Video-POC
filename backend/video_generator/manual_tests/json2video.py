import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("JSON2VIDEO_API_KEY")
if not API_KEY: raise RuntimeError("JSON2VIDEO_API_KEY is missing from .env")
HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}
movie_payload = {"resolution": "full-hd", "scenes": [{"duration": 10, "elements": [{"type": "text", "text": "AI Video POC - JSON2Video Test", "style": "001"}]}]}
print("Submitting video render...")
response = requests.post("https://api.json2video.com/v2/movies", headers=HEADERS, json=movie_payload, timeout=60)
response.raise_for_status(); data = response.json(); print(data)
project_id = data.get("project")
if not project_id: raise RuntimeError(f"Project ID not found: {data}")
while True:
    response = requests.get("https://api.json2video.com/v2/movies", params={"project": project_id}, headers=HEADERS, timeout=60); response.raise_for_status(); movie = response.json()["movie"]; status = movie["status"]; print("Status:", status)
    if status == "done": print("VIDEO GENERATED SUCCESSFULLY!", movie["url"]); break
    if status == "error": raise RuntimeError(movie.get("message", "Video rendering failed"))
    time.sleep(3)
