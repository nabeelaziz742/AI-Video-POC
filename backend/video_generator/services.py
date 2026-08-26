import os

import requests


class JSON2VideoService:
    BASE_URL = "https://api.json2video.com/v2"

    def __init__(self):
        self.api_key = os.getenv("JSON2VIDEO_API_KEY")
        if not self.api_key:
            raise RuntimeError("JSON2VIDEO_API_KEY is not configured.")
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def create_movie(self, movie_payload):
        response = requests.post(
            f"{self.BASE_URL}/movies",
            headers=self.headers,
            json=movie_payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()

    def create_movie_from_clips(self, *, clips, width, height, project_id):
        if not clips:
            raise RuntimeError("At least one generated scene clip is required.")

        payload = {
            "width": width,
            "height": height,
            "scenes": [
                {
                    "comment": f"Scene #{clip['scene_number']}",
                    "elements": [
                        {
                            "type": "video",
                            "src": clip["video_url"],
                        }
                    ],
                }
                for clip in clips
            ],
            "client-data": {"project_id": project_id, "assembly": "ai-scene-clips"},
        }
        return self.create_movie(payload)

    def get_movie(self, project_id):
        response = requests.get(
            f"{self.BASE_URL}/movies",
            params={"project": project_id},
            headers=self.headers,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
