"""Configuration for Pipeline AI Agent (GitLab-specific extension of cicaddy)."""

import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from pydantic import AliasChoices, Field
from pydantic_settings import SettingsConfigDict

from cicaddy.config.settings import (  # noqa: F401
    CoreSettings,
    MCPServerConfig,
    SENSITIVE_ENV_VAR_NAMES,
    _SENSITIVE_FIELD_NAMES,
    load_core_settings,
)

# Use standard logging for settings module to avoid circular imports
logger = logging.getLogger(__name__)


class Settings(CoreSettings):
    """Full application settings with GitLab CI/CD platform-specific fields.

    Extends CoreSettings with GitLab-specific configuration such as
    tokens, project IDs, merge request IIDs, and other CI variables.
    """

    model_config = SettingsConfigDict(extra="ignore")

    # GitLab configuration (uses built-in CI variables with optional overrides)
    gitlab_token: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GITLAB_TOKEN", "CI_JOB_TOKEN"
        ),  # Custom token with enhanced permissions, fallback to CI_JOB_TOKEN
        description=(
            "GitLab API token - use GITLAB_TOKEN for custom token "
            "or CI_JOB_TOKEN is available by default"
        ),
    )
    gitlab_api_url: str = Field(default="", validation_alias="CI_API_V4_URL")
    project_id: Optional[str] = Field(default=None, validation_alias="CI_PROJECT_ID")
    merge_request_iid: Optional[str] = Field(
        None, validation_alias="CI_MERGE_REQUEST_IID"
    )
    default_branch: str = Field("main", validation_alias="CI_DEFAULT_BRANCH")

    # Additional GitLab context variables
    project_name: str = Field(default="", validation_alias="CI_PROJECT_NAME")
    project_namespace: str = Field(default="", validation_alias="CI_PROJECT_NAMESPACE")
    merge_request_title: Optional[str] = Field(
        None, validation_alias="CI_MERGE_REQUEST_TITLE"
    )
    gitlab_user_name: Optional[str] = Field(None, validation_alias="GITLAB_USER_NAME")


