import os
import tempfile
import unittest
from pathlib import Path


class SecretsTests(unittest.TestCase):
    def test_save_openai_key_writes_local_env_file_and_process_env(self):
        from kidbot.core.secrets import load_env_file, save_openai_api_key

        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"

            save_openai_api_key(env_path, "sk-test-123")

            self.assertEqual(load_env_file(env_path)["OPENAI_API_KEY"], "sk-test-123")
            self.assertEqual(os.environ["OPENAI_API_KEY"], "sk-test-123")
            self.assertEqual(env_path.stat().st_mode & 0o777, 0o600)

    def test_mask_secret_keeps_only_edges(self):
        from kidbot.core.secrets import mask_secret

        self.assertEqual(mask_secret("sk-1234567890"), "sk-1...7890")
        self.assertEqual(mask_secret("short"), "set")
        self.assertEqual(mask_secret(""), "not set")

