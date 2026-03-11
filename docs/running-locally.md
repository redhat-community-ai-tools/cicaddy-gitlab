# Running Locally

This guide covers running cicaddy-gitlab outside of GitLab CI for local development and testing.

## Setup

```bash
# Install from source with dev dependencies
git clone https://github.com/redhat-community-ai-tools/cicaddy-gitlab.git
cd cicaddy-gitlab
uv pip install -e ".[dev]"

# Or with standard pip if uv is not installed
# pip install -e ".[dev]"
```

## Environment File Preparation

The CLI loads configuration from `.env` files via `--env-file`. This is the recommended approach over `source .env` because it's simpler, safer (doesn't pollute your shell), and supports `--dry-run` for verification.

### Basic Template

Copy the example and fill in your credentials:

```bash
cp .env.example .env.local
# Edit .env.local with your API key and settings
```

### Environment File Format

```bash
# Use KEY=value format (no spaces around =)
AGENT_TYPE=task
AI_PROVIDER=gemini
GEMINI_API_KEY=your-key-here

# Use single quotes for complex values (JSON, multi-line prompts)
MCP_SERVERS_CONFIG='[{"name":"server","protocol":"http","endpoint":"https://example.com/mcp"}]'

# Multi-line prompts work inside single quotes
AI_TASK_PROMPT='You are an expert analyst.

Analyze the data and provide:
- Summary of findings
- Recommendations'
```

### Task Agent Example

For scheduled analysis or custom tasks (no GitLab API needed):

```bash
# .env.task
AGENT_TYPE=task
TASK_TYPE=custom
TASK_SCOPE=external_tools

AI_PROVIDER=gemini
GEMINI_API_KEY=your-key-here

AI_TASK_PROMPT='Use MCP tools to analyze system data and generate a report.'
MCP_SERVERS_CONFIG='[{"name":"context7","protocol":"http","endpoint":"https://mcp.context7.com/mcp","timeout":300,"idle_timeout":60}]'

LOG_LEVEL=DEBUG
```

### MR Review Agent Example

For reviewing merge requests locally (requires GitLab API access):

```bash
# .env.mr
AGENT_TYPE=merge_request
CI_MERGE_REQUEST_IID=123
CI_PROJECT_ID=your-group/your-project
CI_API_V4_URL=https://gitlab.example.com/api/v4
# Requires api or read_api + read_repository scopes
GITLAB_TOKEN=your-gitlab-token-here

AI_PROVIDER=gemini
GEMINI_API_KEY=your-key-here

LOG_LEVEL=DEBUG
```

### DSPy Task File Example

For structured analysis using declarative YAML prompts:

```bash
# .env.dspy
AGENT_TYPE=task
TASK_TYPE=custom
TASK_SCOPE=external_tools

AI_PROVIDER=gemini
GEMINI_API_KEY=your-key-here

AI_TASK_FILE='.gitlab/prompts/my_analysis.yml'
MCP_SERVERS_CONFIG='[{"name":"my-server","protocol":"http","endpoint":"https://my-mcp.example.com/mcp","timeout":600,"idle_timeout":300}]'

LOG_LEVEL=DEBUG
```

## Running the Agent

```bash
# Run with env file (recommended)
uv run cicaddy run --env-file .env.local

# Override specific settings via CLI args
uv run cicaddy run --env-file .env.local --ai-provider openai --verbose

# Validate configuration before running
uv run cicaddy config show --env-file .env.local
uv run cicaddy validate --env-file .env.local
```

### CLI Options

| Option | Short | Description |
|--------|-------|-------------|
| `--env-file` | `-e` | Load environment from a .env file |
| `--agent-type` | `-t` | Set agent type (task, mr, branch) |
| `--ai-provider` | | Set AI provider (gemini, openai, claude) |
| `--verbose` | `-v` | Enable debug logging |
| `--log-level` | | Set log level (DEBUG, INFO, WARNING, ERROR) |

CLI arguments override env file values, which override shell environment variables.

## MCP Server Configuration

### HTTP Server

```bash
MCP_SERVERS_CONFIG='[{"name":"my-server","protocol":"http","endpoint":"https://example.com/mcp","timeout":300,"idle_timeout":60}]'
```

### Stdio Server (Local)

```bash
MCP_SERVERS_CONFIG='[{"name":"sourcebot","protocol":"stdio","command":"npx","args":["-y","@sourcebot/mcp@latest"],"env":{"SOURCEBOT_HOST":"https://sourcebot.example.com"},"timeout":300}]'
```

### Multiple Servers

```bash
MCP_SERVERS_CONFIG='[{"name":"context7","protocol":"http","endpoint":"https://mcp.context7.com/mcp","timeout":300},{"name":"devlake","protocol":"http","endpoint":"https://devlake.example.com/mcp","timeout":600}]'
```

### No MCP Servers

```bash
MCP_SERVERS_CONFIG='[]'
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| JSON parse error in MCP config | Incorrect quoting | Use single quotes around JSON, double quotes inside |
| `Gemini API key not provided` | Missing key in env file | Set `GEMINI_API_KEY` (or the key matching your `AI_PROVIDER`) |
| Prompt truncated | Missing closing quote | Ensure single quotes wrap entire prompt |
| Variable not substituted | Wrong syntax | Use `{{VAR_NAME}}` for prompt variable placeholders |

### Validate MCP JSON

```bash
source .env.local && echo $MCP_SERVERS_CONFIG | python -m json.tool
```

## Security

- Never commit `.env` files — they're in `.gitignore`
- Use `.env.example` / `.env.mr.example` as templates with placeholder values
- Restrict file permissions: `chmod 600 .env.*`
