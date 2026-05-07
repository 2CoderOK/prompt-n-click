# Contributing to prompt-n-click

Thank you for your interest in contributing! Here are some quick guidelines.

## Reporting Issues

- Search existing issues before opening a new one.
- Include your OS, GPU, Docker version, and model being used.
- Paste the relevant container logs (`docker compose logs api_orchestrator`).

## Submitting a Pull Request

1. Fork the repository and create a feature branch from `main`.
2. Keep changes focused — one logical change per PR.
3. Test your changes end-to-end with Docker Compose before submitting.
4. Update the README if you add new configuration options or pipeline steps.
5. Open the PR with a clear description of what changed and why.

## Adding a New Game Type

1. Add a new `GAME_TYPE_*` constant in `src/shared/constants.py`.
2. Create a skills directory under `src/backend/skills/<game_type>/`.
3. Register the type in `src/backend/nodes/game_type_registry.py`.
4. Add ComfyUI workflow JSON files to `workflows/` as needed.

## Code Style

- Python: follow PEP 8. No hard requirement on a formatter, but consistency within a file is expected.
- Keep functions short and single-purpose.
- Do not commit personal paths, API keys, or credentials.

## License

By contributing you agree that your contributions will be licensed under the project's [MIT License](LICENSE).
