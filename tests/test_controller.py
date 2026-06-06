import unittest


class ButtonTrackerTests(unittest.TestCase):
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
