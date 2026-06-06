import tempfile
import unittest
from pathlib import Path


class FakeRunner:
    def __init__(self, outputs=None):
        self.outputs = outputs or {}
        self.commands = []

    def __call__(self, command, **kwargs):
        self.commands.append(list(command))
        key = tuple(command)
        value = self.outputs.get(key, "")
        return type("Result", (), {"returncode": 0, "stdout": value, "stderr": ""})()


class UpdaterTests(unittest.TestCase):
    def test_apply_update_saves_current_commit_before_pull(self):
        from kidbot.core.updater import apply_update, load_stable_build

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            runner = FakeRunner(
                {
                    ("git", "rev-parse", "HEAD"): "aaa111\n",
                    ("git", "rev-parse", "--abbrev-ref", "HEAD"): "main\n",
                    ("git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"): "origin/main\n",
                    ("git", "status", "--porcelain", "--untracked-files=all"): "",
                    ("git", "rev-parse", "@"): "aaa111\n",
                    ("git", "rev-parse", "@{u}"): "bbb222\n",
                    ("git", "merge-base", "@", "@{u}"): "aaa111\n",
                }
            )

            result = apply_update(repo, runner=runner, restart_service=False)

            self.assertTrue(result.success)
            self.assertTrue(result.changed)
            self.assertEqual(load_stable_build(repo).commit, "aaa111")
            self.assertIn(["git", "pull", "--ff-only"], runner.commands)

    def test_check_update_status_blocks_dirty_tree(self):
        from kidbot.core.updater import check_update_status

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            runner = FakeRunner(
                {
                    ("git", "rev-parse", "HEAD"): "aaa111\n",
                    ("git", "rev-parse", "--abbrev-ref", "HEAD"): "main\n",
                    ("git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"): "origin/main\n",
                    ("git", "status", "--porcelain", "--untracked-files=all"): " M kidbot/core/web_server.py\n",
                    ("git", "rev-parse", "@"): "aaa111\n",
                    ("git", "rev-parse", "@{u}"): "bbb222\n",
                    ("git", "merge-base", "@", "@{u}"): "aaa111\n",
                }
            )

            status = check_update_status(repo, runner=runner)

            self.assertFalse(status.success)
            self.assertTrue(status.dirty)
            self.assertIn("локальные изменения", status.message)

    def test_rollback_to_stable_resets_to_saved_commit(self):
        from kidbot.core.updater import rollback_to_stable, save_stable_build

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            save_stable_build(repo, "aaa111", branch="main", reason="test")
            runner = FakeRunner({("git", "rev-parse", "HEAD"): "bbb222\n"})

            result = rollback_to_stable(repo, runner=runner, restart_service=False)

            self.assertTrue(result.success)
            self.assertTrue(result.changed)
            self.assertIn(["git", "reset", "--hard", "aaa111"], runner.commands)


if __name__ == "__main__":
    unittest.main()
