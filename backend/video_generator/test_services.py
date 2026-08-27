from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from .services import JSON2VideoService


class JSON2VideoServiceTests(SimpleTestCase):
    @patch.dict("os.environ", {"JSON2VIDEO_API_KEY": "test-key"})
    @patch("video_generator.services.requests.post")
    def test_create_movie_from_clips_builds_ordered_video_scenes(self, post):
        response = Mock()
        response.json.return_value = {"project": "assembly-123"}
        post.return_value = response

        service = JSON2VideoService()
        result = service.create_movie_from_clips(
            clips=[
                {"scene_number": 2, "video_url": "https://example.com/2.mp4"},
                {"scene_number": 1, "video_url": "https://example.com/1.mp4"},
            ],
            width=1080,
            height=1920,
            project_id=7,
        )

        self.assertEqual(result["project"], "assembly-123")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(payload["width"], 1080)
        self.assertEqual(payload["height"], 1920)
        self.assertEqual(payload["scenes"][0]["comment"], "Scene #2")
        self.assertEqual(payload["scenes"][1]["elements"][0]["src"], "https://example.com/1.mp4")
        self.assertEqual(payload["client-data"]["project_id"], 7)

    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key_fails_fast(self):
        with self.assertRaises(RuntimeError):
            JSON2VideoService()

    @patch.dict("os.environ", {"JSON2VIDEO_API_KEY": "test-key"})
    def test_empty_clip_list_is_rejected(self):
        service = JSON2VideoService()
        with self.assertRaises(RuntimeError):
            service.create_movie_from_clips(clips=[], width=1080, height=1920, project_id=7)
