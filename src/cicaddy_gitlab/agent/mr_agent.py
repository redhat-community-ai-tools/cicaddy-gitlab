"""Merge Request AI Agent for code review and analysis."""

import os
from typing import Any, Dict, Optional

from cicaddy.utils.formatting_utils import CommentFormatter
from cicaddy.utils.logger import get_logger

from cicaddy_gitlab.config.settings import Settings

from .base_review_agent import BaseReviewAgent

logger = get_logger(__name__)

BOT_NOTE_MARKER = "<!-- cicaddy-gitlab:mr-review -->"


class MergeRequestAgent(BaseReviewAgent):
    """AI Agent specialized for merge request analysis and code review."""

    def __init__(self, settings: Optional[Settings] = None):
        super().__init__(settings)
        self.merge_request_iid = settings.merge_request_iid if settings else None

    async def get_diff_content(self) -> str:
        """Get merge request diff content."""
        if not self.merge_request_iid:
            raise ValueError("No merge request IID provided")

        if not self.platform_analyzer:
            raise ValueError(
                "GitLab analyzer not initialized - required for MR analysis"
            )

        logger.info(f"Getting diff for merge request {self.merge_request_iid}")

        # Use existing GitLab analyzer method for MR diff
        diff_content = await self.platform_analyzer.get_merge_request_diff(
            self.merge_request_iid,
            context_lines=self.settings.git_diff_context_lines,
            working_directory=self.settings.git_working_directory,
        )

        return diff_content

    async def get_review_context(self) -> Dict[str, Any]:
        """Get merge request specific context."""
        if not self.merge_request_iid:
            raise ValueError("No merge request IID provided")

        if not self.platform_analyzer:
            raise ValueError(
                "GitLab analyzer not initialized - required for MR analysis"
            )

        logger.info(
            f"Getting review context for merge request {self.merge_request_iid}"
        )

        # Get merge request data
        mr_data = await self.platform_analyzer.get_merge_request_data(
            self.merge_request_iid
        )

        return {
            "merge_request": mr_data,
            "analysis_type": "merge_request",
            "mr_iid": self.merge_request_iid,
        }

    def build_analysis_prompt(self, context: Dict[str, Any]) -> str:
        """
        Build analysis prompt for merge request code review.

        Supports DSPy YAML task definitions via AI_TASK_FILE environment variable.
        Falls back to built-in prompt if AI_TASK_FILE is not set.

        Args:
            context: Analysis context from get_analysis_context()

        Returns:
            String prompt for AI analysis
        """
        # Check for DSPy task file first
        task_file = os.getenv("AI_TASK_FILE")
        if task_file:
            # Inject MR-specific context into the context dict for DSPy
            mr_context = self._prepare_dspy_context(context)
            dspy_prompt = self.build_dspy_prompt(task_file, mr_context)
            if dspy_prompt:
                return dspy_prompt
            # Fall through to built-in prompt if DSPy fails

        # Get enabled tasks for this MR analysis
        enabled_tasks = self.settings.get_enabled_tasks()

        # Get available tools information with schemas
        tools_info = []
        for tool in context.get("mcp_tools", []):
            tool_info = f"- {tool['name']}: {tool.get('description', 'No description available')}"
            if "server" in tool:
                tool_info += f" (from {tool['server']} server)"

            # Add schema information if available
            if "inputSchema" in tool and tool["inputSchema"]:
                schema = tool["inputSchema"]
                if "properties" in schema:
                    params = []
                    required_params = schema.get("required", [])
                    for param_name, param_info in schema["properties"].items():
                        param_type = param_info.get("type", "unknown")
                        param_desc = param_info.get("description", "")
                        is_required = param_name in required_params
                        required_text = " (required)" if is_required else " (optional)"
                        params.append(
                            f"    {param_name} ({param_type}){required_text}: {param_desc}"
                        )

                    if params:
                        tool_info += "\n  Parameters:\n" + "\n".join(params)
                else:
                    tool_info += "\n  Parameters: No parameters required"

            tools_info.append(tool_info)

        tools_list = "\n".join(tools_info) if tools_info else "No MCP tools available"

        # Build comprehensive prompt for merge request analysis
        mr_data = context["merge_request"]
        diff_content = context["diff"]

        prompt = f"""
You are an AI agent performing merge request analysis on a GitLab project.

Project: {context.get("project", {}).get("name", "Unknown")}
Merge Request: {mr_data["title"]}
Description: {mr_data.get("description", "No description")}
Author: {mr_data.get("author", {}).get("name", "Unknown")}
Target Branch: {mr_data.get("target_branch", "Unknown")}
Source Branch: {mr_data.get("source_branch", "Unknown")}

Code Changes:
```diff
{diff_content}
```

Available MCP Tools:
{tools_list}

Enabled Analysis Tasks: {", ".join(enabled_tasks)}

Instructions:
1. Analyze the merge request and code changes thoroughly
2. For each enabled task, provide detailed analysis:
   - code_review: Focus on code quality, best practices, potential bugs
   - security_scan: Identify security vulnerabilities and risks
3. Use available MCP tools when they can provide additional insights
4. Pay attention to parameter types and requirements when calling tools
5. Provide actionable recommendations and specific code suggestions
6. Format your response clearly for GitLab merge request comments

{self._get_task_specific_instructions(enabled_tasks)}

Please provide your comprehensive analysis.
"""

        return prompt

    def _prepare_dspy_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare context dict with MR-specific data for DSPy prompt building.

        Args:
            context: Base analysis context

        Returns:
            Enriched context with MR-specific fields
        """
        mr_context = context.copy()

        # Add MR data as structured context
        mr_data = context.get("merge_request", {})
        mr_context["mr_title"] = mr_data.get("title", "Unknown")
        mr_context["mr_description"] = mr_data.get("description", "")
        mr_context["mr_author"] = mr_data.get("author", {}).get("name", "Unknown")
        mr_context["target_branch"] = mr_data.get("target_branch", "Unknown")
        mr_context["source_branch"] = mr_data.get("source_branch", "Unknown")
        mr_context["mr_iid"] = self.merge_request_iid

        # Add diff content
        mr_context["diff_content"] = context.get("diff", "")

        # Add enabled tasks
        mr_context["enabled_tasks"] = self.settings.get_enabled_tasks()

        return mr_context

    def _get_task_specific_instructions(self, enabled_tasks: list) -> str:
        """Get task-specific instructions based on enabled tasks."""
        instructions = []

        if "code_review" in enabled_tasks:
            custom_prompt = self.settings.review_prompt
            if custom_prompt:
                instructions.append(f"Code Review Instructions: {custom_prompt}")
            else:
                instructions.append(
                    """
