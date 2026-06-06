import unittest


class WiFiSetupTests(unittest.TestCase):
    def test_parse_nmcli_wifi_list_keeps_signal_security_and_ssid(self):
        from kidbot.core.wifi_setup import parse_nmcli_wifi_list

        output = "\n".join(
            [
                "Home WiFi:82:WPA2",
                "Kid\\:Lab:51:WPA1 WPA2",
                ":0:",
            ]
        )

        networks = parse_nmcli_wifi_list(output)

        self.assertEqual(networks[0].ssid, "Home WiFi")
        self.assertEqual(networks[0].signal, 82)
        self.assertEqual(networks[0].security, "WPA2")
        self.assertEqual(networks[1].ssid, "Kid:Lab")

    def test_connect_to_wifi_uses_nmcli_with_password(self):
        from kidbot.core.wifi_setup import connect_to_wifi

        commands = []

        def runner(command, **kwargs):
            commands.append(command)
            return type("Result", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

        result = connect_to_wifi("Home WiFi", "secret-pass", runner=runner)

        self.assertTrue(result.success)
        self.assertEqual(
            commands[0],
            ["nmcli", "dev", "wifi", "connect", "Home WiFi", "password", "secret-pass"],
        )

    def test_scan_wifi_networks_returns_empty_list_when_nmcli_is_missing(self):
        from kidbot.core.wifi_setup import scan_wifi_networks

        def runner(command, **kwargs):
            raise FileNotFoundError("nmcli")

        self.assertEqual(scan_wifi_networks(runner=runner), [])

    def test_access_point_command_uses_shared_ipv4_address(self):
        from kidbot.core.wifi_setup import AccessPointConfig, build_access_point_commands

        commands = build_access_point_commands(
            AccessPointConfig(
                ssid="KidBot-Setup",
                password="kidbot1234",
                interface="wlan0",
                address="192.168.4.1/24",
            )
        )

        flat = [" ".join(command) for command in commands]
        self.assertTrue(any("802-11-wireless.mode ap" in command for command in flat))
        self.assertTrue(any("ipv4.addresses 192.168.4.1/24" in command for command in flat))
        self.assertEqual(commands[-1], ["nmcli", "connection", "up", "KidBot-Setup"])


if __name__ == "__main__":
    unittest.main()
