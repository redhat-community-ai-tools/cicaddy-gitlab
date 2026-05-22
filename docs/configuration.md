# Configuration Guide

Configure cicaddy-gitlab for your project using GitLab CI/CD variables, AI providers, and MCP servers.

## CI/CD Variables

Set variables in **Project → Settings → CI/CD → Variables**. Mark secrets as **Masked** and leave **Protect variable** unchecked for variables used in MR pipelines (protected variables are only available on protected branches).

### AI Provider Keys (choose one)

| Variable | Provider | Example |
|----------|----------|---------|
| `GEMINI_API_KEY` | Gemini (recommended) | `AIzaSyC...` |
| `OPENAI_API_KEY` | OpenAI | `sk-proj-...` |
| `ANTHROPIC_API_KEY` | Anthropic Claude | `sk-ant-...` |
| `AZURE_OPENAI_KEY` + `AZURE_ENDPOINT` | Azure OpenAI | |
| `GOOGLE_CLOUD_PROJECT` | Gemini via Vertex AI | (uses ADC, no API key) |
| `ANTHROPIC_VERTEX_PROJECT_ID` | Anthropic via Vertex AI | (uses ADC, no API key) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Vertex AI (both providers) | File type; optional for Workload Identity / GKE (SDK uses metadata server). Base64-encoded JSON recommended (enables masking), plain JSON also accepted |

### Optional Variables

| Variable | Description |
|----------|-------------|
| `GITLAB_TOKEN` | Project or Group Access Token with `api` scope — required for MR diff access and comment posting. Falls back to `CI_JOB_TOKEN` if not set, which may cause `401` errors (see [Getting Started — GitLab API Token](getting-started.md#gitlab-api-token)) |
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
  AI_PROVIDER: "gemini"                    # gemini, openai, azure, claude, gemini-vertex, anthropic-vertex
  GEMINI_API_KEY: $GEMINI_API_KEY
  AI_MODEL: "gemini-3.5-flash"             # optional
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
| `POST_MR_COMMENT` | Post summary comment on the MR | `true` |
| `INLINE_REVIEW_COMMENTS` | Post findings as inline comments on diff lines | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `GIT_DIFF_CONTEXT_LINES` | Git diff context lines | `10` |

### Vertex AI

| Variable | Description | Default |
|----------|-------------|---------|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID (gemini-vertex) | - |
| `ANTHROPIC_VERTEX_PROJECT_ID` | GCP project ID (anthropic-vertex) | - |
| `GOOGLE_CLOUD_LOCATION` | GCP region | `global` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service account JSON key (File type; optional for Workload Identity / GKE — SDK uses metadata server). Base64-encoded recommended for masking, plain JSON also accepted | - |

### AI Response Format

`AI_RESPONSE_FORMAT` controls output format. Default is `markdown` (rendered inline in HTML report). Set to `html` or `json` to save the raw AI response as a separate artifact file (`_ai_direct_resp.<ext>`).

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No merge request IID provided" | Ensure job runs on MR events, check `rules` |
| "Failed to connect to MCP server" | Verify URL, credentials, and network access |
| "AI provider configuration error" | Check `AI_PROVIDER` value and API key |
| "GitLab API authentication failed" / `401 Unauthorized` | Create a Project Access Token with `api` scope and store as `GITLAB_TOKEN` CI/CD variable with **Protect variable** unchecked (see [Getting Started — GitLab API Token](getting-started.md#gitlab-api-token)). Verify the token value was actually saved |
| `Permission denied on resource project $GOOGLE_CLOUD_PROJECT` (literal `$`) | CI/CD variable not reaching the job — most likely **Protect variable** is checked (protected variables are unavailable in MR pipelines on non-protected branches) |
| "GOOGLE_APPLICATION_CREDENTIALS file is not valid JSON or base64-encoded JSON" | Re-export the service account key; store as **File** type variable (`base64 -w0 < key.json`) |
| "GOOGLE_APPLICATION_CREDENTIALS file not found" | Ensure the CI/CD variable is configured as **File** type, not **Variable** type |
| "Using Application Default Credentials (metadata server / environment-based)" | Normal on GCE/GKE/Cloud Run — no action needed. Set `GOOGLE_APPLICATION_CREDENTIALS` only when not running on GCP infrastructure |

**Debug mode**: Set `LOG_LEVEL: "DEBUG"` and `JSON_LOGS: "true"`.
