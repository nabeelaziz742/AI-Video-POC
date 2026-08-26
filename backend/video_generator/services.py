import os

import requests


class JSON2VideoService:
    BASE_URL = "https://api.json2video.com/v2"

    def __init__(self):
        self.api_key = os.getenv("JSON2VIDEO_API_KEY")

        if not self.api_key:
            raise RuntimeError(
                "JSON2VIDEO_API_KEY is not configured."
            )

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

    def get_movie(self, project_id):
        response = requests.get(
            f"{self.BASE_URL}/movies",
            params={"project": project_id},
            headers=self.headers,
            timeout=60,
        )

        response.raise_for_status()

        return response.json()