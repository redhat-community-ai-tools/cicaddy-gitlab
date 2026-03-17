# Development Guide

Local development setup, testing, and running cicaddy-gitlab outside GitLab CI.

## Quick Start

```bash
# Run with env file (recommended)
uv run cicaddy run --env-file .env.mr

# Dry run to verify config
uv run cicaddy run --env-file .env.mr --dry-run

# CLI help
cicaddy run --help
```

See [Environment File Preparation](env-file-preparation.md) for `.env` file examples.

## Setup

### Prerequisites

- Python 3.11+
- `uv` (recommended) or `pip`

### Install

```bash
# Using uv (recommended)
uv venv && source .venv/bin/activate
uv pip install -e ".[dev,test]"

# Or using pip
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,test]"
```

### Pre-commit

```bash
pre-commit install
pre-commit install --hook-type commit-msg
```

### Verify

```bash
uv run cicaddy version
```

## Running Locally

### Agent Types

| Agent | Key Variables | Notes |
|-------|--------------|-------|
| MR Agent | `AGENT_TYPE=merge_request`, `CI_MERGE_REQUEST_IID`, `CI_PROJECT_ID` | Needs GitLab API access |
| Branch Review | `AGENT_TYPE=branch_review` | Uses local git, no API needed |
| Task Agent | `AGENT_TYPE=task`, `TASK_TYPE`, `TASK_SCOPE` | Independent of MR context |

### MR Agent Example

Create `.env.mr`:
```bash
AGENT_TYPE=merge_request
CI_MERGE_REQUEST_IID=21
CI_PROJECT_ID=my-group/my-project
CI_API_V4_URL=https://gitlab.example.com/api/v4
GITLAB_TOKEN=glpat-your_token
AI_PROVIDER=gemini
GEMINI_API_KEY=your_key
MCP_SERVERS_CONFIG='[{"name": "Context7", "protocol": "http", "endpoint": "https://mcp.context7.com/mcp", "timeout": 300}]'
LOG_LEVEL=DEBUG
```

```bash
uv run cicaddy run --env-file .env.mr
```

**Note**: Do NOT set `GIT_WORKING_DIRECTORY` for local development — leave it unset so the agent uses GitLab API for diff retrieval instead of running git commands in the wrong repository.

### Task Agent Example

Create `.env.cron`:
```bash
AGENT_TYPE=task
TASK_TYPE=custom
TASK_SCOPE=external_tools
AI_PROVIDER=gemini
GEMINI_API_KEY=your_key
AI_TASK_PROMPT='Analyze system metrics from the past 24 hours.'
MCP_SERVERS_CONFIG='[{"name":"metrics-server","protocol":"http","endpoint":"https://my-mcp-server.example.com/mcp","timeout":300}]'
LOG_LEVEL=DEBUG
```

```bash
uv run cicaddy run --env-file .env.cron
```

### Live Code Changes

| Method | Live Changes? | Use Case |
|--------|--------------|----------|
| `uv pip install -e .` + `uv run cicaddy run` | Yes | Development (recommended) |
| `uv pip install .` + `uv run cicaddy run` | No | CI/Production |

## Testing

```bash
# All tests
pytest tests/ -v

# Unit / integration only
pytest tests/unit/ -v
pytest tests/integration/ -v

# Quick dev test (stops on first failure)
pytest tests/ -x -q

# Coverage
pytest tests/ -v --cov=src --cov-report=html --cov-report=term
```

### Test Markers

```bash
pytest tests/ -m unit
pytest tests/ -m integration
pytest tests/ -m "not slow"
pytest tests/ -m mcp
```

## Code Quality

```bash
ruff format src/ tests/
ruff check src/ tests/
pre-commit run --all-files
```

## Configuration

### Settings Precedence

1. Environment variables (highest)
2. Auto-detection (API keys → providers)
3. Built-in defaults

### Performance Tuning

```bash
MAX_INFER_ITERS=3 cicaddy run          # Fewer iterations
AI_MODEL=gemini-2.5-flash cicaddy run  # Faster model
```

### Debug

```bash
LOG_LEVEL=DEBUG JSON_LOGS=true cicaddy run 2>&1 | tee debug.log
```

## Contributing

1. Create feature branch from `main`
2. Make changes with tests
3. Run `pre-commit run --all-files`
4. Test locally with `cicaddy run`
5. Commit with `git commit -s`
6. Push and create merge request

## Related Docs

- [Environment File Preparation](env-file-preparation.md) — `.env` file setup
- [Configuration Guide](configuration.md) — CI/CD variables and options
- [Task Jobs Guide](cron-jobs.md) — Scheduled task setup
- [MCP Integration](https://github.com/waynesun09/cicaddy/blob/main/docs/mcp-integration.md) — MCP server configuration
