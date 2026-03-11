"""GitLab-specific BranchReviewAgent with commit comment posting.

The core cicaddy BranchReviewAgent handles branch review logic and Slack
notifications. This subclass re-parents it under cicaddy_gitlab's
BaseReviewAgent (which initializes GitLabAnalyzer) and adds GitLab
commit comment posting on top of the core notification behavior.

MRO: BranchReviewAgent (this) -> BaseReviewAgent (cicaddy_gitlab)
     -> BaseAIAgent (cicaddy_gitlab) -> BranchReviewAgent (cicaddy)
     -> BaseReviewAgent (cicaddy) -> BaseAIAgent (cicaddy) -> ABC
"""

import os
from typing import Any, Dict

from cicaddy.agent.branch_agent import BranchReviewAgent as CoreBranchReviewAgent
from cicaddy.utils.logger import get_logger

from cicaddy_gitlab.agent.base_review_agent import BaseReviewAgent

logger = get_logger(__name__)

BOT_NOTE_MARKER = "<!-- cicaddy-gitlab:branch-review -->"


class BranchReviewAgent(BaseReviewAgent, CoreBranchReviewAgent):
    """BranchReviewAgent with GitLab platform integration.

    Combines cicaddy core's branch review logic with GitLab's
    BaseReviewAgent for platform integration. Adds GitLab commit
    comment posting on top of core notification behavior.
    """

    async def send_notifications(
        self, report: Dict[str, Any], analysis_result: Dict[str, Any]
    ):
        """Send notifications via Slack and post GitLab commit comment."""
        logger.info(
            f"Sending notifications for branch review: "
            f"{self.source_branch} -> {self.target_branch}"
        )
        await super().send_notifications(report, analysis_result)
        await self._post_gitlab_commit_comment(report, analysis_result)

    async def _post_gitlab_commit_comment(
        self, report: Dict[str, Any], analysis_result: Dict[str, Any]
    ):
        """Post analysis results as a comment to the current commit."""
        if not self.platform_analyzer:
            logger.debug("No platform analyzer available, skipping commit comment")
            return

        commit_sha = os.getenv("CI_COMMIT_SHA")
        if not commit_sha:
            logger.debug("No CI_COMMIT_SHA available, skipping commit comment")
            return

        try:
            comment_content = self._format_gitlab_comment(report, analysis_result)
            result = await self.platform_analyzer.post_commit_note(
                commit_sha, comment_content, note_marker=BOT_NOTE_MARKER
            )
            logger.info(
                f"Posted analysis comment to commit {commit_sha[:8]}, "
                f"note ID: {result.get('id')}"
            )
        except Exception as e:
            logger.error(f"Failed to post GitLab commit comment: {e}")

    def _format_gitlab_comment(
        self, report: Dict[str, Any], analysis_result: Dict[str, Any]
    ) -> str:
        """Format analysis results for GitLab commit comment.

        The hidden marker is prepended so the bot can find and update its
        own note later.
        """
        ai_analysis = analysis_result.get("ai_analysis", "No analysis available")
        status = analysis_result.get("status", "unknown")
        execution_time = analysis_result.get("execution_time", 0)
        project_name = report.get("project", "Unknown Project")
        status_icon = "pass" if status == "success" else "fail"

        return f"""{BOT_NOTE_MARKER}
## AI Branch Analysis Results ({status_icon})

**Project:** {project_name}
**Branch:** {self.source_branch} -> {self.target_branch}
**Status:** {status.title()}
**Execution Time:** {execution_time:.1f}s
**Report ID:** `{report.get("report_id", "unknown")}`

### Analysis Summary

{ai_analysis}

<!-- cicaddy-footer -->
---
*Analysis by cicaddy-gitlab AI Agent | Report: `{report.get("report_id", "N/A")}`*
"""
