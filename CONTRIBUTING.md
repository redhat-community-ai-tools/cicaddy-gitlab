# Contributing to cicaddy-gitlab

Thank you for your interest in contributing to cicaddy-gitlab! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/<your-username>/cicaddy-gitlab.git
   cd cicaddy-gitlab
   ```
3. Install development dependencies:
   ```bash
   uv pip install -e ".[dev]"
   # Or with standard pip
   pip install -e ".[dev]"
   ```
4. Set up pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Development Workflow

1. Create a branch for your changes:
   ```bash
   git checkout -b my-feature
   ```

2. Make your changes and ensure they pass checks:
   ```bash
   # Run tests
   uv run pytest tests/

   # Run linting
   ruff check src/ tests/
   ruff format src/ tests/

   # Run pre-commit
   pre-commit run --all-files
   ```

3. Commit your changes with a signed-off commit:
   ```bash
   git commit -s -m "feat: description of change"
   ```

4. Push and open a pull request.

## Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation changes
- `chore:` — Maintenance tasks
- `test:` — Adding or updating tests
- `refactor:` — Code restructuring without behavior changes

## Code Style

- Python code follows [Ruff](https://docs.astral.sh/ruff/) defaults with a line length of 88
- All code must pass `ruff check` and `ruff format`
- Security scanning via `bandit` is enforced in pre-commit

## Testing

- Write tests for new functionality in `tests/unit/`
- Use `pytest` with `pytest-asyncio` for async tests
- Mock external services (GitLab API, AI providers) in unit tests

## Running Locally

See [docs/running-locally.md](docs/running-locally.md) for instructions on running the agent outside of GitLab CI.

## Pull Request Process

1. Ensure all tests pass and pre-commit hooks are clean
2. Update documentation if your change affects user-facing behavior
3. PRs require review before merging
4. Use squash merge for clean history

## Reporting Issues

- Use [GitHub Issues](https://github.com/redhat-community-ai-tools/cicaddy-gitlab/issues) to report bugs or request features
- Include steps to reproduce, expected behavior, and environment details

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
