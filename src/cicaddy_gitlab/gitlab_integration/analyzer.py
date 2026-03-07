"""GitLab integration for merge request analysis."""

import subprocess  # nosec B404
from typing import Any, Dict, Optional, Union

from cicaddy.utils.logger import get_logger

import gitlab

logger = get_logger(__name__)


class GitLabAnalyzer:
    """GitLab API client for merge request operations."""

    def __init__(
        self, token: str, api_url: str, project_id: str, ssl_verify: bool = True
    ):
        # python-gitlab expects base server URL, not the full API URL
        # Remove /api/v4 suffix if present since gitlab.Gitlab will add it automatically
        base_url = api_url.rstrip("/")
        if base_url.endswith("/api/v4"):
            base_url = base_url[:-7]  # Remove "/api/v4"
            logger.info(f"Stripped /api/v4 from GitLab URL: {api_url} -> {base_url}")
        else:
            logger.info(f"Using GitLab URL as-is: {base_url}")

        self.gl = gitlab.Gitlab(base_url, private_token=token, ssl_verify=ssl_verify)  # type: ignore[attr-defined]
        self.project_id = project_id
        self._project = None  # Lazy loading

    def _get_project(self):
        """Lazy load project with error handling."""
        if self._project is None:
            try:
                self._project = self.gl.projects.get(self.project_id)
            except Exception as e:
                logger.error(f"Failed to load project {self.project_id}: {e}")
                raise
        return self._project

    async def get_merge_request_data(self, mr_iid: str) -> Dict[str, Any]:
        """Get merge request data from GitLab API."""
        logger.info(f"Fetching merge request data for IID: {mr_iid}")

        mr = self._get_project().mergerequests.get(mr_iid)

        return {
            "iid": mr.iid,
            "title": mr.title,
            "description": mr.description,
            "author": mr.author,
            "target_branch": mr.target_branch,
            "source_branch": mr.source_branch,
            "state": mr.state,
            "web_url": mr.web_url,
            "created_at": mr.created_at,
            "updated_at": mr.updated_at,
            "changes_count": getattr(mr, "changes_count", 0),
        }

    async def get_merge_request_diff(
        self,
        mr_iid: str,
        context_lines: int = 10,
        working_directory: Optional[str] = None,
    ) -> str:
        """Get merge request diff using git commands or GitLab API.

        Args:
            mr_iid: Merge request IID
            context_lines: Number of context lines for diff
            working_directory: Git repository directory. If None, skips git commands and uses GitLab API directly.
        """
        logger.info(f"Generating diff for merge request {mr_iid}")

        # If no working directory specified, skip git commands and use API directly
        # This prevents running git commands in the wrong repository (e.g., agent repo instead of MR repo)
        if not working_directory:
            logger.info("GIT_WORKING_DIRECTORY not set, using GitLab API for diff")
            return await self._get_diff_from_api(mr_iid)

        # Working directory provided, use git commands
        logger.info(f"Using working directory: {working_directory}")

        try:
            # Get merge base
            mr = self._get_project().mergerequests.get(mr_iid)
            target_branch = mr.target_branch

            # Use git command to get diff
            # Use list construction instead of cmd.split() to handle branch names with spaces
            merge_base = subprocess.check_output(  # nosec: B603 B607
                ["git", "merge-base", "HEAD", f"origin/{target_branch}"],
                text=True,
                cwd=working_directory,
            ).strip()

            # Generate diff with context
            # Use list construction for robustness with merge_base containing special chars
            diff_content = subprocess.check_output(  # nosec: B603 B607
                ["git", "diff", f"-U{context_lines}", f"{merge_base}...HEAD"],
                text=True,
                cwd=working_directory,
            )

            # Check if diff is empty (can happen when HEAD is not on the MR source branch,
            # e.g., when testing locally against merged MRs or MRs from user forks)
            if not diff_content or diff_content.strip() == "":
                logger.warning(
                    f"Git diff returned empty content for MR {mr_iid}. "
                    f"This can happen when the working directory is not on the MR source branch. "
                    f"Falling back to GitLab API."
                )
                return await self._get_diff_from_api(mr)

            return diff_content

        except subprocess.CalledProcessError as e:
            logger.error(f"Git command failed: {e}")
            # Fallback to GitLab API
            return await self._get_diff_from_api(mr)

    async def _get_diff_from_api(self, mr_or_iid: Union[str, Any]) -> str:
        """Fallback method to get diff from GitLab API.

        Args:
            mr_or_iid: Either MR IID (str) or pre-fetched MR object
        """
        logger.info("Using GitLab API for diff generation")

        # Handle both cases: string IID or pre-fetched object
        if isinstance(mr_or_iid, str):
            mr = self._get_project().mergerequests.get(mr_or_iid)
        else:
            mr = mr_or_iid  # Already fetched

        changes = mr.changes()

        diff_content = ""
        for change in changes.get("changes", []):
            diff_content += change.get("diff", "") + "\n"

        return diff_content

    async def get_changed_files(self, mr_iid: str) -> list:
        """Get list of changed files in merge request."""
        mr = self._get_project().mergerequests.get(mr_iid)
        changes = mr.changes()

        files = []
        for change in changes.get("changes", []):
            if change.get("new_path"):
                files.append(change["new_path"])

        return files

    async def get_file_content(self, file_path: str, ref: str = "HEAD") -> str:
        """Get content of a specific file."""
        try:
            file_info = self._get_project().files.get(file_path=file_path, ref=ref)
            return file_info.decode().decode("utf-8")
        except Exception as e:
            logger.warning(f"Could not fetch file {file_path}: {e}")
            return ""

    async def post_merge_request_note(
        self, mr_iid: str, content: str
    ) -> Dict[str, Any]:
        """Post a note to merge request."""
        logger.info(f"Posting note to merge request {mr_iid}")

        mr = self._get_project().mergerequests.get(mr_iid)
        note = mr.notes.create({"body": content})

        return {
            "id": note.id,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }

    async def get_merge_request_notes(self, mr_iid: str) -> list:
        """Get all notes from merge request."""
        mr = self._get_project().mergerequests.get(mr_iid)
        notes = mr.notes.list(all=True)

        return [
            {
                "id": note.id,
                "body": note.body,
                "author": note.author,
                "created_at": note.created_at,
                "system": note.system,
            }
            for note in notes
        ]

    async def update_merge_request_note(self, mr_iid: str, note_id: int, content: str):
        """Update an existing merge request note."""
        mr = self._get_project().mergerequests.get(mr_iid)
        note = mr.notes.get(note_id)
        note.body = content
        note.save()

        logger.info(f"Updated note {note_id} in MR {mr_iid}")

    async def post_commit_note(self, commit_sha: str, content: str) -> Dict[str, Any]:
        """Post a note to a specific commit."""
        logger.info(f"Posting note to commit {commit_sha[:8]}...")

        try:
            project = self._get_project()
            # Create commit comments using the repository commits comments manager
            # Use lazy=True to avoid fetching the full commit object
            commit = project.commits.get(commit_sha, lazy=True)
            note = commit.comments.create({"note": content})

            # Debug logging to understand the commit comment object structure
            logger.debug(f"Commit comment object type: {type(note)}")
            logger.debug(
                f"Commit comment attributes: {[attr for attr in dir(note) if not attr.startswith('_')]}"
            )

            return {
                "id": getattr(note, "id", None),
                "created_at": getattr(note, "created_at", "unknown"),
                "updated_at": getattr(note, "updated_at", "unknown"),
                "commit_sha": commit_sha,
            }
        except Exception as e:
            logger.error(f"Failed to post commit note: {e}")
            return {"error": str(e)}

    async def get_commit_info(self, commit_sha: str) -> Dict[str, Any]:
        """Get commit information."""
        try:
            project = self._get_project()
            commit = project.commits.get(commit_sha)

            return {
                "id": commit.id,
                "short_id": commit.short_id,
                "title": commit.title,
                "message": commit.message,
                "author_name": commit.author_name,
                "author_email": commit.author_email,
                "authored_date": commit.authored_date,
                "committer_name": commit.committer_name,
                "committer_email": commit.committer_email,
                "committed_date": commit.committed_date,
                "web_url": commit.web_url,
            }
        except Exception as e:
            logger.warning(f"Could not fetch commit {commit_sha}: {e}")
            return {}

    async def get_project_info(self) -> Dict[str, Any]:
        """Get project information."""
        project = self._get_project()
        return {
            "id": project.id,
            "name": project.name,
            "path": project.path,
            "web_url": project.web_url,
            "default_branch": project.default_branch,
        }
