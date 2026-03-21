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
import re
from datetime import datetime, timezone
from typing import Any, Dict

from cicaddy.agent.branch_agent import BranchReviewAgent as CoreBranchReviewAgent
from cicaddy.utils.formatting_utils import CommentFormatter
from cicaddy.utils.logger import get_logger

from cicaddy_gitlab.agent.base_review_agent import BaseReviewAgent

logger = get_logger(__name__)

BOT_NOTE_MARKER_PREFIX = "<!-- cicaddy-gitlab:branch-review"
BOT_NOTE_MARKER_SUFFIX = " -->"
MIGRATION_MARKER = "<!-- cicaddy-migration-log -->"


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

    def _get_bot_note_marker(self) -> str:
        """Return a branch-specific bot note marker."""
        return f"{BOT_NOTE_MARKER_PREFIX}:{self.source_branch}{BOT_NOTE_MARKER_SUFFIX}"

    @staticmethod
    def _build_commit_url(commit_sha: str) -> str:
        """Build a GitLab commit URL from CI environment variables."""
        server_url = os.getenv("CI_SERVER_URL")
        project_path = os.getenv("CI_PROJECT_PATH")
        if server_url and project_path:
            return f"{server_url}/{project_path}/-/commit/{commit_sha}"
        return ""

    @staticmethod
    def _format_commit_ref(commit_sha: str, commit_url: str = "") -> str:
        """Format a short commit reference, optionally as a markdown link."""
        short = commit_sha[:8]
        if commit_url:
            return f"[`{short}`]({commit_url})"
        return f"`{short}`"

    async def _post_gitlab_comment(
        self, report: Dict[str, Any], analysis_result: Dict[str, Any]
    ):
        """Post analysis results as a GitLab comment.

        Prefers posting as an MR note (edit-in-place with history
        collapsing) when a merge request IID is available.  Falls back
        to commit comments when no MR context exists.

        For commit comments on push events, searches previous commits
        on the same branch for an existing bot note and migrates it to
        the latest commit with the previous analysis collapsed.
        """
        if not self.platform_analyzer:
            logger.debug("No platform analyzer available, skipping comment")
            return

        note_marker = self._get_bot_note_marker()
        comment_content = self._format_gitlab_comment(report, analysis_result)
        mr_iid = getattr(self.settings, "merge_request_iid", None)

        if mr_iid:
            try:
                result = await self.platform_analyzer.post_merge_request_note(
                    mr_iid, comment_content, note_marker=note_marker
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
            # Search previous branch commits for an existing bot note
            # so we can migrate it (with collapsed history) to the new commit.
            previous = await self.platform_analyzer.find_bot_note_on_branch(
                self.source_branch, note_marker, exclude_sha=commit_sha
            )
            if previous:
                old_sha, old_discussion, old_note = previous
                # Preserve migration history from the old note
                previous_rows = self._extract_migration_rows(old_note.body)
                # Strip migration log from old body before collapsing
                old_body = old_note.body
                if MIGRATION_MARKER in old_body:
                    old_body = old_body.split(MIGRATION_MARKER, 1)[0].rstrip()
                # Build updated body with collapsed previous analysis
                updated_content = self.platform_analyzer._build_updated_body(
                    old_body, comment_content
                )
                # Delete the old note before posting so we know the status
                deleted = False
                try:
                    await self.platform_analyzer.delete_commit_note(
                        old_sha, old_discussion.id, old_note.id
                    )
                    deleted = True
                except Exception as e:
                    logger.warning(f"Could not delete old note from {old_sha[:8]}: {e}")
                # Build migration log and post everything in a single call
                migration_entry = self._format_migration_log(
                    old_sha,
                    commit_sha,
                    old_note.id,
                    deleted,
                    previous_rows,
                )
                result = await self.platform_analyzer.post_commit_note(
                    commit_sha, updated_content + migration_entry
                )
                logger.info(
                    f"Migrated branch review from {old_sha[:8]} to "
                    f"{commit_sha[:8]}, note ID: {result.get('id')}"
                )
            else:
                result = await self.platform_analyzer.post_commit_note(
                    commit_sha, comment_content
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
        comment = f"{self._get_bot_note_marker()}\n"

        # Add commit reference header
        commit_sha = os.getenv("CI_COMMIT_SHA", "")
        if commit_sha:
            commit_url = self._build_commit_url(commit_sha)
            commit_ref = self._format_commit_ref(commit_sha, commit_url)
            pipeline_id = os.getenv("CI_PIPELINE_ID", "")
            pipeline_info = f" · pipeline #{pipeline_id}" if pipeline_id else ""
            comment += f"**Branch review** for `{self.source_branch}` at {commit_ref}{pipeline_info}\n\n"

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

    # Matches markdown table data rows: | <timestamp> | ... | ... | ... |
    _MIGRATION_ROW_RE = re.compile(r"^\|[^|]+\|[^|]+\|[^|]+\|[^|]+\|$")

    @classmethod
    def _extract_migration_rows(cls, body: str) -> str:
        """Extract existing migration log table rows from a note body."""
        if MIGRATION_MARKER not in body:
            return ""
        section = body.split(MIGRATION_MARKER, 1)[1]
        rows = []
        for line in section.splitlines():
            line = line.strip()
            # Skip header/separator rows and match only data rows
            if (
                cls._MIGRATION_ROW_RE.match(line)
                and not line.startswith("|--")
                and not line.startswith("| Time")
            ):
                rows.append(line)
        return "\n".join(rows)

    def _format_migration_log(
        self,
        old_sha: str,
        new_sha: str,
        old_note_id: int | None,
        old_deleted: bool,
        previous_rows: str = "",
    ) -> str:
        """Build a hidden migration log block appended after the footer.

        The log records the commit-to-commit migration trail so reviewers
        can audit which commits were reviewed and where notes moved.
        Existing rows from previous migrations are preserved.
        """
        old_url = self._build_commit_url(old_sha)
        new_url = self._build_commit_url(new_sha)
        old_ref = self._format_commit_ref(old_sha, old_url)
        new_ref = self._format_commit_ref(new_sha, new_url)
        status = "deleted" if old_deleted else "kept"
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        new_row = (
            f"| {ts} | {old_ref} (note {old_note_id}) | {new_ref} | old note {status} |"
        )
        all_rows = f"{previous_rows}\n{new_row}" if previous_rows else new_row
        return (
            f"\n{MIGRATION_MARKER}\n"
            f"\n<details>\n<summary><sub>Migration log</sub></summary>\n\n"
            f"| Time | From | To | Status |\n"
            f"|------|------|----|--------|\n"
            f"{all_rows}\n"
            f"\n</details>\n"
        )

    def _get_html_artifact_url(self, report_id: str) -> str:
        """Generate GitLab CI artifact URL for HTML report."""
        ci_server_url = os.getenv("CI_SERVER_URL")
        ci_project_path = os.getenv("CI_PROJECT_PATH")
        ci_job_id = os.getenv("CI_JOB_ID")

        if ci_server_url and ci_project_path and ci_job_id:
            html_filename = f"{report_id}.html"
            return f"{ci_server_url}/{ci_project_path}/-/jobs/{ci_job_id}/artifacts/file/{html_filename}"

        return ""
