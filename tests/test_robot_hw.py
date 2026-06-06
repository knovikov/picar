import unittest
from types import SimpleNamespace
from unittest import mock


class RobotHardwareTests(unittest.TestCase):
    def test_front_distance_reader_uses_picarx_get_distance(self):
        from kidbot.core.robot_hw import RobotHardware

        class FakePicar:
            def get_distance(self):
                return 42.345

        robot = RobotHardware(config={}, mock=True)
        robot.mock = False
        robot._picar = FakePicar()

        self.assertEqual(robot.read_front_distance_cm(), 42.35)

    def test_front_distance_reader_returns_none_on_sensor_error(self):
        from kidbot.core.robot_hw import RobotHardware

        class BrokenPicar:
            def get_distance(self):
                raise RuntimeError("sensor not ready")

        robot = RobotHardware(config={}, mock=True)
        robot.mock = False
        robot._picar = BrokenPicar()

        self.assertIsNone(robot.read_front_distance_cm())

    def test_battery_reader_builds_percentage_from_voltage(self):
        from kidbot.core.robot_hw import RobotHardware

        class FakePicar:
            def get_battery_voltage(self):
                return 7.4

        robot = RobotHardware(config={"battery": {"empty_voltage": 6.4, "full_voltage": 8.4}}, mock=True)
        robot.mock = False
        robot._picar = FakePicar()

        battery = robot.read_battery()

        self.assertEqual(battery["voltage"], 7.4)
        self.assertEqual(battery["percentage"], 50.0)
        self.assertEqual(battery["status"], "ok")

    def test_battery_reader_accepts_millivolts_and_marks_low(self):
        from kidbot.core.robot_hw import RobotHardware

        class FakePicar:
            def power_read(self):
                return 6700

        robot = RobotHardware(
            config={"battery": {"empty_voltage": 6.4, "full_voltage": 8.4, "low_voltage": 6.8}},
            mock=True,
        )
        robot.mock = False
        robot._picar = FakePicar()

        battery = robot.read_battery()

        self.assertEqual(battery["voltage"], 6.7)
        self.assertEqual(battery["status"], "low")

    def test_battery_reader_uses_robot_hat_device_fallback(self):
        from kidbot.core import robot_hw
        from kidbot.core.robot_hw import RobotHardware

        fake_device = SimpleNamespace(get_battery_voltage=lambda: 7.82)

        robot = RobotHardware(config={"battery": {"empty_voltage": 6.4, "full_voltage": 8.4}}, mock=True)
        robot.mock = False
        robot._picar = object()

        with mock.patch.object(robot_hw.importlib, "import_module", return_value=fake_device):
            battery = robot.read_battery()

        self.assertEqual(battery["voltage"], 7.82)
        self.assertEqual(battery["percentage"], 71.0)
        self.assertEqual(battery["source"], "hardware")

    def test_battery_reader_uses_robot_hat_a4_when_device_helper_is_broken(self):
        from kidbot.core import robot_hw
        from kidbot.core.robot_hw import RobotHardware

        class FakeAdc:
            def __init__(self, channel):
                self.channel = channel

            def read_voltage(self):
                return 2.5

        def fake_import_module(name):
            if name in ("robot_hat.device", "robot_hat.utils"):
                raise NameError("name '_adc_obj' is not defined")
            return SimpleNamespace(ADC=FakeAdc)

        robot = RobotHardware(config={"battery": {"empty_voltage": 6.4, "full_voltage": 8.4}}, mock=True)
        robot.mock = False
        robot._picar = object()

        with mock.patch.object(robot_hw.importlib, "import_module", side_effect=fake_import_module):
            battery = robot.read_battery()

        self.assertEqual(battery["voltage"], 7.5)
        self.assertEqual(battery["percentage"], 55.0)
        self.assertEqual(battery["source"], "hardware")

    def test_picarx_getlogin_falls_back_under_systemd(self):
        from kidbot.core import robot_hw

        created_with_users = []

        class FakePicar:
            def __init__(self):
                created_with_users.append(robot_hw.os.getlogin())

        with mock.patch.object(robot_hw.os, "getlogin", side_effect=OSError(-25, "no tty")):
            with mock.patch.dict(robot_hw.os.environ, {"USER": "pi"}, clear=True):
                picar = robot_hw._build_picarx(FakePicar)

        self.assertIsInstance(picar, FakePicar)
        self.assertEqual(created_with_users, ["pi"])


if __name__ == "__main__":
    unittest.main()
