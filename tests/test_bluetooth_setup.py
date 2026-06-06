import unittest


class BluetoothSetupTests(unittest.TestCase):
    def test_parse_bluetooth_devices_keeps_address_name_and_flags(self):
        from kidbot.core.bluetooth_setup import parse_bluetooth_devices

        output = "\n".join(
            [
                "Device AA:BB:CC:DD:EE:FF 8BitDo Lite 2",
                "Device 11:22:33:44:55:66 Wireless Controller",
                "not a device line",
            ]
        )

        devices = parse_bluetooth_devices(output)

        self.assertEqual(devices[0].address, "AA:BB:CC:DD:EE:FF")
        self.assertEqual(devices[0].name, "8BitDo Lite 2")
        self.assertFalse(devices[0].connected)
        self.assertEqual(devices[1].name, "Wireless Controller")

    def test_connect_bluetooth_device_pairs_trusts_and_connects(self):
        from kidbot.core.bluetooth_setup import connect_bluetooth_device

        commands = []

        def runner(command, **kwargs):
            commands.append(command)
            return type("Result", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

        result = connect_bluetooth_device("AA:BB:CC:DD:EE:FF", runner=runner)

        self.assertTrue(result.success)
        self.assertIn(["bluetoothctl", "pair", "AA:BB:CC:DD:EE:FF"], commands)
        self.assertIn(["bluetoothctl", "trust", "AA:BB:CC:DD:EE:FF"], commands)
        self.assertEqual(commands[-1], ["bluetoothctl", "connect", "AA:BB:CC:DD:EE:FF"])

    def test_connect_bluetooth_device_rejects_bad_address(self):
        from kidbot.core.bluetooth_setup import connect_bluetooth_device

        commands = []

        def runner(command, **kwargs):
            commands.append(command)
            return type("Result", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

        result = connect_bluetooth_device("not-a-mac", runner=runner)

        self.assertFalse(result.success)
        self.assertEqual(commands, [])

    def test_scan_bluetooth_devices_returns_empty_list_when_tool_is_missing(self):
        from kidbot.core.bluetooth_setup import scan_bluetooth_devices

        def runner(command, **kwargs):
            raise FileNotFoundError("bluetoothctl")

        self.assertEqual(scan_bluetooth_devices(runner=runner), [])


if __name__ == "__main__":
    unittest.main()