Code Review Focus:
- **Summary**: Briefly summarize the changes
- **Issues**: Identify bugs, logic errors, edge cases, security vulnerabilities
- **Recommendations**: Suggest concrete fixes and improvements
- **Code Quality**: Assess readability, maintainability, best practices
"""
                )

        if "security_scan" in enabled_tasks:
            instructions.append(
                """
Security Analysis Focus:
- **Vulnerabilities**: Identify security issues (injection, auth, crypto, etc.)
- **Attack Vectors**: Describe potential attack scenarios
- **Risk Assessment**: Rate severity (Critical/High/Medium/Low)
- **Mitigation**: Provide specific security fixes
"""
            )

        return "\n".join(instructions)

    async def send_notifications(
        self, report: Dict[str, Any], analysis_result: Dict[str, Any]
    ):
        """Send notifications via GitLab comment and Slack."""
        try:
            # Post results to GitLab MR
            await self._post_gitlab_comment(report, analysis_result)
            logger.info(f"Posted analysis to GitLab MR {self.merge_request_iid}")

        except Exception as e:
            logger.error(f"Failed to post GitLab comment: {e}", exc_info=True)

        # Send Slack notification using parent class method
        await super().send_notifications(report, analysis_result)

    async def _post_gitlab_comment(
        self, report: Dict[str, Any], analysis_result: Dict[str, Any]
    ):
        """Post analysis results as GitLab merge request comment."""
        if not self.platform_analyzer:
            logger.warning("GitLab analyzer not available - skipping comment posting")
            return

        # Format results for GitLab comment
        comment = self._format_gitlab_comment(report, analysis_result)

        # Post to GitLab (updates existing bot note in-place if found)
        await self.platform_analyzer.post_merge_request_note(
            self.merge_request_iid, comment, note_marker=BOT_NOTE_MARKER
        )

    def _extract_token_summary(self, analysis_result: Dict[str, Any]) -> str:
        """
        Extract and format AI token usage summary from analysis result.

        Args:
            analysis_result: The analysis result containing execution data

        Returns:
            Formatted string with token usage information, or empty string if no data
        """
        try:
            from cicaddy.utils.token_utils import TokenUsageExtractor

            # Use the base class method to aggregate token usage
            token_data = self._aggregate_token_usage(analysis_result)

            # Use shared formatting utility for detailed format
            return TokenUsageExtractor.format_detailed_usage(token_data)

        except Exception as e:
            logger.debug(f"Failed to extract token summary: {e}")

        return ""

    def _get_html_artifact_url(self, report_id: str, agent_type: str = "mr") -> str:
        """
        Generate GitLab CI artifact URL for HTML report.

        Args:
            report_id: Report identifier (turn_id)
            agent_type: Agent type for filename (default: "mr")

        Returns:
            GitLab artifact URL or empty string if not in CI environment
        """
        ci_server_url = os.getenv("CI_SERVER_URL")
        ci_project_path = os.getenv("CI_PROJECT_PATH")
        ci_job_id = os.getenv("CI_JOB_ID")

        if ci_server_url and ci_project_path and ci_job_id:
            # GitLab artifact URL format:
            # https://gitlab.com/project/path/-/jobs/12345/artifacts/file/mr_20250827_213801.html
            html_filename = f"{report_id}.html"
            return f"{ci_server_url}/{ci_project_path}/-/jobs/{ci_job_id}/artifacts/file/{html_filename}"

        return ""

    def _format_gitlab_comment(
        self, report: Dict[str, Any], analysis_result: Dict[str, Any]
    ) -> str:
        """Format analysis results as GitLab comment.

        The hidden marker is prepended so the bot can find and update its
        own note later.  No heading is injected — the AI analysis output
        already contains its own structure.
        """
        comment = f"{BOT_NOTE_MARKER}\n"

        if "ai_analysis" in analysis_result:
            # New execution engine format
            ai_analysis = analysis_result["ai_analysis"]
            comment += ai_analysis + "\n\n"

            # Add execution details if available
            comment += CommentFormatter.format_new_execution_details(analysis_result)

        else:
            # Legacy format compatibility
            comment += CommentFormatter.format_analysis_sections(analysis_result)

        # Add HTML report link if running in CI
        report_id = report.get("report_id", "")
        if report_id and os.getenv("CI_JOB_ID"):
            html_url = self._get_html_artifact_url(report_id, "mr")
            if html_url:
                comment += f"\n📊 **[View Full HTML Report]({html_url})**\n"

        # Add footer with token usage information
        footer = "🤖 Generated with cicaddy-gitlab AI Agent"

        # Add token usage summary if available
        token_summary = self._extract_token_summary(analysis_result)
        if token_summary.strip():  # Ensure it's not empty or whitespace-only
            footer += f"  \n{token_summary}"

        comment += f"\n<!-- cicaddy-footer -->\n---\n{footer}"
        return comment

    def get_session_id(self) -> str:
        """
        Get unique session ID for this MR analysis session.

        Returns:
            String session identifier based on MR IID
        """
        return f"mr_{self.merge_request_iid or 'unknown'}"

    async def process_merge_request(self) -> Dict[str, Any]:
        """
        Main entry point for processing merge requests.

        This is a convenience method that calls the base analyze() method
        and returns the results in the expected format.

        Returns:
            Dict containing analysis results and execution metadata
        """
        if not self.merge_request_iid:
            raise ValueError("No merge request IID provided")

        logger.info("Processing merge request %s", self.merge_request_iid)

        # Initialize all components (GitLab analyzer, MCP, etc.)
        await self.initialize()

        # Use the base class analyze method which implements the full pipeline
        result = await self.analyze()

        # Return in expected format for backwards compatibility
        return result["analysis_result"]

    async def generate_report(
        self, analysis_result: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate formatted report with MR-specific information."""
        # Use base class report generation
        report = await super().generate_report(analysis_result, context)

        # Add MR-specific metadata for notifications
        if "merge_request" in context:
            report["merge_request"] = context["merge_request"]

        return report
