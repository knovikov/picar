import tempfile
import unittest
from pathlib import Path


class WebServerTests(unittest.TestCase):
    def test_status_payload_and_photo_listing_work_without_starting_server(self):
        from kidbot.core.status import BatteryStatus, SystemStatus
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
                battery=BatteryStatus(percentage=72.0, voltage=7.84, status="ok", source="test", updated_at=123.0),
            )

            payload = build_status_payload(status)
            photos = list_photo_files(photo_dir)

            self.assertEqual(payload["robot_name"], "KidBot")
            self.assertFalse(payload["internet_connected"])
            self.assertEqual(payload["battery"]["percentage"], 72.0)
            self.assertEqual(payload["battery"]["voltage"], 7.84)
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

    def test_index_contains_battery_indicator(self):
        from kidbot.core.web_server import _render_index
        from kidbot.core.wifi_setup import AccessPointConfig

        status = {
            "robot_name": "KidBot",
            "version": "0.1.0",
            "wifi_connected": True,
            "internet_connected": True,
            "ip_address": "127.0.0.1",
            "controller_connected": False,
            "battery": {"percentage": 42, "voltage": 7.24, "status": "low"},
            "latest_error": None,
            "uptime_seconds": 1,
        }

        html = _render_index(status, [], {"masked": "not set"}, AccessPointConfig())

        self.assertIn("Батарея", html)
        self.assertIn("battery-meter", html)
        self.assertIn("42%", html)
        self.assertIn("7.24 V", html)

    def test_index_contains_bluetooth_controller_setup(self):
        from kidbot.core.web_server import _render_index
        from kidbot.core.wifi_setup import AccessPointConfig

        status = {
            "robot_name": "KidBot",
            "version": "0.1.0",
            "wifi_connected": True,
            "internet_connected": True,
            "ip_address": "127.0.0.1",
            "controller_connected": False,
            "latest_error": None,
            "uptime_seconds": 1,
        }

        html = _render_index(status, [], {"masked": "not set"}, AccessPointConfig())

        self.assertIn("Пульт", html)
        self.assertIn("Найти Bluetooth", html)
        self.assertIn("bluetoothDevice", html)
        self.assertIn("/api/bluetooth/scan", html)

    def test_index_contains_web_photo_capture(self):
        from kidbot.core.web_server import _render_index
        from kidbot.core.wifi_setup import AccessPointConfig

        status = {
            "robot_name": "KidBot",
            "version": "0.1.0",
            "wifi_connected": True,
            "internet_connected": True,
            "ip_address": "127.0.0.1",
            "controller_connected": False,
            "latest_error": None,
            "uptime_seconds": 1,
        }

        html = _render_index(status, [], {"masked": "not set"}, AccessPointConfig())

        self.assertIn("Сделать фото", html)
        self.assertIn("/api/photos/capture", html)
        self.assertIn("Все фото", html)

    def test_index_contains_soundboard(self):
        from kidbot.core.web_server import _render_index
        from kidbot.core.wifi_setup import AccessPointConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            sounds_dir = Path(tmpdir)
            engine = sounds_dir / "engine_rev.wav"
            fart = sounds_dir / "fart_1.wav"
            engine.write_bytes(b"engine")
            fart.write_bytes(b"fart")
            status = {
                "robot_name": "KidBot",
                "version": "0.1.0",
                "wifi_connected": True,
                "internet_connected": True,
                "ip_address": "127.0.0.1",
                "controller_connected": False,
                "latest_error": None,
                "uptime_seconds": 1,
            }

            html = _render_index(status, [], {"masked": "not set"}, AccessPointConfig(), [engine, fart])

        self.assertIn("Звуки", html)
        self.assertIn("Рев мотора", html)
        self.assertIn("Пук 1", html)
        self.assertIn("/api/sounds/", html)

    def test_index_header_uses_picar_brand_name(self):
        from kidbot.core.web_server import _render_index
        from kidbot.core.wifi_setup import AccessPointConfig

        status = {
            "robot_name": "KidBot",
            "version": "0.1.0",
            "wifi_connected": True,
            "internet_connected": True,
            "ip_address": "127.0.0.1",
            "controller_connected": False,
            "latest_error": None,
            "uptime_seconds": 1,
        }

        html = _render_index(status, [], {"masked": "not set"}, AccessPointConfig())

        self.assertIn("<h1>Picar</h1>", html)
        self.assertNotIn("<h1>KidBot</h1>", html)

    def test_index_contains_manual_update_panel_and_debug_link(self):
        from kidbot.core.web_server import _render_index
        from kidbot.core.wifi_setup import AccessPointConfig

        status = {
            "robot_name": "KidBot",
            "version": "0.1.0",
            "wifi_connected": True,
            "internet_connected": True,
            "ip_address": "127.0.0.1",
            "controller_connected": False,
            "latest_error": None,
            "uptime_seconds": 1,
        }

        html = _render_index(status, [], {"masked": "not set"}, AccessPointConfig())

        self.assertIn("Обновления", html)
        self.assertIn("/api/update/check", html)
        self.assertIn("/api/update/apply", html)
        self.assertIn("/api/update/rollback", html)
        self.assertIn('href="/debug"', html)

    def test_debug_page_contains_websocket_and_live_widgets(self):
        from kidbot.core.web_server import _render_debug_page

        html = _render_debug_page()

        self.assertIn("/ws/debug", html)
        self.assertIn("controllerGrid", html)
        self.assertIn("frontSensorDistance", html)
        self.assertIn("renderFrontSensor", html)
        self.assertIn("batteryCard", html)
        self.assertIn("renderBattery", html)
        self.assertIn("logConsole", html)
        self.assertIn("waveCanvas", html)

    def test_debug_page_draws_8bitdo_lite2_controller_layout(self):
        from kidbot.core.web_server import _render_debug_page

        html = _render_debug_page()

        self.assertIn("controllerFrame", html)
        self.assertIn("controllerShell", html)
        self.assertIn("systemRow", html)
        self.assertIn("leftStick", html)
        self.assertIn("rightStick", html)
        self.assertIn("faceCluster", html)
        self.assertIn("faceDiamond", html)
        self.assertIn("dpadCluster", html)
        self.assertNotIn("mode-dots", html)
        for button_id in (
            "btn-a",
            "btn-b",
            "btn-x",
            "btn-y",
            "btn-l",
            "btn-r",
            "btn-l2",
            "btn-r2",
            "btn-select",
            "btn-start",
            "btn-star",
            "btn-home",
            "btn-l3",
            "btn-r3",
            "btn-dpad-up",
            "btn-dpad-right",
            "btn-dpad-down",
            "btn-dpad-left",
        ):
            self.assertIn(button_id, html)

    def test_debug_page_contains_responsive_layout_guards(self):
        from kidbot.core.web_server import _render_debug_page

        html = _render_debug_page()

        self.assertIn(".grid > section { min-width: 0; }", html)
        self.assertIn("@media (max-width: 640px)", html)
        self.assertIn(".stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }", html)

    def test_debug_websocket_sends_snapshot(self):
        from fastapi.testclient import TestClient

        from kidbot.core.status import SystemStatus
        from kidbot.core.web_server import create_app

        with tempfile.TemporaryDirectory() as tmpdir:
            photo_dir = Path(tmpdir)

            def status_provider():
                return SystemStatus(
                    robot_name="KidBot",
                    version="0.1.0",
                    wifi_connected=True,
                    internet_connected=True,
                    ip_address="127.0.0.1",
                    controller_connected=False,
                    latest_error=None,
                    uptime_seconds=1,
                )

            app = create_app(photo_dir, status_provider, repo_dir=Path(tmpdir))
            client = TestClient(app)

            with client.websocket_connect("/ws/debug") as websocket:
                payload = websocket.receive_json()

        self.assertIn("controller", payload)
        self.assertIn("status", payload)

    def test_sound_api_lists_and_plays_safe_audio_files(self):
        from fastapi.testclient import TestClient

        from kidbot.core.status import SystemStatus
        from kidbot.core.web_server import create_app

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo_dir = root / "photos"
            sounds_dir = root / "sounds"
            photo_dir.mkdir()
            sounds_dir.mkdir()
            (sounds_dir / "engine_rev.wav").write_bytes(b"not really wav")
            played = []

            def status_provider():
                return SystemStatus(
                    robot_name="KidBot",
                    version="0.1.0",
                    wifi_connected=True,
                    internet_connected=True,
                    ip_address="127.0.0.1",
                    controller_connected=False,
                    latest_error=None,
                    uptime_seconds=1,
                )

            app = create_app(
                photo_dir,
                status_provider,
                repo_dir=root,
                sounds_dir=sounds_dir,
                sound_player=lambda path: played.append(path.name),
            )
            client = TestClient(app)

            sounds = client.get("/api/sounds").json()
            response = client.post("/api/sounds/engine_rev.wav/play")

        self.assertEqual(sounds[0]["name"], "engine_rev.wav")
        self.assertEqual(sounds[0]["label"], "Рев мотора")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(played, ["engine_rev.wav"])

    def test_photo_capture_api_uses_callback_and_lists_newest_first(self):
        from fastapi.testclient import TestClient

        from kidbot.core.status import SystemStatus
        from kidbot.core.web_server import create_app

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            photo_dir = root / "photos"
            photo_dir.mkdir()
            older = photo_dir / "photo_older.jpg"
            newer = photo_dir / "photo_newer.jpg"
            older.write_bytes(b"old")

            def status_provider():
                return SystemStatus(
                    robot_name="KidBot",
                    version="0.1.0",
                    wifi_connected=True,
                    internet_connected=True,
                    ip_address="127.0.0.1",
                    controller_connected=False,
                    latest_error=None,
                    uptime_seconds=1,
                )

            def capture_photo():
                newer.write_bytes(b"new")
                return newer

            app = create_app(photo_dir, status_provider, repo_dir=root, capture_photo=capture_photo)
            client = TestClient(app)

            capture_response = client.post("/api/photos/capture")
            photos = client.get("/api/photos").json()

        self.assertEqual(capture_response.status_code, 200)
        self.assertEqual(capture_response.json()["photo"]["name"], "photo_newer.jpg")
        self.assertEqual([photo["name"] for photo in photos], ["photo_newer.jpg", "photo_older.jpg"])


if __name__ == "__main__":
    unittest.main()
