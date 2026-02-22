import unittest
from unittest.mock import patch

import core


class TestCore(unittest.TestCase):
    def test_extract_video_id_watch_url(self):
        self.assertEqual(core.extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"), "dQw4w9WgXcQ")

    def test_extract_video_id_short_url(self):
        self.assertEqual(core.extract_video_id("https://youtu.be/dQw4w9WgXcQ"), "dQw4w9WgXcQ")

    def test_extract_video_id_invalid_url(self):
        self.assertIsNone(core.extract_video_id("https://example.com/video"))

    @patch("core.YouTubeTranscriptApi")
    def test_try_get_captions_uses_direct_transcript(self, mock_api):
        mock_api.get_transcript.return_value = [{"text": "word " * 60}]
        result = core.try_get_captions("abc123xyz89")
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
