import unittest


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


if __name__ == "__main__":
    unittest.main()
