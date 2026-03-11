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
  AI_MODEL: "claude-3-5-sonnet-latest"
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

## Troubleshooting

### API Key Not Found

```
ERROR: AI_PROVIDER='gemini' requires GEMINI_API_KEY to be set
```

Ensure the variable is set in **Settings > CI/CD > Variables** with the "Mask variable" option checked.

### Template Not Found

If using `include: remote:`, ensure the URL is accessible from your GitLab instance. Some corporate firewalls may block GitHub raw content URLs.