def load_settings() -> Settings:
    """Load settings from environment variables with GitLab CI defaults."""

    # Use CI_JOB_TOKEN as fallback if GITLAB_TOKEN not provided
    ci_job_token = os.getenv("CI_JOB_TOKEN")
    if not os.getenv("GITLAB_TOKEN") and ci_job_token:
        os.environ["GITLAB_TOKEN"] = ci_job_token

    # Handle MCP_SERVERS_CONFIG - default to empty array if missing
    # Let get_mcp_servers() handle YAML/JSON parsing with proper fallbacks
    current_mcp_config = os.getenv("MCP_SERVERS_CONFIG")
    if not current_mcp_config:
        os.environ["MCP_SERVERS_CONFIG"] = "[]"

    # Set minimal defaults for required GitLab variables if missing
    if not os.getenv("CI_API_V4_URL"):
        # Check for manual override first
        manual_api_url = os.getenv("GITLAB_API_URL")
        if manual_api_url:
            os.environ["CI_API_V4_URL"] = manual_api_url
            logger.info(f"Using manual GITLAB_API_URL override: {manual_api_url}")
        else:
            # Construct API URL from CI_SERVER_URL if available (works for GitLab EE instances)
            server_url = os.getenv("CI_SERVER_URL")
            if server_url:
                # Remove trailing slash
                server_url = server_url.rstrip("/")

                # Check if /api/v4 is already present to avoid duplication
                if server_url.endswith("/api/v4"):
                    api_url = server_url
                    logger.info(f"CI_SERVER_URL already contains /api/v4: {api_url}")
                else:
                    # Append /api/v4 if not present
                    api_url = server_url + "/api/v4"
                    logger.info(
                        f"Constructed CI_API_V4_URL from CI_SERVER_URL: {api_url}"
                    )

                os.environ["CI_API_V4_URL"] = api_url
                logger.info(f"Final CI_API_V4_URL set to: {api_url}")
            else:
                # Fallback to gitlab.com (should rarely be needed)
                os.environ["CI_API_V4_URL"] = "https://gitlab.com/api/v4"
                logger.warning("CI_SERVER_URL not available, using gitlab.com fallback")

    # Handle CI_PROJECT_ID - treat empty string as unset
    project_id = os.getenv("CI_PROJECT_ID")
    if not project_id or project_id.strip() == "":
        # Remove empty CI_PROJECT_ID to ensure it's treated as None
        if "CI_PROJECT_ID" in os.environ:
            del os.environ["CI_PROJECT_ID"]

        # Try to extract project ID from CI_PROJECT_URL if available
        project_url = os.getenv("CI_PROJECT_URL")
        if project_url:
            # Extract project ID from URL like https://gitlab.com/group/project(.git) -> group/project
            try:
                # Remove the base GitLab URL and get the path
                parsed = urlparse(project_url)
                project_path = parsed.path.lstrip("/")

                # Strip .git suffix if present
                if project_path.endswith(".git"):
                    project_path = project_path[:-4]

                # Use raw path - let python-gitlab handle URL encoding
                os.environ["CI_PROJECT_ID"] = project_path
                logger.info(f"Extracted project ID from CI_PROJECT_URL: {project_path}")
            except Exception as e:
                logger.error(f"Failed to extract project ID from CI_PROJECT_URL: {e}")
                # Don't set a default - let the application handle missing project ID gracefully
                logger.warning(
                    "CI_PROJECT_ID not available - some features may not work"
                )
        else:
            logger.warning(
                "CI_PROJECT_ID and CI_PROJECT_URL not available - some features may not work"
            )

    # Explicitly pass environment variables to work around Pydantic env reading issues
    # This is needed because Pydantic's env Field parsing appears to fail in certain environments
    env_data: Dict[str, Any] = {}

    # GitLab configuration
    if os.getenv("GITLAB_TOKEN"):
        env_data["gitlab_token"] = os.getenv("GITLAB_TOKEN")
    if os.getenv("CI_API_V4_URL"):
        env_data["gitlab_api_url"] = os.getenv("CI_API_V4_URL")
    if os.getenv("CI_PROJECT_ID"):
        env_data["project_id"] = os.getenv("CI_PROJECT_ID")
    if os.getenv("CI_MERGE_REQUEST_IID"):
        env_data["merge_request_iid"] = os.getenv("CI_MERGE_REQUEST_IID")
    if os.getenv("CI_DEFAULT_BRANCH"):
        env_data["default_branch"] = os.getenv("CI_DEFAULT_BRANCH")

    # Additional GitLab context
    if os.getenv("CI_PROJECT_NAME"):
        env_data["project_name"] = os.getenv("CI_PROJECT_NAME")
    if os.getenv("CI_PROJECT_NAMESPACE"):
        env_data["project_namespace"] = os.getenv("CI_PROJECT_NAMESPACE")
    if os.getenv("CI_MERGE_REQUEST_TITLE"):
        env_data["merge_request_title"] = os.getenv("CI_MERGE_REQUEST_TITLE")
    if os.getenv("GITLAB_USER_NAME"):
        env_data["gitlab_user_name"] = os.getenv("GITLAB_USER_NAME")

    # AI provider configuration
    if os.getenv("AI_PROVIDER"):
        env_data["ai_provider"] = os.getenv("AI_PROVIDER")
    if os.getenv("AI_MODEL"):
        env_data["ai_model"] = os.getenv("AI_MODEL")
    if os.getenv("AI_RESPONSE_FORMAT"):
        env_data["ai_response_format"] = os.getenv("AI_RESPONSE_FORMAT")
    if os.getenv("AI_TEMPERATURE"):
        env_data["ai_temperature"] = os.getenv("AI_TEMPERATURE")

    # AI API keys
    if os.getenv("GEMINI_API_KEY"):
        env_data["gemini_api_key"] = os.getenv("GEMINI_API_KEY")
    if os.getenv("OPENAI_API_KEY"):
        env_data["openai_api_key"] = os.getenv("OPENAI_API_KEY")
    if os.getenv("ANTHROPIC_API_KEY"):
        env_data["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY")
    if os.getenv("AZURE_OPENAI_KEY"):
        env_data["azure_openai_key"] = os.getenv("AZURE_OPENAI_KEY")
    if os.getenv("AZURE_ENDPOINT"):
        env_data["azure_endpoint"] = os.getenv("AZURE_ENDPOINT")

    # Ollama configuration
    if os.getenv("OLLAMA_BASE_URL"):
        env_data["ollama_base_url"] = os.getenv("OLLAMA_BASE_URL")
    if os.getenv("OLLAMA_API_KEY"):
        env_data["ollama_api_key"] = os.getenv("OLLAMA_API_KEY")

    # MCP server configuration
    if os.getenv("MCP_SERVERS_CONFIG"):
        env_data["mcp_servers_config"] = os.getenv("MCP_SERVERS_CONFIG")

    # Slack configuration
    if os.getenv("SLACK_WEBHOOK_URL"):
        env_data["slack_webhook_url"] = os.getenv("SLACK_WEBHOOK_URL")
    if os.getenv("SLACK_WEBHOOK_URLS"):
        env_data["slack_webhook_urls"] = os.getenv("SLACK_WEBHOOK_URLS")

    # Email configuration
    if os.getenv("EMAIL_ENABLED", "").strip():
        env_data["email_enabled"] = os.getenv("EMAIL_ENABLED", "").lower().strip() in (
            "true",
            "1",
            "yes",
        )
    if os.getenv("EMAIL_RECIPIENTS"):
        env_data["email_recipients"] = os.getenv("EMAIL_RECIPIENTS")
    if os.getenv("SENDER_EMAIL"):
        env_data["sender_email"] = os.getenv("SENDER_EMAIL")
    if os.getenv("USE_GMAIL_API", "").strip():
        env_data["use_gmail_api"] = os.getenv("USE_GMAIL_API", "").lower().strip() in (
            "true",
            "1",
            "yes",
        )

    # Agent configuration
    if os.getenv("AGENT_TASKS"):
        env_data["agent_tasks"] = os.getenv("AGENT_TASKS")
    if os.getenv("ANALYSIS_FOCUS"):
        env_data["analysis_focus"] = os.getenv("ANALYSIS_FOCUS")
    if os.getenv("AI_TASK_PROMPT"):
        env_data["review_prompt"] = os.getenv("AI_TASK_PROMPT")
    if os.getenv("AI_TASK_FILE"):
        env_data["task_file"] = os.getenv("AI_TASK_FILE")

    # Git configuration
    git_diff_context = os.getenv("GIT_DIFF_CONTEXT_LINES")
    if git_diff_context:
        env_data["git_diff_context_lines"] = int(git_diff_context)
    if os.getenv("GIT_WORKING_DIRECTORY"):
        env_data["git_working_directory"] = os.getenv("GIT_WORKING_DIRECTORY")

    # Logging configuration
    if os.getenv("LOG_LEVEL"):
        env_data["log_level"] = os.getenv("LOG_LEVEL")
    if os.getenv("JSON_LOGS", "").strip():
        env_data["json_logs"] = os.getenv("JSON_LOGS", "").lower().strip() in (
            "true",
            "1",
            "yes",
        )

    # Report configuration
    if os.getenv("ENABLE_REPORT_CHART", "").strip():
        env_data["enable_report_chart"] = os.getenv(
            "ENABLE_REPORT_CHART", ""
        ).lower().strip() in (
            "true",
            "1",
            "yes",
        )

    # SSL configuration
    if os.getenv("SSL_VERIFY", "").strip():
        env_data["ssl_verify"] = os.getenv("SSL_VERIFY", "").lower().strip() in (
            "true",
            "1",
            "yes",
        )

    # Task configuration (support both new TASK_* and legacy CRON_* env vars)
    task_type = os.getenv("TASK_TYPE") or os.getenv("CRON_TASK_TYPE")
    if task_type:
        env_data["task_type"] = task_type
    task_scope = os.getenv("TASK_SCOPE") or os.getenv("CRON_SCOPE")
    if task_scope:
        env_data["task_scope"] = task_scope
    task_schedule = os.getenv("TASK_SCHEDULE_NAME") or os.getenv("CRON_SCHEDULE_NAME")
    if task_schedule:
        env_data["task_schedule_name"] = task_schedule

    # Local tools configuration
    if os.getenv("ENABLE_LOCAL_TOOLS", "").strip():
        env_data["enable_local_tools"] = os.getenv(
            "ENABLE_LOCAL_TOOLS", ""
        ).lower().strip() in ("true", "1", "yes")
    if os.getenv("LOCAL_TOOLS_WORKING_DIR"):
        env_data["local_tools_working_dir"] = os.getenv("LOCAL_TOOLS_WORKING_DIR")

    # Execution configuration
    max_infer_iters_str = os.getenv("MAX_INFER_ITERS")
    if max_infer_iters_str:
        try:
            max_iters_value = int(max_infer_iters_str)
            # Ensure at least 1 iteration
            env_data["max_infer_iters"] = max(1, max_iters_value)
        except ValueError:
            logger.warning(
                f"Invalid MAX_INFER_ITERS value '{max_infer_iters_str}' - "
                "must be a positive integer. Using default value 10."
            )
            env_data["max_infer_iters"] = 10

    # Execution time limits
    # Handle MAX_EXECUTION_TIME - check for empty string and invalid values
    max_exec_env = os.getenv("MAX_EXECUTION_TIME")
    if max_exec_env == "":
        # Unset environment variable if it's an empty string to prevent Pydantic validation error
        os.environ.pop("MAX_EXECUTION_TIME", None)
        logger.debug("MAX_EXECUTION_TIME was empty string, using default 600")
    elif max_exec_env:  # Not None and not empty string
        try:
            max_exec_time = int(max_exec_env)
            # Validate range [60, 7200]
            if 60 <= max_exec_time <= 7200:
                env_data["max_execution_time"] = max_exec_time
            else:
                logger.warning(
                    f"MAX_EXECUTION_TIME {max_exec_time} out of range [60, 7200], using default 600"
                )
                # Unset to use Pydantic default
                os.environ.pop("MAX_EXECUTION_TIME", None)
                env_data["max_execution_time"] = 600
        except ValueError:
            logger.warning(
                f"Invalid MAX_EXECUTION_TIME value '{max_exec_env}' - "
                "must be an integer between 60 and 7200. Using default value 600."
            )
            # Unset to prevent Pydantic from trying to parse invalid value
            os.environ.pop("MAX_EXECUTION_TIME", None)
            env_data["max_execution_time"] = 600
    # If None, environment variable not set - Pydantic will use Field default (600)

    # Token budget management
    # Handle CONTEXT_SAFETY_FACTOR - check for empty string and invalid values
    context_safety_env = os.getenv("CONTEXT_SAFETY_FACTOR")
    if context_safety_env == "":
        # Unset environment variable if it's an empty string to prevent Pydantic validation error
        # This can happen when GitLab CI variable is defined but not set
        os.environ.pop("CONTEXT_SAFETY_FACTOR", None)
        logger.debug("CONTEXT_SAFETY_FACTOR was empty string, using default 0.85")
    elif context_safety_env:  # Not None and not empty string
        try:
            safety_factor = float(context_safety_env)
            # Validate range [0.5, 0.97]
            if 0.5 <= safety_factor <= 0.97:
                env_data["context_safety_factor"] = safety_factor
            else:
                logger.warning(
                    f"CONTEXT_SAFETY_FACTOR {safety_factor} out of range [0.5, 0.97], using default 0.85"
                )
                # Unset to use Pydantic default
                os.environ.pop("CONTEXT_SAFETY_FACTOR", None)
                env_data["context_safety_factor"] = 0.85
        except ValueError:
            logger.warning(
                f"Invalid CONTEXT_SAFETY_FACTOR value '{context_safety_env}' - "
                "must be a float between 0.5 and 0.97. Using default value 0.85."
            )
            # Unset to prevent Pydantic from trying to parse invalid value
            os.environ.pop("CONTEXT_SAFETY_FACTOR", None)
            env_data["context_safety_factor"] = 0.85
    # If None, environment variable not set - Pydantic will use Field default (0.85)

    # HTML Report customization: Let Pydantic handle these via validation_alias
    # Fields: html_report_header, html_report_subheader, html_report_logo_url, html_report_logo_height

    return Settings(**env_data)
