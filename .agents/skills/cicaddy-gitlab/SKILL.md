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
  - remote: 'https://raw.githubusercontent.com/redhat-community-ai-tools/cicaddy-gitlab/main/gitlab/ai_agent_template.yml'

ai_code_review:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini"           # gemini | openai | claude | anthropic-vertex
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
  - remote: 'https://raw.githubusercontent.com/redhat-community-ai-tools/cicaddy-gitlab/main/gitlab/ai_cron_template.yml'

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
| `TASK_TYPE` | `custom` | Prompt template: `custom` (uses `AI_TASK_PROMPT`/`AI_TASK_FILE`), `security_audit`, `quality_report`, `dependency_check`; other values use general analysis |
| `TASK_SCOPE` | `external_tools` | `full_project`, `main_branch`, `recent_changes`, `external_tools` |
| `MAX_INFER_ITERS` | `30` | Higher default for complex analysis |
| `MAX_EXECUTION_TIME` | `600` | Seconds (range: 60–7200) |
| `RECOVERY_ENABLED` | `true` | Early break recovery for long runs |
| `CONTEXT_SAFETY_FACTOR` | `0.75` | Token budget safety factor (range: 0.5–0.97) |
| `JSON_LOGS` | `true` | Structured logging for scheduled jobs |

Rules: runs on `schedule` by default, manual on `web` trigger. Timeout: 2h.

---

## GitLab Environment Variables

The plugin reads standard GitLab CI variables automatically:

| Variable | Source | Description |
|----------|--------|-------------|
| `GITLAB_TOKEN` | User-set | GitLab API token (enhanced permissions) |
| `CI_JOB_TOKEN` | GitLab CI | Fallback token (auto-provided in CI) |
| `GITLAB_API_URL` | User-set | Manual override for GitLab API endpoint |
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

