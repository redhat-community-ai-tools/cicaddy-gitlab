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
        self, mr_iid: str, content: str, note_marker: str | None = None
    ) -> Dict[str, Any]:
        """Post or update a note on a merge request.

        When *note_marker* is provided the method searches for an existing
        note whose body starts with that marker.  If found, the previous
        analysis is collapsed into a ``<details>`` block and the note is
        updated in-place (similar to CodeRabbit / Qodo persistent review).
        Otherwise a new note is created.

        Args:
            mr_iid: Merge request IID.
            content: Note body text.
            note_marker: Optional marker that identifies the bot note.
        """
        mr = self._get_project().mergerequests.get(mr_iid)

        if note_marker:
            existing = self._find_bot_note(mr, note_marker)
            if existing is not None:
                updated = self._build_updated_body(existing.body, content)
                existing.body = updated
                existing.save()
                logger.info(f"Updated existing note (id={existing.id}) in MR {mr_iid}")
                return {
                    "id": existing.id,
                    "created_at": existing.created_at,
                    "updated_at": getattr(existing, "updated_at", ""),
                }

        logger.info(f"Posting new note to merge request {mr_iid}")
        note = mr.notes.create({"body": content})

        return {
            "id": note.id,
            "created_at": note.created_at,
            "updated_at": note.updated_at,
        }

    @staticmethod
    def _find_bot_note(mr, marker: str):
        """Return the most recent non-system note whose body starts with *marker*.

        Fetches notes in descending order so the most recent bot note is
        found first, and uses pagination to avoid fetching all notes on
        MRs with long discussion histories.
        """
        page = 1
        per_page = 50
        while True:
            notes = mr.notes.list(
                page=page, per_page=per_page, order_by="created_at", sort="desc"
            )
            if not notes:
                break
            for note in notes:
                if note.system:
                    continue
                if note.body and note.body.lstrip().startswith(marker):
                    return note
            if len(notes) < per_page:
                break
            page += 1
        return None

    # GitLab notes have a ~1MB limit; use a generous threshold that
    # preserves more history while staying safely below the API limit.
    MAX_NOTE_LENGTH = 250_000
    # Reserve a buffer so the final result (new body + history overhead)
    # stays comfortably under MAX_NOTE_LENGTH.
    _HISTORY_OVERHEAD_BUFFER = 5_000

    FOOTER_MARKER = "<!-- cicaddy-footer -->"

    @classmethod
    def _strip_footer(cls, body: str) -> str:
        """Remove the trailing footer from a note body.

        Looks for the unique ``<!-- cicaddy-footer -->`` marker to avoid
        accidentally stripping markdown horizontal rules in AI output.
        """
        idx = body.rfind(cls.FOOTER_MARKER)
        if idx != -1:
            return body[:idx].rstrip()
        return body.rstrip()

    @classmethod
    def _build_updated_body(cls, old_body: str, new_body: str) -> str:
        """Prepend *new_body* and collapse the previous analysis.

        Footers are stripped from old content to avoid duplication.
        If the result exceeds the note length limit the oldest
        history entries are dropped.
        """
        # Safety truncate: if new_body alone exceeds the limit (minus a
        # buffer for history overhead), trim it to avoid a GitLab API 400.
        safe_limit = cls.MAX_NOTE_LENGTH - cls._HISTORY_OVERHEAD_BUFFER
        if len(new_body) > safe_limit:
            truncation_suffix = (
                "\n\n*[Analysis truncated to stay within note length limit]*"
            )
            new_body = (
                new_body[: safe_limit - len(truncation_suffix)] + truncation_suffix
            )
            logger.warning("New analysis body truncated to stay within character limit")

        history_tag = "\n<details>\n<summary><b>Previous analyses</b></summary>\n"

        # Strip footer from old content before collapsing
        old_content = cls._strip_footer(old_body)

        if history_tag in old_content:
            current_section, existing_history = old_content.split(history_tag, 1)
            existing_history = existing_history.rstrip()
            if existing_history.endswith("</details>"):
                existing_history = existing_history[: -len("</details>")].rstrip()
            collapsed = (
                f"{history_tag}\n{current_section.strip()}\n\n"
                f"{existing_history}\n\n</details>\n"
            )
        else:
            collapsed = f"{history_tag}\n{old_content.strip()}\n\n</details>\n"

        result = f"{new_body}\n{collapsed}"

        # Truncate history if the note exceeds the length limit.
        # Keep as much of the collapsed history as possible rather than
        # dropping it entirely.
        if len(result) > cls.MAX_NOTE_LENGTH:
            truncation_notice = (
                "\n\n*[Older history truncated to stay within note length limit]*"
                "\n\n</details>\n"
            )
            # Account for the newline joining new_body and trimmed history
            budget = cls.MAX_NOTE_LENGTH - len(new_body) - len(truncation_notice) - 1
            if budget > 0:
                # Keep the opening history tag and as much content as fits
                trimmed = collapsed[:budget]
                result = f"{new_body}\n{trimmed}{truncation_notice}"
            else:
                # New body alone is near the limit; drop history entirely
                result = f"{new_body}\n\n*[History omitted — note length limit]*"
            logger.warning("Note history truncated to stay within character limit")

        return result

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

    async def post_commit_note(
        self, commit_sha: str, content: str, note_marker: str | None = None
    ) -> Dict[str, Any]:
        """Post or update a note on a specific commit.

        When *note_marker* is provided the method searches existing commit
        discussions for a note whose body starts with that marker.  If found,
        the previous analysis is collapsed into a ``<details>`` block and the
        note is updated in-place via the Discussions API.  Otherwise a new
        comment is created.

        Args:
            commit_sha: Commit SHA to comment on.
            content: Note body text.
            note_marker: Optional marker that identifies the bot note.
        """
        logger.info(f"Posting note to commit {commit_sha[:8]}...")

        try:
            project = self._get_project()
            commit = project.commits.get(commit_sha, lazy=True)

            # Try update-in-place via discussions API
            if note_marker:
                existing = self._find_bot_commit_note(commit, note_marker)
                if existing is not None:
                    discussion, note_obj = existing
                    updated = self._build_updated_body(note_obj.body, content)
                    note_obj.body = updated
                    note_obj.save()
                    logger.info(
                        f"Updated existing commit note (id={note_obj.id}) "
                        f"on {commit_sha[:8]}"
                    )
                    return {
                        "id": note_obj.id,
                        "created_at": getattr(note_obj, "created_at", "unknown"),
                        "updated_at": getattr(note_obj, "updated_at", "unknown"),
                        "commit_sha": commit_sha,
                    }

            # Create new comment
            note = commit.comments.create({"note": content})
            return {
                "id": getattr(note, "id", None),
                "created_at": getattr(note, "created_at", "unknown"),
                "updated_at": getattr(note, "updated_at", "unknown"),
                "commit_sha": commit_sha,
            }
        except Exception as e:
            logger.error(f"Failed to post commit note: {e}")
            return {"error": str(e)}

    @staticmethod
    def _find_bot_commit_note(commit, marker: str):
        """Find a bot note in commit discussions by marker.

        Returns a (discussion, note) tuple if found, else None.
        Uses the Discussions API which supports note editing via save().

        Note: the commit discussions API returns discussions in default
        (oldest-first) order and does not support ``sort``/``order_by``.
        The bot assumes a single note per marker, so order doesn't matter.
        """
        page = 1
        per_page = 50
        while True:
            discussions = commit.discussions.list(page=page, per_page=per_page)
            if not discussions:
                break
            for discussion in discussions:
                for note_data in discussion.attributes.get("notes", []):
                    if note_data.get("system"):
                        continue
                    body = note_data.get("body", "")
                    if body and body.lstrip().startswith(marker):
                        # Get the saveable note object
                        note_obj = discussion.notes.get(note_data["id"])
                        return discussion, note_obj
            if len(discussions) < per_page:
                break
            page += 1
        return None

    async def find_bot_note_on_branch(
        self, branch: str, note_marker: str, exclude_sha: str | None = None
    ):
        """Search recent commits on *branch* for an existing bot note.

        Returns ``(commit_sha, discussion, note_obj)`` if found, else
        ``None``.  Useful for migrating a note from an older commit to the
        latest one on the same branch (e.g. branch review on push events).

        Args:
            branch: Branch name to search commits on.
            note_marker: HTML comment marker that identifies the bot note.
            exclude_sha: Skip this commit SHA (typically the current commit).
        """
        project = self._get_project()
        # Check the most recent commits on this branch (limit search scope)
        commits = project.commits.list(ref_name=branch, per_page=20)
        for commit_obj in commits:
            sha = commit_obj.id
            if sha == exclude_sha:
                continue
            commit = project.commits.get(sha, lazy=True)
            result = self._find_bot_commit_note(commit, note_marker)
            if result is not None:
                logger.debug(f"Found existing bot note on commit {sha[:8]}")
                return sha, result[0], result[1]
        return None

    async def delete_commit_note(
        self, commit_sha: str, discussion_id: str, note_id: int
    ) -> None:
        """Delete a note from a commit discussion."""
        project = self._get_project()
        commit = project.commits.get(commit_sha, lazy=True)
        discussion = commit.discussions.get(discussion_id)
        note = discussion.notes.get(note_id)
        note.delete()
        logger.info(f"Deleted note {note_id} from commit {commit_sha[:8]}")

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
