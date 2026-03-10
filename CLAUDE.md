# Claude Code Rules

## Project Overview

Cicaddy-GitLab is the GitLab platform plugin for the cicaddy AI agent library. It extends cicaddy's core agent framework with GitLab-specific functionality including merge request analysis, GitLab API integration, and GitLab CI pipeline support.

## Architecture

### Plugin System

This package registers itself with cicaddy's plugin system via entry points in `pyproject.toml`:

- `cicaddy.agents` — registers GitLab-specific agents (e.g., `MergeRequestAgent`)
- `cicaddy.settings_loader` — provides GitLab settings loader
- `cicaddy.cli_args` / `cicaddy.env_vars` / `cicaddy.config_sections` / `cicaddy.validators` — CLI and config extensions

### Key Subpackages

| Package | Purpose |
|---------|---------|
| `src/cicaddy_gitlab/agent/` | GitLab-specific agent implementations |
| `src/cicaddy_gitlab/config/` | GitLab settings (tokens, project IDs, etc.) |
| `src/cicaddy_gitlab/gitlab_integration/` | GitLab API client and analyzers |
| `src/cicaddy_gitlab/plugin.py` | Entry point registration for cicaddy |

### Dependencies

- Depends on `cicaddy>=0.2.0` (core library) and `python-gitlab>=4.4.0`
- Follows the same agent/factory patterns as the core library

## Code Quality

- Run `pre-commit run --files <changed-files>` before committing
- Run `uv run pytest tests/ -q` before committing
- Prefer shared/utility modules over code duplication

## Git Workflow

- Sign commits: `git commit -s`
- Only commit files modified by Claude in current session
- No "Generated with Claude Code" or "Co-Authored-By" in commits
- Ask permission before pushing

## Python

- Use `uv` for package management
- Always use virtual environments
- Dev install: `uv pip install -e ".[dev,test]"`
- Run tests: `uv run pytest tests/ -q`
