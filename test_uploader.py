import unittest

from uploader import build_video_metadata, _youtube_tags_total_length


class BuildVideoMetadataTests(unittest.TestCase):
    def test_tags_respect_youtube_effective_length_limit(self):
        metadata = build_video_metadata(
            {
                "date": "2026-05-24",
                "answer": "Things shaped like discs/disks (i.e, flat and circular)",
                "clues": [
                    "Plates",
                    "Coins",
                    "Frisbees",
                    "Manhole covers",
                    "CDs and DVDs (it's the last D)",
                ],
                "puzzleNumber": 754,
            }
        )

        self.assertLessEqual(_youtube_tags_total_length(metadata["tags"]), 500)
        self.assertEqual(len(metadata["tags"]), len(set(metadata["tags"])))


if __name__ == "__main__":
    unittest.main()
