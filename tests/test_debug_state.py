import logging
import unittest


class DebugStateTests(unittest.TestCase):
    def test_debug_state_records_controller_buttons_events_and_logs(self):
        from kidbot.core.controller import JoystickState
        from kidbot.core.debug_state import DebugStateStore

        store = DebugStateStore()
        state = JoystickState(
            connected=True,
            name="8BitDo Lite 2",
            axes={0: 0.5, 3: -1.0},
            buttons={0: True, 1: False},
            hats={0: (1, 0)},
        )

        store.record_controller(state, {"a": True, "b": False}, [("a", "press")])
        store.record_drive(speed=30.0, steering_angle=12.0)
        store.append_log("INFO", "kidbot.test", "hello from test")

        snapshot = store.snapshot()

        self.assertTrue(snapshot["controller"]["connected"])
        self.assertEqual(snapshot["controller"]["name"], "8BitDo Lite 2")
        self.assertEqual(snapshot["controller"]["named_buttons"]["a"], True)
        self.assertEqual(snapshot["drive"]["speed"], 30.0)
        self.assertEqual(snapshot["events"][-1]["button"], "a")
        self.assertIn("hello from test", snapshot["logs"][-1]["message"])

    def test_debug_log_handler_appends_formatted_records(self):
        from kidbot.core.debug_state import DebugLogHandler, DebugStateStore

        store = DebugStateStore()
        handler = DebugLogHandler(store)
        handler.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))

        record = logging.LogRecord("kidbot.test", logging.WARNING, __file__, 12, "careful", (), None)
        handler.emit(record)

        snapshot = store.snapshot()

        self.assertEqual(snapshot["logs"][-1]["level"], "WARNING")
        self.assertEqual(snapshot["logs"][-1]["logger"], "kidbot.test")
        self.assertEqual(snapshot["logs"][-1]["message"], "WARNING:careful")


if __name__ == "__main__":
    unittest.main()
