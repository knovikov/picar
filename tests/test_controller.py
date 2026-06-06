import unittest
import sys
from types import SimpleNamespace
from unittest import mock


class ButtonTrackerTests(unittest.TestCase):
    def test_controller_connect_refreshes_joystick_subsystem(self):
        from kidbot.core.controller import ControllerReader

        calls = []

        class FakeJoystickModule:
            def quit(self):
                calls.append("joystick.quit")

            def init(self):
                calls.append("joystick.init")

            def get_count(self):
                return 0

        fake_pygame = SimpleNamespace(
            init=lambda: calls.append("pygame.init"),
            joystick=FakeJoystickModule(),
        )

        with mock.patch.dict(sys.modules, {"pygame": fake_pygame}):
            reader = ControllerReader()
            self.assertFalse(reader.connect())

        self.assertEqual(calls, ["pygame.init", "joystick.quit", "joystick.init", "joystick.quit"])

    def test_controller_poll_resets_after_read_error(self):
        from kidbot.core.controller import ControllerReader

        class BrokenJoystick:
            def get_numaxes(self):
                return 1

            def get_axis(self, index):
                raise RuntimeError("gone")

        reader = ControllerReader()
        reader._pygame = SimpleNamespace(event=SimpleNamespace(pump=lambda: None))
        reader._joystick = BrokenJoystick()

        state = reader.poll()

        self.assertFalse(state.connected)
        self.assertIsNone(reader._joystick)

    def test_combo_long_pressed_fires_once_after_hold(self):
        from kidbot.core.controller import ButtonTracker

        tracker = ButtonTracker()

        self.assertFalse(
            tracker.combo_long_pressed(
                "rollback",
                {"select": True, "start": True},
                ("select", "start"),
                now=10.0,
                hold_seconds=2.0,
            )
        )
        self.assertFalse(
            tracker.combo_long_pressed(
                "rollback",
                {"select": True, "start": True},
                ("select", "start"),
                now=11.0,
                hold_seconds=2.0,
            )
        )
        self.assertTrue(
            tracker.combo_long_pressed(
                "rollback",
                {"select": True, "start": True},
                ("select", "start"),
                now=12.1,
                hold_seconds=2.0,
            )
        )
        self.assertFalse(
            tracker.combo_long_pressed(
                "rollback",
                {"select": True, "start": True},
                ("select", "start"),
                now=13.0,
                hold_seconds=2.0,
            )
        )

        tracker.combo_long_pressed("rollback", {"select": False, "start": False}, ("select", "start"), now=14.0)
        self.assertFalse(
            tracker.combo_long_pressed(
                "rollback",
                {"select": True, "start": True},
                ("select", "start"),
                now=15.0,
                hold_seconds=2.0,
            )
        )


if __name__ == "__main__":
    unittest.main()
