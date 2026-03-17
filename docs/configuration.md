# Configuration Guide

Configure cicaddy-gitlab for your project using GitLab CI/CD variables, AI providers, and MCP servers.

## CI/CD Variables

Set variables in **Project → Settings → CI/CD → Variables**. Mark secrets as **Masked** and **Protected**.

### AI Provider Keys (choose one)

| Variable | Provider | Example |
|----------|----------|---------|
| `GEMINI_API_KEY` | Gemini (recommended) | `AIzaSyC...` |
| `OPENAI_API_KEY` | OpenAI | `sk-proj-...` |
| `AZURE_OPENAI_KEY` + `AZURE_ENDPOINT` | Azure OpenAI | |

### Optional Variables

| Variable | Description |
|----------|-------------|
| `GITLAB_TOKEN` | GitLab API token (CI_JOB_TOKEN used by default for MR Agent) |
| `SLACK_WEBHOOK_URL` | Slack webhook for notifications |
| `MCP_TOKEN` | MCP server authentication |

## Agent Types

Auto-detected from CI environment, or set explicitly with `AGENT_TYPE`:

| Agent | Trigger | GitLab API | Output |
|-------|---------|------------|--------|
| `merge_request` | `CI_MERGE_REQUEST_IID` exists | Required | CI comments + Slack |
| `branch_review` | Push to non-default branch | Not required | Slack only |
| `task` | Schedule or `TASK_TYPE` set | Optional | Slack + reports |

**Detection priority**: `AGENT_TYPE` env var → `CI_MERGE_REQUEST_IID` → `TASK_TYPE` → `CI_PIPELINE_SOURCE` → default (task)

## AI Provider Config

```yaml
variables:
  AI_PROVIDER: "gemini"                    # gemini, openai, azure
  GEMINI_API_KEY: $GEMINI_API_KEY
  AI_MODEL: "gemini-3-flash-preview"       # optional
```

## MCP Server Config

```yaml
variables:
  MCP_SERVERS_CONFIG: |
    [{
      "name": "my-server",
      "protocol": "http",
      "endpoint": "https://my-mcp-server.example.com/mcp",
      "headers": {"Authorization": "Bearer ${MCP_TOKEN}"},
      "timeout": 300,
      "idle_timeout": 60
    }]
```

See [MCP Integration Guide](https://github.com/waynesun09/cicaddy/blob/main/docs/mcp-integration.md) for config schema and timeout details.

## Task Definitions

### DSPy Task Files (recommended)

```yaml
variables:
  AI_TASK_FILE: ".gitlab/prompts/my_analysis.yml"
```

See [examples/prompts/](../examples/prompts/) for DSPy task file examples.

### Inline Prompts

```yaml
variables:
  AI_TASK_PROMPT: |
    Custom instructions for AI analysis.
    Use markdown format for responses.
```

`AI_TASK_FILE` takes precedence over `AI_TASK_PROMPT` when both are set.

## Slack Notifications

```yaml
variables:
  SLACK_WEBHOOK_URL: $SLACK_WEBHOOK_URL

  # Multiple webhooks (JSON array)
  SLACK_WEBHOOK_URLS: |
    ["https://hooks.slack.com/services/T123/B456/general",
     "https://hooks.slack.com/services/T123/B789/security"]
```

The agent auto-converts markdown to Slack format with rich formatting, emoji indicators, and severity-based layouts.

## Schedule Rules

```yaml
# Basic schedule
daily_monitoring:
  extends: .ai_cron_template
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"

# Specific schedule by description
daily_analysis:
  extends: .ai_cron_template
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule" && $CI_PIPELINE_SCHEDULE_DESCRIPTION == "system_statistics_daily"

# Manual execution also allowed
flexible_analysis:
  extends: .ai_cron_template
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
    - if: $CI_PIPELINE_SOURCE == "web"
      when: manual
```

## Complete Example

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/redhat-community-ai-tools/cicaddy-gitlab/main/gitlab/ai_agent_template.yml'

ai_analysis:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini"
    GEMINI_API_KEY: $GEMINI_API_KEY
    SLACK_WEBHOOK_URL: $SLACK_WEBHOOK_URL
    AGENT_TASKS: "code_review,security_scan"
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

## Environment Variables Reference

### Core

| Variable | Description | Default |
|----------|-------------|---------|
| `AI_PROVIDER` | AI provider | Auto-detected from keys |
| `AI_MODEL` | Model name | Provider default |
| `MCP_SERVERS_CONFIG` | MCP servers (JSON array) | `[]` |
| `SLACK_WEBHOOK_URL` | Slack webhook | - |
| `AI_TASK_FILE` | DSPy task file path | - |
| `AI_TASK_PROMPT` | Inline analysis prompt | Default prompt |
| `AGENT_TASKS` | Comma-separated tasks | `code_review` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `GIT_DIFF_CONTEXT_LINES` | Git diff context lines | `10` |

### AI Response Format

`AI_RESPONSE_FORMAT` controls output format. Default is `markdown` (rendered inline in HTML report). Set to `html` or `json` to save the raw AI response as a separate artifact file (`_ai_direct_resp.<ext>`).

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No merge request IID provided" | Ensure job runs on MR events, check `rules` |
| "Failed to connect to MCP server" | Verify URL, credentials, and network access |
| "AI provider configuration error" | Check `AI_PROVIDER` value and API key |
| "GitLab API authentication failed" | CI_JOB_TOKEN used by default; only set `GITLAB_TOKEN` for enhanced permissions |

**Debug mode**: Set `LOG_LEVEL: "DEBUG"` and `JSON_LOGS: "true"`.
