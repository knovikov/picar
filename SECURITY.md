# Security

Please do not commit local robot secrets or personal data.

- Keep `.env` local. It may contain `OPENAI_API_KEY`.
- Keep `.deploy-keys/` local. It may contain private SSH deploy keys.
- Keep `photos/`, `logs/`, and `.kidbot/` local unless you intentionally want to publish them.
- Change the default setup access-point password in `config.yaml` before using the robot around other people.

For private forks, use `./tools/setup_robot.sh --private` to create a read-only
deploy key locally. For public repos, HTTPS clone is enough.
