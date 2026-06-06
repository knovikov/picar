import unittest

from kidbot.core.wifi_setup import WiFiActionResult


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class NetworkRecoveryTests(unittest.TestCase):
    def test_skip_when_setup_ap_is_disabled(self):
        from kidbot.core.network_recovery import ensure_setup_access_point

        starts = []

        result = ensure_setup_access_point(
            {"setup_ap": {"enabled": False}},
            is_wifi_connected_fn=lambda: False,
            start_access_point_fn=lambda *args, **kwargs: starts.append((args, kwargs)),
        )

        self.assertEqual(result.action, "disabled")
        self.assertFalse(starts)

    def test_skip_when_wifi_is_connected_before_timeout(self):
        from kidbot.core.network_recovery import ensure_setup_access_point

        clock = FakeClock()
        states = [False, False, True]
        starts = []

        result = ensure_setup_access_point(
            {"setup_ap": {"boot_check_wait_seconds": 10, "boot_check_poll_seconds": 3}},
            is_wifi_connected_fn=lambda: states.pop(0),
            start_access_point_fn=lambda *args, **kwargs: starts.append((args, kwargs)),
            sleeper=clock.sleep,
            monotonic=clock.monotonic,
        )

        self.assertEqual(result.action, "wifi-connected")
        self.assertEqual(clock.sleeps, [3, 3])
        self.assertFalse(starts)

    def test_start_setup_access_point_when_wifi_never_connects(self):
        from kidbot.core.network_recovery import ensure_setup_access_point

        starts = []

        def start_access_point(config, use_sudo=False):
            starts.append((config, use_sudo))
            return WiFiActionResult(True, "ap up")

        result = ensure_setup_access_point(
            {
                "setup_ap": {
                    "ssid": "Picar-Setup",
                    "password": "secret",
                    "interface": "wlan1",
                    "address": "192.168.50.1/24",
                    "boot_check_wait_seconds": 0,
                }
            },
            is_wifi_connected_fn=lambda: False,
            start_access_point_fn=start_access_point,
        )

        self.assertEqual(result.action, "started")
        self.assertTrue(result.success)
        self.assertEqual(starts[0][0].ssid, "Picar-Setup")
        self.assertEqual(starts[0][0].password, "secret")
        self.assertEqual(starts[0][0].interface, "wlan1")
        self.assertEqual(starts[0][0].address, "192.168.50.1/24")
        self.assertTrue(starts[0][1])


if __name__ == "__main__":
    unittest.main()
