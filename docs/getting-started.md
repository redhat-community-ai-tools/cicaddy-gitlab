# Getting Started with cicaddy-gitlab

## Prerequisites

- Python 3.11+
- A GitLab instance (gitlab.com or self-hosted)
- An AI provider API key (Gemini, OpenAI, or Claude)

## Installation

### From PyPI

```bash
pip install cicaddy-gitlab
```

### From Source

```bash
git clone https://github.com/redhat-community-ai-tools/cicaddy-gitlab.git
cd cicaddy-gitlab
pip install -e .
```

## Setting Up CI Variables

In your GitLab project, navigate to **Settings > CI/CD > Variables** and add:

1. **API Key** (required, masked):
   - `GEMINI_API_KEY` for Google Gemini
   - `OPENAI_API_KEY` for OpenAI
   - `ANTHROPIC_API_KEY` for Anthropic Claude

2. **Slack Webhook** (optional, masked):
   - `SLACK_WEBHOOK_URL` for notifications

## Including Templates

### Option 1: Remote Include (Public GitHub)

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/redhat-community-ai-tools/cicaddy-gitlab/main/gitlab/ai_agent_template.yml'
  - remote: 'https://raw.githubusercontent.com/redhat-community-ai-tools/cicaddy-gitlab/main/gitlab/ai_cron_template.yml'
```

### Option 2: Local Copy

Copy the template files to your repository and include locally:

```yaml
include:
  - local: '.gitlab/templates/ai_agent_template.yml'
```

## AI Provider Configuration

### Google Gemini (Default)

```yaml
variables:
  AI_PROVIDER: "gemini"
  GEMINI_API_KEY: $GEMINI_API_KEY
  AI_MODEL: "gemini-3-flash-preview"  # or gemini-3-pro-preview
```

### OpenAI

```yaml
variables:
  AI_PROVIDER: "openai"
  OPENAI_API_KEY: $OPENAI_API_KEY
  AI_MODEL: "gpt-4o"
```

### Anthropic Claude

```yaml
variables:
  AI_PROVIDER: "claude"
  ANTHROPIC_API_KEY: $ANTHROPIC_API_KEY
  AI_MODEL: "claude-sonnet-4-6"
```

### Anthropic Claude via Vertex AI

Uses Google Cloud ADC for authentication — no API key needed. Set `GOOGLE_APPLICATION_CREDENTIALS` as a **File** type CI/CD variable containing your service account JSON key.

```yaml
variables:
  AI_PROVIDER: "anthropic-vertex"
  ANTHROPIC_VERTEX_PROJECT_ID: $ANTHROPIC_VERTEX_PROJECT_ID
  CLOUD_ML_REGION: "us-east5"  # default
  AI_MODEL: "claude-sonnet-4-6"
```

## MCP Server Configuration

MCP (Model Context Protocol) servers provide external tool capabilities to the AI agent.

```yaml
variables:
  MCP_SERVERS_CONFIG: >-
    [{"name": "my-server", "protocol": "http",
      "endpoint": "https://my-mcp-server.example.com/mcp",
      "timeout": 300, "idle_timeout": 60}]
```

Set to `"[]"` for analysis without external tools.

## Security Best Practices

All secrets should be stored as GitLab CI/CD variables (**Settings > CI/CD > Variables**), never hardcoded in `.gitlab-ci.yml`.

| Variable | Masked | Protected | Notes |
|----------|--------|-----------|-------|
| `GEMINI_API_KEY` | **Yes** | Recommended | AI provider key |
| `OPENAI_API_KEY` | **Yes** | Recommended | AI provider key |
| `ANTHROPIC_API_KEY` | **Yes** | Recommended | AI provider key |
| `CONTEXT7_API_KEY` | **Yes** | Recommended | MCP tool authentication |
| `SLACK_WEBHOOK_URL` | **Yes** | Optional | Notification webhook |
| `GITLAB_TOKEN` | **Yes** | Recommended | Only needed for enhanced permissions beyond `CI_JOB_TOKEN` |
| `ANTHROPIC_VERTEX_PROJECT_ID` | **Yes** | Recommended | GCP project ID for Vertex AI Claude |
| `GOOGLE_APPLICATION_CREDENTIALS` | **File** | Recommended | GCP service account JSON key — use **File** type variable so GitLab writes it to disk and ADC picks it up automatically |
| `CI_JOB_TOKEN` | Auto | Auto | Provided and masked by GitLab automatically — no setup needed |

- **Masked** — hides values from job logs. Always enable for secrets.
- **Protected** — restricts the variable to protected branches/tags only. Use when you want to prevent feature branches from accessing production keys.
- For shared keys across multiple projects, set variables at the **group level** (**Group > Settings > CI/CD > Variables**) to avoid per-project duplication.
- Never commit `.env` files containing secrets to version control.

## Troubleshooting

### API Key Not Found

```
ERROR: AI_PROVIDER='gemini' requires GEMINI_API_KEY to be set
```

Ensure the variable is set in **Settings > CI/CD > Variables** with the "Mask variable" option checked.

### Template Not Found

If using `include: remote:`, ensure the URL is accessible from your GitLab instance. Some corporate firewalls may block GitHub raw content URLs.
