---
name: cicaddy-gitlab
description: >
  Use this skill when working with the Cicaddy GitLab plugin — the platform-specific
  extension for GitLab CI/CD integration. Covers GitLab CI templates, merge request
  and branch review agents, GitLab settings, plugin registration, and DSPy task files
  for GitLab-based code review workflows.
---

# Cicaddy GitLab Plugin

Cicaddy-GitLab is the GitLab platform plugin for the cicaddy AI agent library.
It provides merge request analysis, branch review, GitLab API integration, and
reusable GitLab CI templates that can be included in any project's `.gitlab-ci.yml`.

## GitLab CI Templates

Two reusable CI templates live in `gitlab/`:

### Merge Request Agent (`ai_agent_template.yml`)

For AI-powered code review on merge requests. Include in your `.gitlab-ci.yml`:

```yaml
include:
  - remote: 'https://raw.githubusercontent.com/waynesun09/cicaddy-gitlab/main/gitlab/ai_agent_template.yml'

ai_code_review:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini"           # gemini | openai | claude
    GEMINI_API_KEY: $GEMINI_API_KEY
    SLACK_WEBHOOK_URL: $SLACK_WEBHOOK_URL
```

Key template variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_PROVIDER` | `gemini` | AI provider to use |
| `AI_MODEL` | `gemini-3-flash-preview` | Model name |
| `AGENT_TASKS` | `code_review` | Comma-separated task list |
| `AI_TASK_FILE` | `""` | DSPy task YAML path (overrides AI_TASK_PROMPT) |
| `AI_TASK_PROMPT` | *(built-in review prompt)* | Inline task prompt |
| `MCP_SERVERS_CONFIG` | `[]` | JSON array of MCP server configs |
| `MAX_INFER_ITERS` | `15` | Max inference iterations |
| `GIT_DIFF_CONTEXT_LINES` | `10` | Lines of context in diffs |
| `SLACK_WEBHOOK_URL` | `""` | Slack notification webhook |

Rules: runs on `merge_request_event` by default, manual on `web` trigger.

#### Branch review variant

```yaml
ai_branch_review:
  extends: .ai_agent_template
  variables:
    AGENT_TYPE: "branch_review"
    AI_PROVIDER: "gemini"
    GEMINI_API_KEY: $GEMINI_API_KEY
    BRANCH_REVIEW_TARGET_BRANCH: "main"
  rules:
    - if: $CI_PIPELINE_SOURCE == "push" && $CI_COMMIT_BRANCH != $CI_DEFAULT_BRANCH
      variables:
        GIT_STRATEGY: clone
        GIT_DEPTH: 0
```

#### DSPy task file variant

```yaml
ai_code_review_dspy:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini"
    GEMINI_API_KEY: $GEMINI_API_KEY
    AI_TASK_FILE: ".gitlab/prompts/mr_code_review.yml"
```

### Scheduled/Cron Agent (`ai_cron_template.yml`)

For scheduled jobs with MCP tool servers (monitoring, reports, audits):

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
        "endpoint": "https://my-mcp.example.com/mcp",
        "timeout": 300, "idle_timeout": 60}]
    AI_TASK_PROMPT: |
      Use MCP tools to analyze system data and generate a report.
    SLACK_WEBHOOK_URL: $SLACK_WEBHOOK_URL
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
```

