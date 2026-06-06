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


if __name__ == "__main__":
    unittest.main()
