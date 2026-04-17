# Cicaddy-GitLab Development Guidelines

## Project Overview

Cicaddy-GitLab is the GitLab platform plugin for the cicaddy AI agent library. It extends cicaddy's core agent framework with GitLab-specific functionality including merge request analysis, GitLab API integration, and GitLab CI pipeline support.

## Architecture

### Plugin System

This package registers itself with cicaddy's plugin system via entry points in `pyproject.toml`:

- `cicaddy.agents` — registers GitLab-specific agents (e.g., `MergeRequestAgent`)
- `cicaddy.settings_loader` — provides GitLab settings loader
- `cicaddy.cli_args` / `cicaddy.env_vars` / `cicaddy.config_sections` / `cicaddy.validators` — CLI and config extensions

### Agent Registration

```python
# src/cicaddy_gitlab/plugin.py
def register_agents():
    from cicaddy.agent.factory import AgentFactory
    from cicaddy_gitlab.agent.mr_agent import MergeRequestAgent
    from cicaddy_gitlab.agent.branch_agent import BranchReviewAgent
    from cicaddy_gitlab.agent.factory import _detect_gitlab_agent_type

    AgentFactory.register("merge_request", MergeRequestAgent)
    AgentFactory.register("branch_review", BranchReviewAgent)
    AgentFactory.register_detector(_detect_gitlab_agent_type, priority=40)
```

Detector priority 40 ensures GitLab detection runs before cicaddy's built-in CI detector at priority 50.

### Key Subpackages

| Package | Purpose |
|---------|---------|
| `src/cicaddy_gitlab/agent/` | GitLab-specific agent implementations (`MergeRequestAgent`, `BranchReviewAgent`) |
| `src/cicaddy_gitlab/config/` | GitLab settings (tokens, project IDs, GitLab API URL) |
| `src/cicaddy_gitlab/gitlab_integration/` | GitLab API client and analyzers (MR diffs, branch diffs, code review) |
| `src/cicaddy_gitlab/plugin.py` | Entry point registration for cicaddy plugin system |
| `gitlab/` | Reusable GitLab CI templates (`ai_agent_template.yml`, `ai_cron_template.yml`) |

### Dependencies

- Depends on `cicaddy>=0.7.0` (core library) and `python-gitlab>=4.4.0`
- Follows the same agent/factory patterns as the core library
- Extends `BaseAIAgent` and `BaseReviewAgent` from cicaddy

## Agent Types

| Type | Class | Trigger |
|------|-------|---------|
| `merge_request` | `MergeRequestAgent` | `CI_MERGE_REQUEST_IID` or `CI_PIPELINE_SOURCE=merge_request_event` |
| `branch_review` | `BranchReviewAgent` | `AGENT_TYPE=branch_review` or push to non-default branch |
| `task` | `TaskAgent` (cicaddy core) | `CI_PIPELINE_SOURCE=schedule` or `TASK_TYPE` set |

`MergeRequestAgent` and `BranchReviewAgent` extend `BaseReviewAgent` which extends cicaddy's `BaseAIAgent` with `_setup_platform_integration()` for GitLab API.

## GitLab CI Templates

Two reusable templates in `gitlab/`:

### Merge Request Agent (`ai_agent_template.yml`)

For AI-powered code review on merge requests:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/redhat-community-ai-tools/cicaddy-gitlab/main/gitlab/ai_agent_template.yml'

ai_code_review:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini"
    GEMINI_API_KEY: $GEMINI_API_KEY
```

Key variables: `AI_PROVIDER`, `AI_MODEL`, `AGENT_TASKS`, `AI_TASK_FILE`, `MCP_SERVERS_CONFIG`, `MAX_INFER_ITERS`

### Scheduled/Cron Agent (`ai_cron_template.yml`)

For scheduled jobs with MCP tool servers:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/redhat-community-ai-tools/cicaddy-gitlab/main/gitlab/ai_cron_template.yml'

daily_analysis:
  extends: .ai_cron_template
  variables:
    AI_PROVIDER: "gemini"
    MCP_SERVERS_CONFIG: '[{"name": "my-server", "protocol": "http", ...}]'
    AI_TASK_PROMPT: "Analyze system data..."
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
```

Key variables: `TASK_TYPE`, `TASK_SCOPE`, `MAX_INFER_ITERS`, `MAX_EXECUTION_TIME`, `RECOVERY_ENABLED`

## Code Quality

- Run `pre-commit run --files <changed-files>` before committing
- Run `uv run pytest tests/ -q --cov=src/cicaddy_gitlab` before committing (must pass all tests)
- Prefer shared/utility modules over code duplication
- Follow type hints, Google-style docstrings, async where appropriate

## Git Workflow

- **Sign commits**: `git commit -s` (DCO sign-off required)
- Only commit files modified in current session
- **No "Generated with Claude Code"** or **"Co-Authored-By"** in commits, PR descriptions
- Ask permission before pushing to remote

## Python

- Use `uv` for package management
- Always use virtual environments
- Dev install: `uv pip install -e ".[dev,test]"`
- Run tests: `uv run pytest tests/ -q --cov=src/cicaddy_gitlab`
- Type checking: `uv run ty check` (if available)
- Format: `pre-commit run ruff-format --files <changed-files>`

## Running Locally

```bash
# Install and prepare env file
uv pip install -e .
cp .env.example .env.local   # task agent template
cp .env.mr.example .env.mr   # MR review template

# Validate and run
uv run cicaddy config show --env-file .env.local
uv run cicaddy run --env-file .env.local

# Override settings via CLI
uv run cicaddy run --env-file .env.local --ai-provider openai --verbose
```

## Release Process

1. Bump version in `pyproject.toml`
2. Update `AGENTS.md` if architecture changes
3. Run full test suite: `uv run pytest tests/ -q --cov=src/cicaddy_gitlab`
4. Create release with `gh release create v<version>`
5. PyPI publish is automated via `.github/workflows/python-publish.yml`
6. Downstream packages auto-pick latest via `>=` constraints