Auto-detects agent type from GitLab CI environment variables. Detector priority
is 40 (runs before cicaddy's built-in CI detector at 50). Detects:
- `merge_request` — from `CI_MERGE_REQUEST_IID` or `CI_PIPELINE_SOURCE=merge_request_event`
- `task` — from `TASK_TYPE`/`CRON_TASK_TYPE` or `CI_PIPELINE_SOURCE=schedule`
- `branch_review` — from `CI_PIPELINE_SOURCE=push` to non-default branch

### Settings (`config/settings.py`)

`Settings` extends `CoreSettings` with GitLab fields. `load_settings()` handles:
- `CI_JOB_TOKEN` → `GITLAB_TOKEN` fallback
- `CI_SERVER_URL` → `CI_API_V4_URL` construction
- `CI_PROJECT_URL` → `CI_PROJECT_ID` extraction

---

## Agent Types

| Type | Class | Module | Trigger |
|------|-------|--------|---------|
| `merge_request` | `MergeRequestAgent` | `agent/mr_agent.py` | `CI_MERGE_REQUEST_IID` set or `CI_PIPELINE_SOURCE=merge_request_event` |
| `branch_review` | `BranchReviewAgent` | `agent/branch_agent.py` | `AGENT_TYPE=branch_review` or push to non-default branch |
| `task` | `TaskAgent` (cicaddy core) | cicaddy `agent/task_agent.py` | `CI_PIPELINE_SOURCE=schedule` or `TASK_TYPE`/`CRON_TASK_TYPE` set |

`MergeRequestAgent` and `BranchReviewAgent` extend `BaseReviewAgent` (`agent/base_review_agent.py`)
which extends cicaddy's `BaseAIAgent` with `_setup_platform_integration()` for GitLab API.
`TaskAgent` is provided by cicaddy core and does not require GitLab API access.

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

outputs:
  - name: summary
    required: true
    format: paragraph
  - name: issues
    required: true
    format: list
  # ... see examples/prompts/ for full file with tools, context, examples

constraints:
  - Prioritize issues by severity (Critical > High > Medium > Low)
  - Provide specific line references when identifying issues
  - Check for common security vulnerabilities

reasoning: chain_of_thought
output_format: markdown
```

Reference with `AI_TASK_FILE=".gitlab/prompts/mr_code_review.yml"` in CI variables.

---

## Running Locally

Run the agent outside GitLab CI using `.env` files and the cicaddy CLI.

```bash
# Install and prepare env file
uv pip install -e .
cp .env.example .env.local   # task agent template
cp .env.mr.example .env.mr   # MR review template

# Validate and run
uv run cicaddy config show --env-file .env.local
uv run cicaddy run --env-file .env.local

# Override settings via CLI
uv run cicaddy run --env-file .env.local --ai-provider openai --verbose
```

Key env file rules:
- Use `KEY=value` (no spaces around `=`)
- Use single quotes for JSON and multi-line values: `MCP_SERVERS_CONFIG='[...]'`
- `AI_TASK_FILE` (DSPy YAML) is recommended over `AI_TASK_PROMPT` for complex tasks

See [docs/running-locally.md](../../../docs/running-locally.md) for full examples.

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

---

## Sub-Agent Delegation

cicaddy-gitlab v0.4.0+ supports AI-powered sub-agent delegation via cicaddy>=0.8.0.

### How It Works

When `DELEGATION_MODE=auto` is set in GitLab CI or the environment, the parent agent
delegates to specialized sub-agents:

1. **Triage AI call** — analyzes the MR diff and selects relevant specialist reviewers
2. **Parallel execution** — selected sub-agents run concurrently with focused prompts
3. **Aggregation** — results merged into a single MR comment with per-agent sections

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DELEGATION_MODE` | `none` | `none` (single-agent) or `auto` (multi-agent) |
| `MAX_SUB_AGENTS` | `3` | Max concurrent sub-agents (1-10) |
| `SUB_AGENT_MAX_ITERS` | `5` | Iterations per sub-agent (1-15) |
| `DELEGATION_AGENTS_DIR` | `.agents/delegation` | Custom agent YAML directory |
| `TRIAGE_PROMPT` | (empty) | Custom triage instructions |

CLI flags:
```bash
cicaddy run --env-file .env.mr --delegation-mode auto --max-sub-agents 2
```

### GitLab CI Example

```yaml
ai_delegated_review:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini"
    GEMINI_API_KEY: $GEMINI_API_KEY
    DELEGATION_MODE: "auto"
    MAX_SUB_AGENTS: "3"
```

### Plugin Hooks

The cicaddy-gitlab plugin provides:

- **`cicaddy.delegation_blocked_tools` entry point** — blocks GitLab write operations
  (posting MR notes, merging MRs, managing labels, creating pipelines, etc.) so that
  sub-agents only perform analysis and cannot modify the GitLab state

- **Delegation metadata in MR comments** — when delegation is active, the MR comment
  includes a collapsible `<details>` block showing:
  - Number of sub-agents that succeeded/failed
  - Total execution time
  - Sub-agent names and triage rationale

### Built-in Sub-Agents

For MR review (`merge_request` and `branch_review` agent types):

- `security-reviewer` — auth, crypto, secrets, injection, access control
- `architecture-reviewer` — design patterns, module boundaries, interfaces
- `api-reviewer` — endpoints, schemas, versioning, backward compat
- `database-reviewer` — queries, migrations, schema changes, indexes
- `ui-reviewer` — frontend components, accessibility, UX
- `devops-reviewer` — CI/CD pipelines, Docker, deployment configs
- `performance-reviewer` — algorithms, caching, concurrency, resource usage
- `general-reviewer` — catch-all for anything not covered above

For scheduled tasks (`task` agent type):

- `data-analyst` — data processing, statistics, pattern recognition
- `report-writer` — report generation, formatting, documentation
- `general-task` — general-purpose catch-all

### Custom Sub-Agents

Define custom sub-agents in `.agents/delegation/review/` or `task/` using YAML:

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
priority: 15
```

Or via `DELEGATION_AGENTS` environment variable (JSON array).

See [docs/delegation.md](../../../docs/delegation.md) and cicaddy's [sub-agent delegation docs](https://github.com/waynesun09/cicaddy/blob/main/docs/sub-agent-delegation.md) for full details.
