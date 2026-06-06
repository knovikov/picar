import unittest

from kidbot.core.ai_chat import AIChat
from kidbot.kid_code.robot_personality import build_personality_prompt


class AIChatConfigTests(unittest.TestCase):
    def test_personality_prompt_uses_public_default_child_context(self):
        prompt = build_personality_prompt()

        self.assertIn("с ребенком 7 лет", prompt)
        self.assertNotIn("Ярослав", prompt)

    def test_response_history_uses_configured_child_name_when_present(self):
        chat = AIChat({"robot": {"child_name": "Миша", "child_age": 8}, "openai": {}})
        chat.history.append({"role": "user", "content": "Привет"})

        self.assertIn("Миша: Привет", chat._response_input())
        self.assertIn("по имени Миша", chat.personality_prompt)


if __name__ == "__main__":
    unittest.main()
