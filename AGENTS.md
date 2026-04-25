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

- Depends on `cicaddy>=0.11.0` (core library) and `python-gitlab>=4.4.0`
- Follows the same agent/factory patterns as the core library
- Extends `BaseAIAgent` and `BaseReviewAgent` from cicaddy

## Agent Types

| Type | Class | Trigger |
|------|-------|---------|
| `merge_request` | `MergeRequestAgent` | `CI_MERGE_REQUEST_IID` or `CI_PIPELINE_SOURCE=merge_request_event` |
| `branch_review` | `BranchReviewAgent` | `AGENT_TYPE=branch_review` or push to non-default branch |
| `task` | `TaskAgent` (cicaddy core) | `CI_PIPELINE_SOURCE=schedule` or `TASK_TYPE` set |

`MergeRequestAgent` and `BranchReviewAgent` extend `BaseReviewAgent` which extends cicaddy's `BaseAIAgent` with `_setup_platform_integration()` for GitLab API.

## Sub-Agent Delegation (v0.4.0+)

Requires cicaddy>=0.8.0. When `DELEGATION_MODE=auto`, the parent agent's `analyze()` method delegates to specialized sub-agents:

1. **Triage** — AI analyzes the MR diff/context and selects reviewers
2. **Parallel Execution** — Selected sub-agents run concurrently with focused prompts
3. **Aggregation** — Results merged into a single MR comment with per-agent sections

### Plugin Hooks

The cicaddy-gitlab plugin provides:

- `cicaddy.delegation_blocked_tools` entry point — blocks GitLab write operations (posting notes, merging MRs, etc.) so sub-agents only perform analysis
- Delegation metadata in MR comments — shows which agents ran, success/failure counts, and execution time in a collapsible details block

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DELEGATION_MODE` | `none` | `none` or `auto` |
| `MAX_SUB_AGENTS` | `3` | Max concurrent sub-agents (1-10) |
| `SUB_AGENT_MAX_ITERS` | `10` | Iterations per sub-agent (1-15) |
| `DELEGATION_AGENTS_DIR` | `.agents/delegation` | Custom agent YAML directory |
| `DELEGATION_AGENTS` | (empty) | JSON config for inline custom sub-agents |
| `TRIAGE_PROMPT` | (empty) | Custom triage instructions |

CLI flags: `--delegation-mode auto --max-sub-agents 2`

See cicaddy's [sub-agent delegation docs](https://github.com/waynesun09/cicaddy/blob/main/docs/sub-agent-delegation.md) for built-in agents, custom YAML format, and tool filtering.

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

## Comment Posting Control

| Variable | Default | Description |
|----------|---------|-------------|
| `POST_MR_COMMENT` | `true` | Whether to post analysis results as MR/commit comment. Set to `false` for local testing. |

Accepted values: `true`/`false`, `1`/`0`, `yes`/`no` (case-insensitive). Unrecognized values log a warning and default to `true`.

**Local development**: If you have `GITLAB_TOKEN` set (e.g., for `glab` CLI), add `POST_MR_COMMENT=false` to your `.env` file to prevent accidentally posting review comments to real MRs during local testing.

**Note**: cicaddy-action defaults `POST_PR_COMMENT` to `false` (explicit opt-in) because GitHub Actions tokens are often personal access tokens. cicaddy-gitlab defaults to `true` to preserve backward compatibility with existing CI pipelines that expect comments to be posted automatically.

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

**Important**: When running locally with a valid `GITLAB_TOKEN`, always set `POST_MR_COMMENT=false` in your env file to avoid posting to real MRs.

## Release Process

1. Bump version in `pyproject.toml`
2. Update `AGENTS.md` if architecture changes
3. Run full test suite: `uv run pytest tests/ -q --cov=src/cicaddy_gitlab`
4. Create release with `gh release create v<version>`
5. PyPI publish is automated via `.github/workflows/python-publish.yml`
6. Downstream packages auto-pick latest via `>=` constraints
