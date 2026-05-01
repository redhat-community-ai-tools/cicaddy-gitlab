# cicaddy-gitlab

GitLab platform plugin for the [cicaddy](https://github.com/waynesun09/cicaddy) AI agent framework.

## Features

- **Merge Request Code Review** - AI-powered code review on GitLab merge requests with inline comments
- **Sub-Agent Delegation** - AI-powered multi-agent review with specialized sub-agents running in parallel
- **Branch Review** - Compare branch changes against main for deployment readiness analysis
- **Scheduled Analysis** - Cron-based AI analysis jobs with MCP tool integration
- **Multi-Provider AI** - Support for Gemini, OpenAI, Claude, Gemini via Vertex AI, Anthropic via Vertex AI
- **DSPy Task Files** - Declarative YAML prompt definitions for structured analysis
- **GitLab CI Templates** - Ready-to-use CI/CD templates for merge request and scheduled jobs

## Installation

```bash
pip install cicaddy-gitlab
```

This automatically installs `cicaddy` core as a dependency and registers the GitLab plugin via entry points.

## Prerequisites

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

### AI Provider Credentials

Set up your AI provider credentials as a GitLab CI/CD variable.

Using Gemini via Vertex AI as an example (recommended):

1. Create a GCP service account with the **Vertex AI User** role and export its JSON key
2. Base64-encode the key: `base64 < service-account-key.json | tr -d '\n'`
3. Go to **Settings > CI/CD > Variables** in your GitLab project
4. Add `GOOGLE_APPLICATION_CREDENTIALS` — paste the base64 string as **Value**, select **File** type, check **Mask variable**, **Hidden**, and **Expand variable reference**
5. Add `GOOGLE_CLOUD_PROJECT` — set to your GCP project ID, check **Mask variable** and **Expand variable reference**

For API key providers (`gemini`, `openai`, `claude`) or Claude via Vertex AI (`anthropic-vertex`), see [docs/getting-started.md](docs/getting-started.md) for full setup and security best practices.

## Quick Start

### Merge Request Code Review

Add to your `.gitlab-ci.yml`:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/redhat-community-ai-tools/cicaddy-gitlab/main/gitlab/ai_agent_template.yml'

ai_code_review:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini-vertex"
    GOOGLE_CLOUD_PROJECT: $GOOGLE_CLOUD_PROJECT
    DELEGATION_MODE: "auto"
    SLACK_WEBHOOK_URL: $SLACK_WEBHOOK_URL
```

The CI template sets `DELEGATION_MODE: "auto"`, which triages the diff and spawns specialist sub-agents (security, performance, etc.) in parallel. Set `DELEGATION_MODE: "none"` for single-agent review. You can add custom sub-agents to the pool alongside the defaults — see [docs/delegation.md](docs/delegation.md) for details.

#### Custom Sub-Agents

Add your own specialist reviewers by placing YAML files in `.agents/delegation/review/`:

```yaml
# .agents/delegation/review/compliance-reviewer.yaml
name: compliance-reviewer
agent_type: review
persona: compliance engineer specializing in regulatory requirements
description: Reviews changes for regulatory and compliance impact
categories: [security, configuration]
constraints:
  - Focus on regulatory compliance (SOC2, GDPR, HIPAA)
  - Flag any PII handling changes
output_sections:
  - Compliance Impact
  - Regulatory Risks
priority: 15
```

Or define agents inline via the `DELEGATION_AGENTS` CI/CD variable:

```yaml
ai_code_review:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini-vertex"
    GOOGLE_CLOUD_PROJECT: $GOOGLE_CLOUD_PROJECT
    DELEGATION_MODE: "auto"
    DELEGATION_AGENTS: >-
      [{"name": "compliance-reviewer", "agent_type": "review",
        "persona": "compliance engineer",
        "description": "Reviews regulatory and compliance impact",
        "categories": ["security", "configuration"]}]
```

Custom agents with the same name as a built-in replace it. See [docs/delegation.md](docs/delegation.md) for the full YAML format, merge precedence, and tool filtering.

### Scheduled Analysis with MCP Tools

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/redhat-community-ai-tools/cicaddy-gitlab/main/gitlab/ai_cron_template.yml'

daily_analysis:
  extends: .ai_cron_template
  variables:
    AI_PROVIDER: "gemini-vertex"
    GOOGLE_CLOUD_PROJECT: $GOOGLE_CLOUD_PROJECT
    MCP_SERVERS_CONFIG: >-
      [{"name": "my-server", "protocol": "http",
        "endpoint": "https://my-mcp-server.example.com/mcp",
        "timeout": 300, "idle_timeout": 60}]
    AI_TASK_PROMPT: |
      Use MCP tools to analyze data and generate a comprehensive report.
    SLACK_WEBHOOK_URL: $SLACK_WEBHOOK_URL
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
```

### Using DSPy Task Files

Create structured task definitions in YAML:

```yaml
# .gitlab/prompts/my_analysis.yml
name: custom_analysis
description: Custom analysis task
type: analysis
version: "1.0"

inputs:
  - name: data_source
    description: Data source to analyze
    required: true

outputs:
  - name: summary
    description: Analysis summary
    required: true
    format: paragraph

constraints:
  - Focus on actionable insights
  - Prioritize by business impact

reasoning: chain_of_thought
output_format: markdown
```

Reference it in your CI job:

```yaml
custom_analysis:
  extends: .ai_cron_template
  variables:
    AI_TASK_FILE: "../.gitlab/prompts/my_analysis.yml"
```

## CI Template Variables

### Common Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `gemini` | AI provider (gemini, openai, claude, gemini-vertex, anthropic-vertex) |
| `AI_MODEL` | `gemini-3-flash-preview` | Model to use |
| `MCP_SERVERS_CONFIG` | `[]` | JSON array of MCP server configs |
| `AI_TASK_FILE` | (empty) | Path to DSPy task YAML file |
| `AI_TASK_PROMPT` | (built-in) | Inline task prompt |
| `SLACK_WEBHOOK_URL` | (empty) | Slack webhook for notifications |
| `MAX_INFER_ITERS` | `15` | Max AI inference iterations (agent: 15, cron: 30) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### Agent Template Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_TASKS` | `code_review` | Comma-separated task list |
| `DELEGATION_MODE` | `none` | `none` (single-agent) or `auto` (multi-agent delegation). CI template sets `auto`. |
| `MAX_SUB_AGENTS` | `3` | Max concurrent sub-agents (1-10) |
| `SUB_AGENT_MAX_ITERS` | `10` | Max iterations per sub-agent (1-15) |
| `DELEGATION_AGENTS` | (empty) | JSON config for custom sub-agent definitions |
| `DELEGATION_AGENTS_DIR` | `.agents/delegation` | Directory for user-defined sub-agent YAML files |
| `TRIAGE_PROMPT` | (empty) | Custom instructions for the triage AI |
| `GIT_DIFF_CONTEXT_LINES` | `10` | Context lines in diff |
| `GIT_WORKING_DIRECTORY` | `.` | Git repo directory |

### Cron Template Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TASK_TYPE` | `custom` | Prompt template: `custom` (uses `AI_TASK_PROMPT`/`AI_TASK_FILE`), `security_audit`, `quality_report`, `dependency_check`; other values use general analysis |
| `TASK_SCOPE` | `external_tools` | Analysis scope |
| `MAX_EXECUTION_TIME` | `600` | Max execution time (seconds) |
| `CONTEXT_SAFETY_FACTOR` | `0.75` | Token budget safety factor |

## Architecture

```
cicaddy (core)          - AI agent framework with MCP support
  +-- cicaddy-gitlab    - GitLab platform plugin (this package)
```

The plugin registers with cicaddy via Python entry points:
- `cicaddy.agents` - MergeRequestAgent, BranchReviewAgent
- `cicaddy.settings_loader` - GitLab-specific settings
- `cicaddy.cli_args` - GitLab CLI arguments
- `cicaddy.validators` - GitLab configuration validation
- `cicaddy.delegation_blocked_tools` - Side-effect tools blocked for sub-agents

## Running Locally

You can run the agent outside of GitLab CI for development and testing using `.env` files.

```bash
# Install from source
git clone https://github.com/redhat-community-ai-tools/cicaddy-gitlab.git
cd cicaddy-gitlab
uv pip install -e .

# Prepare environment file
cp .env.example .env.local
# Edit .env.local with your API key and settings

# Validate configuration
uv run cicaddy config show --env-file .env.local

# Run the agent
uv run cicaddy run --env-file .env.local

# Override settings via CLI
uv run cicaddy run --env-file .env.local --ai-provider openai --verbose
```

For MR review, use `.env.mr.example` as a starting point — it includes GitLab API variables (`GITLAB_TOKEN`, `CI_MERGE_REQUEST_IID`, etc.).

See [docs/running-locally.md](docs/running-locally.md) for detailed examples including MCP server configuration, DSPy task files, and troubleshooting.

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest

# Lint and format
ruff check --fix src/ tests/
ruff format src/ tests/
```

## License

Apache License 2.0
