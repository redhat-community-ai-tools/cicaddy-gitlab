# cicaddy-gitlab

GitLab platform plugin for the [cicaddy](https://github.com/waynesun09/cicaddy) AI agent framework.

## Features

- **Merge Request Code Review** - AI-powered code review on GitLab merge requests with inline comments
- **Branch Review** - Compare branch changes against main for deployment readiness analysis
- **Scheduled Analysis** - Cron-based AI analysis jobs with MCP tool integration
- **Multi-Provider AI** - Support for Gemini, OpenAI, Claude
- **DSPy Task Files** - Declarative YAML prompt definitions for structured analysis
- **GitLab CI Templates** - Ready-to-use CI/CD templates for merge request and scheduled jobs

## Installation

```bash
pip install cicaddy-gitlab
```

This automatically installs `cicaddy` core as a dependency and registers the GitLab plugin via entry points.

## Quick Start

### Merge Request Code Review

Add to your `.gitlab-ci.yml`:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/waynesun09/cicaddy-gitlab/main/gitlab/ai_agent_template.yml'

ai_code_review:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini"
    GEMINI_API_KEY: $GEMINI_API_KEY
    SLACK_WEBHOOK_URL: $SLACK_WEBHOOK_URL
```

### Scheduled Analysis with MCP Tools

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/waynesun09/cicaddy-gitlab/main/gitlab/ai_cron_template.yml'

daily_analysis:
  extends: .ai_cron_template
  variables:
    AI_PROVIDER: "gemini"
    GEMINI_API_KEY: $GEMINI_API_KEY
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
| `AI_PROVIDER` | `gemini` | AI provider (gemini, openai, claude) |
| `AI_MODEL` | `gemini-3-flash-preview` | Model to use |
| `MCP_SERVERS_CONFIG` | `[]` | JSON array of MCP server configs |
| `AI_TASK_FILE` | (empty) | Path to DSPy task YAML file |
| `AI_TASK_PROMPT` | (built-in) | Inline task prompt |
| `SLACK_WEBHOOK_URL` | (empty) | Slack webhook for notifications |
| `MAX_INFER_ITERS` | `10`/`15` | Max AI inference iterations |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### Agent Template Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_TASKS` | `code_review` | Comma-separated task list |
| `GIT_DIFF_CONTEXT_LINES` | `10` | Context lines in diff |
| `GIT_WORKING_DIRECTORY` | `..` | Git repo directory |

### Cron Template Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TASK_TYPE` | `custom` | Task type identifier |
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

## Development

```bash
# Clone the repo
git clone https://github.com/waynesun09/cicaddy-gitlab.git
cd cicaddy-gitlab

# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/ tests/
isort src/ tests/
```

## License

Apache License 2.0
