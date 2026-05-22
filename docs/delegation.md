# Sub-Agent Delegation

cicaddy-gitlab v0.5.1+ supports AI-powered sub-agent delegation via cicaddy>=0.8.0. Instead of a single AI pass, the framework uses a triage AI to select specialized sub-agents that run in parallel.

## How It Works

1. **Triage** — An AI call analyzes the MR diff and context, then selects which sub-agents to activate from the registry
2. **Parallel Execution** — Selected sub-agents run concurrently with focused prompts, filtered tools, and divided token budgets
3. **Aggregation** — Results are merged into a unified MR comment with per-agent sections

Sub-agents share the parent's MCP connections and tool registry. Side-effect tools (posting MR notes, merging, etc.) are blocked via the `cicaddy.delegation_blocked_tools` entry point.

## Quick Start

### GitLab CI

Add `DELEGATION_MODE` and `MAX_SUB_AGENTS` to your CI job:

```yaml
ai_delegated_review:
  extends: .ai_agent_template
  variables:
    AI_PROVIDER: "gemini"
    GEMINI_API_KEY: $GEMINI_API_KEY
    DELEGATION_MODE: "auto"
    MAX_SUB_AGENTS: "3"
```

### Running Locally

```bash
# Add to your .env file:
DELEGATION_MODE=auto
MAX_SUB_AGENTS=3

# Or use CLI flags:
uv run cicaddy run --env-file .env.mr --delegation-mode auto --max-sub-agents 2
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DELEGATION_MODE` | `none` | `none` (single-agent) or `auto` (AI-powered delegation). CI template sets `auto`. |
| `MAX_SUB_AGENTS` | `3` | Maximum concurrent sub-agents (1-10) |
| `SUB_AGENT_MAX_ITERS` | `10` | Max inference iterations per sub-agent (1-15) |
| `DELEGATION_AGENTS_DIR` | `.agents/delegation` | Directory for user-defined sub-agent YAML files |
| `DELEGATION_AGENTS` | (empty) | JSON config for inline custom sub-agent definitions |
| `DELEGATION_VERIFY_FINDINGS` | `false` | Verify findings against diff before posting (core cicaddy setting) |
| `TRIAGE_PROMPT` | (empty) | Optional custom instructions for the triage AI |
| `POST_MR_COMMENT` | `true` | Post summary comment on the MR |
| `INLINE_REVIEW_COMMENTS` | `false` | Post findings as inline comments on diff lines |

### CLI Flags

```bash
cicaddy run --env-file .env --delegation-mode auto --max-sub-agents 2
```

These override the corresponding environment variables.

## Built-in Sub-Agents

### Review Agents

Activated automatically for MR code review (`merge_request` and `branch_review` agent types):

| Agent | Focus Areas |
|-------|-------------|
| `security-reviewer` | Auth, crypto, secrets, injection, access control |
| `architecture-reviewer` | Design patterns, module boundaries, interfaces |
| `api-reviewer` | Endpoints, schemas, versioning, backward compat |
| `database-reviewer` | Queries, migrations, schema changes, indexes |
| `ui-reviewer` | Frontend components, accessibility, UX |
| `devops-reviewer` | CI/CD pipelines, Docker, deployment configs |
| `performance-reviewer` | Algorithms, caching, concurrency, resource usage |
| `general-reviewer` | Catch-all for anything not covered above |

### Task Agents

Activated for scheduled jobs (`task` agent type):

| Agent | Focus Areas |
|-------|-------------|
| `data-analyst` | Data processing, statistics, pattern recognition |
| `report-writer` | Report generation, formatting, documentation |
| `general-task` | General-purpose catch-all |

## Custom Sub-Agents

### YAML Files

Place YAML files in `.agents/delegation/review/` (or `task/`) in your project:

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
  - Check audit logging requirements
output_sections:
  - Compliance Impact
  - Regulatory Risks
  - Required Controls
priority: 15
```

### JSON Inline

Define agents via the `DELEGATION_AGENTS` environment variable:

```bash
DELEGATION_AGENTS='[{"name": "compliance-reviewer", "agent_type": "review", "persona": "compliance engineer", "description": "Reviews compliance impact", "categories": ["security"]}]'
```

### Merge Precedence

1. Built-in agents (lowest priority)
2. User YAML files from `DELEGATION_AGENTS_DIR`
3. `DELEGATION_AGENTS` JSON overrides (highest priority)

User-defined agents with the same name as a built-in agent replace it.

## Tool Filtering

Sub-agents receive a filtered subset of the parent's tools:

1. **Base blocked**: `delegate_task` (prevents recursive delegation)
2. **Plugin blocked**: cicaddy-gitlab registers GitLab write operations (posting notes, merging MRs, managing labels, creating pipelines, etc.)
3. **Per-agent**: `SubAgentSpec.allowed_tools` (strict whitelist) and `blocked_tools` (additional blocks)

## MR Comment Output

When delegation is active, the MR comment includes a collapsible details block showing:
- Number of agents that succeeded/failed
- Total execution time
- Agent names and triage rationale

## DSPy Task Files + Delegation

When using `AI_TASK_FILE` with `DELEGATION_MODE=auto`, the task definition is provided to the triage agent as context for task-aware sub-agent selection. The task's `forbidden_tools` cascade to all sub-agents.

## Cost Considerations

Delegation multiplies AI inference calls. With defaults (`MAX_SUB_AGENTS=3`, `SUB_AGENT_MAX_ITERS=10`), a single MR review can use up to 1 (triage) + 3×10 (sub-agents) + 1 (aggregation) = **32 AI calls** versus 1-15 for single-agent mode. Tune `MAX_SUB_AGENTS` and `SUB_AGENT_MAX_ITERS` based on your AI provider tier and rate limits.

## Troubleshooting

- **Disable delegation**: Set `DELEGATION_MODE=none` in your CI variables — no redeployment needed
- **Sub-agent failures**: If sub-agents fail, the parent agent still posts a comment with results from successful agents. Failed agent count is shown in the delegation details block
- **Rate limits**: With `MAX_SUB_AGENTS` concurrent API calls, shared API keys may hit RPM limits. Reduce `MAX_SUB_AGENTS` if you see rate-limit errors

See cicaddy's [sub-agent delegation docs](https://github.com/waynesun09/cicaddy/blob/main/docs/sub-agent-delegation.md) for the full specification.
