# Environment File Preparation Guide

Prepare `.env` files for running cicaddy-gitlab locally.

## Basic Template

```bash
# Agent Configuration
AGENT_TYPE=task                    # task, merge_request, branch_review
TASK_TYPE=custom                   # For task agents
TASK_SCOPE=external_tools          # For task agents with MCP tools

# AI Provider
AI_PROVIDER=gemini                 # gemini, openai, azure, claude
GEMINI_API_KEY=your-api-key-here
AI_MODEL=gemini-3-flash-preview    # Optional: override default model

# Task Definition (choose one)
AI_TASK_FILE='.gitlab/prompts/my_task.yml'  # DSPy YAML (recommended)
# AI_TASK_PROMPT='Your task instructions here'  # Or inline prompt

# MCP Servers
MCP_SERVERS_CONFIG='[{"name":"server-name","protocol":"http","endpoint":"https://example.com/mcp","timeout":300}]'

# Logging
LOG_LEVEL=DEBUG
```

`AI_TASK_FILE` takes precedence over `AI_TASK_PROMPT`. See [examples/prompts/](../examples/prompts/) for DSPy task file examples.

## AI_TASK_PROMPT Rules

When using inline prompts instead of task files:

1. **Single quotes** to wrap the entire value
2. **Double quotes** preserved inside
3. **Multi-line** works within single quotes
4. **Variable placeholders** use `{{VAR_NAME}}` syntax

```bash
AI_TASK_PROMPT='You are an expert analyst. Follow this workflow:

**1. Data Collection**
Use available MCP tools to gather metrics.

**2. Analysis**
Identify trends and anomalies.

**3. Output**
Comprehensive report in markdown with tables and recommendations.'
```

## Example: MR Review with Context7

```bash
# .env.mr
AGENT_TYPE=merge_request
CI_MERGE_REQUEST_IID=123
CI_PROJECT_ID=your-group/your-project
CI_API_V4_URL=https://gitlab.example.com/api/v4
GITLAB_TOKEN=glpat-your-token
AI_PROVIDER=gemini
GEMINI_API_KEY=your-key
MCP_SERVERS_CONFIG='[{"name":"context7","protocol":"http","endpoint":"https://mcp.context7.com/mcp","timeout":300,"idle_timeout":60}]'
LOG_LEVEL=DEBUG
```

**Note**: Do NOT set `GIT_WORKING_DIRECTORY` for local development — leave it unset so the agent uses GitLab API for diff retrieval.

## Example: Task Agent with DSPy File

```bash
# .env.cron
AGENT_TYPE=task
TASK_TYPE=custom
TASK_SCOPE=external_tools
AI_PROVIDER=gemini
GEMINI_API_KEY=your-key
AI_TASK_FILE='.gitlab/prompts/analysis.yml'
REPO_NAME=my-repo
ANALYSIS_DAYS=30
MAX_INFER_ITERS=40
MCP_SERVERS_CONFIG='[{"name":"devlake","protocol":"http","endpoint":"https://devlake-mcp.example.com/mcp","timeout":600,"idle_timeout":300}]'
LOG_LEVEL=DEBUG
```

## MCP Server Patterns

### Multiple Servers

```bash
MCP_SERVERS_CONFIG='[{"name":"context7","protocol":"http","endpoint":"https://mcp.context7.com/mcp","timeout":300},{"name":"devlake","protocol":"http","endpoint":"https://devlake.example.com/mcp","timeout":600}]'
```

### Stdio Protocol (Local Servers)

```bash
MCP_SERVERS_CONFIG='[{"name":"sourcebot","protocol":"stdio","command":"npx","args":["-y","@sourcebot/mcp@latest"],"env":{"SOURCEBOT_HOST":"https://sourcebot.example.com"},"timeout":300}]'
```

### Authenticated Endpoints

```bash
MCP_SERVERS_CONFIG='[{"name":"secure-server","protocol":"http","endpoint":"https://secure-mcp.example.com/mcp","headers":{"Authorization":"Bearer your-token"},"timeout":120}]'
```

## Validating Configuration

```bash
uv run cicaddy config show --env-file .env.mr
uv run cicaddy run --env-file .env.mr --dry-run
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| JSON parse error in MCP config | Use single quotes around JSON, double quotes inside |
| Variable not substituted | Use `{{VAR_NAME}}` syntax |
| Prompt truncated | Ensure closing single quote wraps entire prompt |
| API key not recognized | No spaces around `=` |

## Security

- Never commit `.env` files — add `.env*` to `.gitignore`
- Restrict file permissions: `chmod 600 .env.mr`

## Related Docs

- [Development Guide](development.md) — Local development setup
- [MCP Integration](https://github.com/waynesun09/cicaddy/blob/main/docs/mcp-integration.md) — MCP server configuration
- [Configuration Guide](configuration.md) — All configuration options
