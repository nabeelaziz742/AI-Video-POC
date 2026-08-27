from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from .services import JSON2VideoService


class JSON2VideoAssemblyTests(SimpleTestCase):
    @patch.dict("os.environ", {"JSON2VIDEO_API_KEY": "test-key"})
    @patch("video_generator.services.requests.get")
    def test_get_movie_returns_provider_response(self, get):
        response = Mock()
        response.json.return_value = {"movie": {"status": "done", "url": "https://example.com/final.mp4"}}
        get.return_value = response

        result = JSON2VideoService().get_movie("assembly-123")

        self.assertEqual(result["movie"]["status"], "done")
        get.assert_called_once()
        self.assertEqual(get.call_args.kwargs["params"], {"project": "assembly-123"})

    @patch.dict("os.environ", {"JSON2VIDEO_API_KEY": "test-key"})
    @patch("video_generator.services.requests.get")
    def test_get_movie_uses_api_key_header(self, get):
        response = Mock()
        response.json.return_value = {"movie": {"status": "running"}}
        get.return_value = response

        JSON2VideoService().get_movie("assembly-456")

        self.assertEqual(get.call_args.kwargs["headers"]["x-api-key"], "test-key")
