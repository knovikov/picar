import tempfile
import unittest
from pathlib import Path


class CameraTests(unittest.TestCase):
    def test_mock_camera_saves_timestamped_photo(self):
        from kidbot.core.camera import Camera

        with tempfile.TemporaryDirectory() as tmpdir:
            camera = Camera(photo_dir=Path(tmpdir), mock=True)

            photo_path = camera.capture_photo(prefix="test")

            self.assertTrue(photo_path.exists())
            self.assertTrue(photo_path.name.startswith("test_"))
            self.assertEqual(photo_path.suffix, ".jpg")
            self.assertGreater(photo_path.stat().st_size, 20)


if __name__ == "__main__":
    unittest.main()

