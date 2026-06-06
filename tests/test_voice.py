import unittest


class VoiceTests(unittest.TestCase):
    def test_voice_uses_espeak_when_cloud_voice_is_disabled(self):
        from kidbot.core.voice import Voice

        spoken = []
        voice = Voice(
            use_openai=False,
            command_runner=lambda command: spoken.append(command),
        )

        voice.say("Привет, Ярослав!")

        self.assertEqual(len(spoken), 1)
        self.assertEqual(spoken[0][0], "espeak-ng")
        self.assertIn("Привет, Ярослав!", spoken[0])


if __name__ == "__main__":
    unittest.main()