Additional cron-specific variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TASK_TYPE` | `custom` | `security_audit`, `quality_report`, `dependency_check`, `custom` |
| `TASK_SCOPE` | `external_tools` | `full_project`, `main_branch`, `recent_changes`, `external_tools` |
| `MAX_INFER_ITERS` | `30` | Higher default for complex analysis |
| `MAX_EXECUTION_TIME` | `600` | Seconds (range: 60–7200) |
| `RECOVERY_ENABLED` | `true` | Early break recovery for long runs |
| `JSON_LOGS` | `true` | Structured logging for scheduled jobs |

Rules: runs on `schedule` by default, manual on `web` trigger. Timeout: 2h.

---

## GitLab Environment Variables

The plugin reads standard GitLab CI variables automatically:

| Variable | Source | Description |
|----------|--------|-------------|
| `GITLAB_TOKEN` | User-set | GitLab API token (enhanced permissions) |
| `CI_JOB_TOKEN` | GitLab CI | Fallback token (auto-provided in CI) |
| `CI_API_V4_URL` | GitLab CI | API base URL (auto-constructed from `CI_SERVER_URL`) |
| `CI_PROJECT_ID` | GitLab CI | Project ID (or extracted from `CI_PROJECT_URL`) |
| `CI_PROJECT_URL` | User-set | GitLab project URL (fallback for project ID) |
| `CI_MERGE_REQUEST_IID` | GitLab CI | MR IID (triggers MR agent auto-detection) |
| `CI_DEFAULT_BRANCH` | GitLab CI | Default branch name |
| `CI_PROJECT_NAME` | GitLab CI | Project name |
| `CI_PROJECT_NAMESPACE` | GitLab CI | Project namespace/group |
| `CI_MERGE_REQUEST_TITLE` | GitLab CI | MR title |
| `GITLAB_USER_NAME` | GitLab CI | User who triggered the pipeline |

---

## Plugin Architecture

### Entry points (registered in `pyproject.toml`)

```toml
[project.entry-points."cicaddy.agents"]
gitlab = "cicaddy_gitlab.plugin:register_agents"

[project.entry-points."cicaddy.settings_loader"]
gitlab = "cicaddy_gitlab.config.settings:load_settings"
```

### Agent registration (`plugin.py`)

```python
def register_agents():
    AgentFactory.register("merge_request", MergeRequestAgent)
    AgentFactory.register("branch_review", BranchReviewAgent)
    AgentFactory.register_detector(_detect_gitlab_agent_type, priority=40)
```

### Agent type detection (`agent/factory.py`)

Auto-detects `merge_request` agent when `CI_MERGE_REQUEST_IID` is set. Detector
priority is 40 (runs before cicaddy's built-in CI detector at 50).

### Settings (`config/settings.py`)

`Settings` extends `CoreSettings` with GitLab fields. `load_settings()` handles:
- `CI_JOB_TOKEN` → `GITLAB_TOKEN` fallback
- `CI_SERVER_URL` → `CI_API_V4_URL` construction
- `CI_PROJECT_URL` → `CI_PROJECT_ID` extraction

---

## Agent Types

| Type | Class | Module | Trigger |
|------|-------|--------|---------|
| `merge_request` | `MergeRequestAgent` | `agent/mr_agent.py` | `CI_MERGE_REQUEST_IID` set |
| `branch_review` | `BranchReviewAgent` | `agent/branch_agent.py` | `AGENT_TYPE=branch_review` |

Both extend `BaseReviewAgent` (`agent/base_review_agent.py`) which extends
cicaddy's `BaseAIAgent` with `_setup_platform_integration()` for GitLab API.

---

## DSPy Task Files for GitLab

Example MR review task at `examples/prompts/mr_code_review.yml`:

```yaml
name: mr_code_review
type: code_review
version: "1.0"

inputs:
  - name: mr_title
    required: true
  - name: diff_content
    required: true
    format: diff
  - name: review_focus
    env_var: ANALYSIS_FOCUS
    default: "general"

constraints:
  - Prioritize issues by severity (Critical > High > Medium > Low)
  - Provide specific line references when identifying issues
  - Check for common security vulnerabilities

reasoning: chain_of_thought
output_format: markdown
```

Reference with `AI_TASK_FILE=".gitlab/prompts/mr_code_review.yml"` in CI variables.

---

## Exit Codes (CI template retry logic)

| Code | Meaning | Retry? |
|------|---------|--------|
| `0` | Success | — |
| `2` | AI provider temporarily unavailable | Yes (with delay) |
| `3` | Configuration error (missing API key) | No |
| Other | General failure | No |

Templates use `AI_PROVIDER_RETRY_ATTEMPTS` and `AI_PROVIDER_RETRY_DELAY_SECONDS`
for automatic retry on exit code 2.
