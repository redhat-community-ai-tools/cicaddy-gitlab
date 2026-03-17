"""GitLab-specific BranchReviewAgent with MR/commit comment posting.

The core cicaddy BranchReviewAgent handles branch review logic and Slack
notifications. This subclass re-parents it under cicaddy_gitlab's
BaseReviewAgent (which initializes GitLabAnalyzer) and adds GitLab
comment posting on top of the core notification behavior.

When an MR is associated with the branch (CI_MERGE_REQUEST_IID is set),
the analysis is posted as an MR note — the same edit-in-place behavior
used by the MR code review agent.  This keeps all branch analyses in a
single, continuously updated comment with previous analyses collapsed.
When no MR exists, falls back to posting on the commit.

MRO: BranchReviewAgent (this) -> BaseReviewAgent (cicaddy_gitlab)
     -> BaseAIAgent (cicaddy_gitlab) -> BranchReviewAgent (cicaddy)
     -> BaseReviewAgent (cicaddy) -> BaseAIAgent (cicaddy) -> ABC
"""

import os
from typing import Any, Dict

from cicaddy.agent.branch_agent import BranchReviewAgent as CoreBranchReviewAgent
from cicaddy.utils.formatting_utils import CommentFormatter
from cicaddy.utils.logger import get_logger

from cicaddy_gitlab.agent.base_review_agent import BaseReviewAgent

logger = get_logger(__name__)

BOT_NOTE_MARKER = "<!-- cicaddy-gitlab:branch-review -->"


class BranchReviewAgent(BaseReviewAgent, CoreBranchReviewAgent):
    """BranchReviewAgent with GitLab platform integration.

    Combines cicaddy core's branch review logic with GitLab's
    BaseReviewAgent for platform integration. Posts analysis as an
    MR note (edit-in-place) when an MR exists, otherwise falls back
    to commit comments.
    """

    async def send_notifications(
        self, report: Dict[str, Any], analysis_result: Dict[str, Any]
    ):
        """Send notifications via Slack and post GitLab comment."""
        logger.info(
            f"Sending notifications for branch review: "
            f"{self.source_branch} -> {self.target_branch}"
        )
        await super().send_notifications(report, analysis_result)
        await self._post_gitlab_comment(report, analysis_result)

    async def _post_gitlab_comment(
        self, report: Dict[str, Any], analysis_result: Dict[str, Any]
    ):
        """Post analysis results as a GitLab comment.

        Prefers posting as an MR note (edit-in-place with history
        collapsing) when a merge request IID is available.  Falls back
        to commit comments when no MR context exists.
        """
        if not self.platform_analyzer:
            logger.debug("No platform analyzer available, skipping comment")
            return

        comment_content = self._format_gitlab_comment(report, analysis_result)
        mr_iid = getattr(self.settings, "merge_request_iid", None)

        if mr_iid:
            try:
                result = await self.platform_analyzer.post_merge_request_note(
                    mr_iid, comment_content, note_marker=BOT_NOTE_MARKER
                )
                logger.info(
                    f"Posted branch analysis to MR {mr_iid}, "
                    f"note ID: {result.get('id')}"
                )
                return
            except Exception as e:
                logger.error(
                    f"Failed to post MR note, falling back to commit comment: {e}"
                )

        # Fallback: post on the commit
        commit_sha = os.getenv("CI_COMMIT_SHA")
        if not commit_sha:
            logger.debug("No CI_COMMIT_SHA available, skipping commit comment")
            return

        try:
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
        """Format analysis results for GitLab comment.

        Uses the same format as the MR code review agent: the hidden
        marker is prepended, the AI analysis is included directly, and
        execution details are appended via CommentFormatter.
        """
        comment = f"{BOT_NOTE_MARKER}\n"

        if "ai_analysis" in analysis_result:
            ai_analysis = analysis_result["ai_analysis"]
            comment += ai_analysis + "\n\n"
            comment += CommentFormatter.format_new_execution_details(analysis_result)
        else:
            comment += CommentFormatter.format_analysis_sections(analysis_result)

        # Add HTML report link if running in CI
        report_id = report.get("report_id", "")
        if report_id and os.getenv("CI_JOB_ID"):
            html_url = self._get_html_artifact_url(report_id)
            if html_url:
                comment += f"\n📊 **[View Full HTML Report]({html_url})**\n"

        comment += (
            "\n<!-- cicaddy-footer -->\n---\n🤖 Generated with cicaddy-gitlab AI Agent"
        )
        return comment

    def _get_html_artifact_url(self, report_id: str) -> str:
        """Generate GitLab CI artifact URL for HTML report."""
        ci_server_url = os.getenv("CI_SERVER_URL")
        ci_project_path = os.getenv("CI_PROJECT_PATH")
        ci_job_id = os.getenv("CI_JOB_ID")

        if ci_server_url and ci_project_path and ci_job_id:
            html_filename = f"{report_id}.html"
            return f"{ci_server_url}/{ci_project_path}/-/jobs/{ci_job_id}/artifacts/file/{html_filename}"

        return ""
