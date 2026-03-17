# Task Jobs Guide

The Task Agent runs scheduled analysis and monitoring **independently** of merge requests. It uses MCP tools for infrastructure monitoring, security audits, and custom analysis.

## Quick Start

### 1. Include Template

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/redhat-community-ai-tools/cicaddy-gitlab/main/gitlab/ai_cron_template.yml'
```

### 2. Create Job

```yaml
daily_monitoring:
  extends: .ai_cron_template
  variables:
    TASK_TYPE: "custom"
    TASK_SCOPE: "external_tools"
    AI_TASK_FILE: ".gitlab/prompts/daily_monitoring.yml"
    GEMINI_API_KEY: $GEMINI_API_KEY
    SLACK_WEBHOOK_URL: $MONITORING_SLACK_WEBHOOK
    MCP_SERVERS_CONFIG: |
      [{"name": "metrics-server", "protocol": "http",
        "endpoint": "https://my-mcp-server.example.com/mcp",
        "timeout": 300, "idle_timeout": 60}]
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
```

### 3. Configure GitLab Schedule

**CI/CD → Schedules → New Schedule**: set cron pattern (e.g., `0 9 * * *`), target branch, and optional schedule variables.

## Task Scopes

| Scope | GitLab API | Use Case |
|-------|------------|----------|
| `external_tools` | Not required | Infrastructure monitoring via MCP tools |
| `full_project` | Required | Comprehensive project analysis |
| `main_branch` | Required | Main branch health |
| `recent_changes` | Required | Recent commits analysis |

## Task Types

### Custom Analysis (recommended)

Use `AI_TASK_FILE` (DSPy format) or `AI_TASK_PROMPT` (inline) with MCP tools:

```yaml
variables:
  TASK_TYPE: "custom"
  TASK_SCOPE: "external_tools"
  AI_TASK_FILE: ".gitlab/prompts/metrics_analysis.yml"
```

See [examples/prompts/](../examples/prompts/) for DSPy task file examples. `AI_TASK_FILE` takes precedence over `AI_TASK_PROMPT`.

### Built-in Types

| Type | Scope | Purpose |
|------|-------|---------|
| `security_audit` | `full_project` | Vulnerability detection, secret scanning |
| `quality_report` | `main_branch` | Code complexity, maintainability, test coverage |
| `dependency_check` | `full_project` | Vulnerable/deprecated packages |

## Schedule Examples

```yaml
# Weekly security audit (requires GitLab API)
weekly_security:
  extends: .ai_cron_template
  variables:
    TASK_TYPE: "security_audit"
    TASK_SCOPE: "full_project"
    GITLAB_TOKEN: $GITLAB_TOKEN
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule" && $SCHEDULE_NAME == "weekly_security"

# Monthly quality report
monthly_quality:
  extends: .ai_cron_template
  variables:
    TASK_TYPE: "quality_report"
    TASK_SCOPE: "full_project"
    TASK_REPORT_FORMAT: "detailed"
    GITLAB_TOKEN: $GITLAB_TOKEN
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule" && $SCHEDULE_NAME == "monthly_quality"
```

## Configuration Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TASK_TYPE` | Analysis type | `scheduled_analysis` |
| `TASK_SCOPE` | Analysis scope | `full_project` |
| `TASK_REPORT_FORMAT` | Report detail | `detailed` |
| `AI_TASK_FILE` | DSPy task file (recommended) | - |
| `AI_TASK_PROMPT` | Inline instructions | - |

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Job not triggering | Check GitLab schedule config and `rules` |
| GitLab API errors | Set `GITLAB_TOKEN` for project-dependent scopes |
| MCP timeouts | Increase `timeout`/`idle_timeout` in MCP config |
| Slack not sent | Verify webhook URL, test with manual job |

**Debug mode**: `LOG_LEVEL: "DEBUG"`, `JSON_LOGS: "true"`

**Manual test run**:
```yaml
test_cron:
  extends: .ai_cron_template
  variables:
    TASK_TYPE: "custom"
    TASK_SCOPE: "recent_changes"
  rules:
    - if: $CI_PIPELINE_SOURCE == "web"
      when: manual
```
