import unittest


class SmoothingTests(unittest.TestCase):
    def test_deadzone_removes_tiny_stick_noise_and_rescales_rest(self):
        from kidbot.core.smoothing import apply_deadzone

        self.assertEqual(apply_deadzone(0.05, 0.1), 0.0)
        self.assertAlmostEqual(apply_deadzone(0.55, 0.1), 0.5, places=6)
        self.assertAlmostEqual(apply_deadzone(-0.55, 0.1), -0.5, places=6)

    def test_rate_limiter_moves_toward_target_without_jump(self):
        from kidbot.core.smoothing import RateLimiter

        limiter = RateLimiter(rate_per_second=10.0, initial_value=0.0)

        self.assertEqual(limiter.update(100.0, dt=0.5), 5.0)
        self.assertEqual(limiter.update(-100.0, dt=0.25), 2.5)


class DriveLogicTests(unittest.TestCase):
    def test_drive_command_turns_and_goes_forward_smoothly(self):
        from kidbot.kid_code.drive_logic import build_drive_command

        config = {
            "steering": {"deadzone": 0.1, "max_angle": 30, "curve": 1.0},
            "speed": {"deadzone": 0.1, "max_forward": 40, "max_reverse": 40},
        }

        command = build_drive_command(
            steering_axis=0.55,
            throttle_axis=-1.0,
            config=config,
        )

        self.assertAlmostEqual(command.steering_angle, 15.0, places=6)
        self.assertAlmostEqual(command.speed, 40.0, places=6)

    def test_emergency_stop_command_is_zero(self):
        from kidbot.kid_code.drive_logic import emergency_stop_command

        command = emergency_stop_command()

        self.assertEqual(command.speed, 0.0)
        self.assertEqual(command.steering_angle, 0.0)

    def test_front_sensor_stop_blocks_forward_but_allows_reverse(self):
        from kidbot.main import _safe_speed_for_front_sensor

        config = {"front_sensor": {"stop_distance_cm": 10}}

        self.assertEqual(_safe_speed_for_front_sensor(80.0, 9.5, config), 0.0)
        self.assertEqual(_safe_speed_for_front_sensor(-40.0, 9.5, config), -40.0)
        self.assertEqual(_safe_speed_for_front_sensor(80.0, 12.0, config), 80.0)


if __name__ == "__main__":
    unittest.main()
