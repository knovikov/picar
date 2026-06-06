import tempfile
import unittest
from pathlib import Path


class WebServerTests(unittest.TestCase):
    def test_status_payload_and_photo_listing_work_without_starting_server(self):
        from kidbot.core.status import SystemStatus
        from kidbot.core.web_server import build_status_payload, list_photo_files

        with tempfile.TemporaryDirectory() as tmpdir:
            photo_dir = Path(tmpdir)
            (photo_dir / "b.jpg").write_bytes(b"two")
            (photo_dir / "a.jpg").write_bytes(b"one")
            (photo_dir / "notes.txt").write_text("not a photo", encoding="utf-8")

            status = SystemStatus(
                robot_name="KidBot",
                version="0.1.0",
                wifi_connected=True,
                internet_connected=False,
                ip_address="192.168.1.50",
                controller_connected=True,
                latest_error=None,
                uptime_seconds=12.5,
            )

            payload = build_status_payload(status)
            photos = list_photo_files(photo_dir)

            self.assertEqual(payload["robot_name"], "KidBot")
            self.assertFalse(payload["internet_connected"])
            self.assertEqual([photo.name for photo in photos], ["a.jpg", "b.jpg"])

    def test_delete_photo_file_removes_only_safe_photo_name(self):
        from kidbot.core.web_server import delete_photo_file

        with tempfile.TemporaryDirectory() as tmpdir:
            photo_dir = Path(tmpdir)
            (photo_dir / "photo.jpg").write_bytes(b"photo")

            self.assertTrue(delete_photo_file(photo_dir, "photo.jpg"))
            self.assertFalse((photo_dir / "photo.jpg").exists())

            with self.assertRaises(ValueError):
                delete_photo_file(photo_dir, "../secret.jpg")

    def test_openai_panel_contains_check_key_button_and_limit_box(self):
        from kidbot.core.status import SystemStatus
        from kidbot.core.web_server import _render_index
        from kidbot.core.wifi_setup import AccessPointConfig

        status = {
            **{
                "robot_name": "KidBot",
                "version": "0.1.0",
                "wifi_connected": True,
                "internet_connected": True,
                "ip_address": "127.0.0.1",
                "controller_connected": False,
                "latest_error": None,
                "uptime_seconds": 1,
            }
        }

        html = _render_index(status, [], {"masked": "not set"}, AccessPointConfig())

        self.assertIn("Проверить ключ", html)
        self.assertIn("limitBox", html)
        self.assertIn("/api/openai-key/check", html)


if __name__ == "__main__":
    unittest.main()
