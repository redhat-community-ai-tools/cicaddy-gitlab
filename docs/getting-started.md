# Getting Started with cicaddy-gitlab

## Prerequisites

- Python 3.11+
- A GitLab instance (gitlab.com or self-hosted)
- A GitLab API token with `api` scope (see [GitLab API Token](#gitlab-api-token) below)
- An AI provider API key **or** Google Cloud ADC credentials (for Vertex AI providers)

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

### GitLab API Token

The agent needs a GitLab API token to read merge request diffs and post review comments. Without it, the agent falls back to `CI_JOB_TOKEN`, which may not have sufficient permissions and can result in `401 Unauthorized` errors.

Create a **Project Access Token**:

1. Go to your project **Settings > Access tokens**
2. Click **Add new token**
3. Set **Token name** (e.g. `cicaddy-agent`), **Expiration date**, **Role** to `Developer`, and check the **`api`** scope
4. Click **Create project access token** and copy the token
5. Go to **Settings > CI/CD > Variables** and add:
   - **Key**: `GITLAB_TOKEN`
   - **Value**: the token you copied
   - **Mask variable**: checked
   - **Expand variable reference**: checked
   - **Protect variable**: unchecked (so MR pipelines on non-protected branches can use it)

> **Tip:** To share one token across multiple projects, create a **Group Access Token** instead (**Group > Settings > Access tokens** with `api` scope) and add it as a group-level CI/CD variable (**Group > Settings > CI/CD > Variables**). All projects in that group will inherit it automatically.
>
> **Troubleshooting:** If the agent logs show `401 Unauthorized` with `Failed to load project`, verify that the token value was actually copied into the CI/CD variable (the token is only shown once at creation time). Also check that **Protect variable** is unchecked — protected variables are only available on protected branches, not in MR pipelines.

### AI Provider Key

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
  AI_MODEL: "gemini-3.5-flash"  # or gemini-3.1-pro-preview
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

### Google Gemini via Vertex AI

Uses Google Cloud ADC for authentication — no API key needed. On GCE, GKE, or Cloud Run, the SDK auto-discovers credentials from the metadata server, so no key file is required. For other environments (local dev, non-GCP CI runners), set `GOOGLE_APPLICATION_CREDENTIALS` as a **File** type CI/CD variable containing your service account JSON key. **Base64-encode the JSON before storing** (`base64 -w0 < service-account.json`) so the value can be masked in job logs. Plain JSON is also accepted but cannot be masked. The template auto-detects the format and decodes as needed.

> **Security**: Store `GOOGLE_APPLICATION_CREDENTIALS` at the **group level** with **Masked** flag to limit exposure. At the project level, any user with Maintainer access or above can view CI/CD variables. Base64-encoding enables the **Mask variable** option, which prevents the credential from appearing in job logs. Leave **Protect variable** unchecked if the variable needs to be available in MR pipelines on non-protected branches.

```yaml
variables:
  AI_PROVIDER: "gemini-vertex"
  GOOGLE_CLOUD_PROJECT: $GOOGLE_CLOUD_PROJECT
  GOOGLE_CLOUD_LOCATION: "global"  # or specific region
  AI_MODEL: "gemini-3.5-flash"
```

### Anthropic Claude via Vertex AI

Uses Google Cloud ADC for authentication — no API key needed. On GCE, GKE, or Cloud Run, the SDK auto-discovers credentials from the metadata server, so no key file is required. For other environments, set `GOOGLE_APPLICATION_CREDENTIALS` as a **File** type CI/CD variable containing your service account JSON key. **Base64-encode the JSON before storing** so the value can be masked — see the [Gemini Vertex AI](#google-gemini-via-vertex-ai) section above for details. Plain JSON is also accepted but cannot be masked.

```yaml
variables:
  AI_PROVIDER: "anthropic-vertex"
  ANTHROPIC_VERTEX_PROJECT_ID: $ANTHROPIC_VERTEX_PROJECT_ID
  GOOGLE_CLOUD_LOCATION: "global"
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

| Variable | Masked | Protected | Expand | Notes |
|----------|--------|-----------|--------|-------|
| `GEMINI_API_KEY` | **Yes** | No | **Yes** | AI provider key |
| `OPENAI_API_KEY` | **Yes** | No | **Yes** | AI provider key |
| `ANTHROPIC_API_KEY` | **Yes** | No | **Yes** | AI provider key |
| `CONTEXT7_API_KEY` | **Yes** | No | **Yes** | MCP tool authentication |
| `SLACK_WEBHOOK_URL` | **Yes** | Optional | **Yes** | Notification webhook |
| `GITLAB_TOKEN` | **Yes** | No | **Yes** | Project or Group Access Token with `api` scope — required for MR diff access and comment posting (see [GitLab API Token](#gitlab-api-token)) |
| `ANTHROPIC_VERTEX_PROJECT_ID` | **Yes** | No | **Yes** | GCP project ID for Vertex AI Claude |
| `GOOGLE_CLOUD_PROJECT` | **Yes** | No | **Yes** | GCP project ID for Vertex AI Gemini |
| `GOOGLE_CLOUD_LOCATION` | No | Optional | **Yes** | GCP region for Vertex AI (defaults to `global`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | **File** + **Masked** | No | **Yes** | GCP service account JSON key — optional for Workload Identity / GKE environments (SDK uses metadata server). **Base64-encode recommended** (`base64 -w0 < key.json`) so it can be masked; plain JSON accepted but cannot be masked. Store at group level to limit access to admins |
| `CI_JOB_TOKEN` | Auto | Auto | Auto | Provided and masked by GitLab automatically — no setup needed |

- **Masked** — hides values from job logs. Always enable for secrets.
- **Protected** — restricts the variable to protected branches/tags only. Must be **unchecked** for variables used in MR pipelines, since MR source branches are typically not protected.
- **Expand variable reference** — controls whether `$` references *within the variable's own value* are expanded. Leave checked (default) for most variables. Only uncheck if a secret contains a literal `$` that should not be interpreted as a variable reference.
- **Security trade-off**: Unchecking **Protect variable** is required for MR pipelines but means any user who can push a branch and modify `.gitlab-ci.yml` could potentially access these secrets in job logs. Mitigate by using **Masked** variables, storing secrets at the **group level** (limits visibility to group admins), and enabling **Hidden** (GitLab 17.6+) where possible.
- For shared keys across multiple projects, set variables at the **group level** (**Group > Settings > CI/CD > Variables**) to avoid per-project duplication.
- Never commit `.env` files containing secrets to version control.

## Troubleshooting

### API Key Not Found

```
ERROR: AI_PROVIDER='gemini' requires GEMINI_API_KEY to be set
```

Ensure the variable is set in **Settings > CI/CD > Variables** with the "Mask variable" option checked.

### Vertex AI Credentials Error

```
ERROR: GOOGLE_APPLICATION_CREDENTIALS file is not valid JSON or base64-encoded JSON
```

The service account key must be either plain JSON or base64-encoded JSON. Re-export the key and store it as a **File** type CI/CD variable. To base64-encode: `base64 -w0 < service-account.json`.

### Literal `$VARIABLE_NAME` in Error Messages

```
Permission denied on resource project $GOOGLE_CLOUD_PROJECT
```

The CI/CD variable value is not reaching the job. The most common cause is **Protect variable** being checked — protected variables are only available on protected branches, not in MR pipelines. Uncheck it in **Settings > CI/CD > Variables**. Also verify that the variable value was actually saved (tokens are only shown once at creation time).

### Template Not Found

If using `include: remote:`, ensure the URL is accessible from your GitLab instance. Some corporate firewalls may block GitHub raw content URLs.
