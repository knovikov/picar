import tempfile
import unittest
from pathlib import Path


class FakeProcess:
    def __init__(self):
        self.terminated = False

    def poll(self):
        return 0 if self.terminated else None

    def terminate(self):
        self.terminated = True


class MediaPlayerTests(unittest.TestCase):
    def test_engine_sound_starts_switches_and_stops_with_speed(self):
        from kidbot.core.media import MediaPlayer

        launched = []

        def launch(path):
            process = FakeProcess()
            launched.append((path.name, process))
            return process

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sounds = root / "sounds"
            music = root / "music"
            stories = root / "stories"
            sounds.mkdir()
            music.mkdir()
            stories.mkdir()
            (sounds / "engine_idle.wav").write_bytes(b"idle")
            (sounds / "engine_rev.wav").write_bytes(b"rev")

            media = MediaPlayer(sounds, music, stories, process_launcher=launch)
            config = {"min_speed": 4, "rev_speed": 18}

            media.update_engine_sound(3.9, config)
            media.update_engine_sound(6, config)
            media.update_engine_sound(8, config)
            media.update_engine_sound(22, config)
            media.update_engine_sound(0, config)

        self.assertEqual([name for name, _process in launched], ["engine_idle.wav", "engine_rev.wav"])
        self.assertTrue(launched[0][1].terminated)
        self.assertTrue(launched[1][1].terminated)
        self.assertFalse(media.is_engine_sound_playing)

    def test_engine_sound_disabled_stops_running_process(self):
        from kidbot.core.media import MediaPlayer

        launched = []

        def launch(path):
            process = FakeProcess()
            launched.append(process)
            return process

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            sounds = root / "sounds"
            music = root / "music"
            stories = root / "stories"
            sounds.mkdir()
            music.mkdir()
            stories.mkdir()
            (sounds / "engine_idle.wav").write_bytes(b"idle")

            media = MediaPlayer(sounds, music, stories, process_launcher=launch)
            media.update_engine_sound(8, {"enabled": True})
            media.update_engine_sound(8, {"enabled": False})

        self.assertEqual(len(launched), 1)
        self.assertTrue(launched[0].terminated)


if __name__ == "__main__":
    unittest.main()
