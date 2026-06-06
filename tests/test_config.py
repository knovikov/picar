import tempfile
import unittest
from pathlib import Path


class ConfigTests(unittest.TestCase):
    def test_simple_yaml_fallback_reads_nested_robot_settings(self):
        from kidbot.core.config import _read_simple_yaml

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "config.yaml"
            path.write_text(
                """
robot:
  name: "KidBot"
  mock: true
speed:
  max_forward: 40
""".strip(),
                encoding="utf-8",
            )

            config = _read_simple_yaml(path)

            self.assertEqual(config["robot"]["name"], "KidBot")
            self.assertTrue(config["robot"]["mock"])
            self.assertEqual(config["speed"]["max_forward"], 40)


if __name__ == "__main__":
    unittest.main()

