"""Tests for GitLabAnalyzer merge request note operations."""

from unittest.mock import MagicMock, patch

import pytest

from cicaddy_gitlab.gitlab_integration.analyzer import GitLabAnalyzer


@pytest.fixture
def mock_gitlab():
    """Create a mock python-gitlab client."""
    with patch("cicaddy_gitlab.gitlab_integration.analyzer.gitlab") as mock_gl_mod:
        mock_gl = MagicMock()
        mock_gl_mod.Gitlab.return_value = mock_gl
        mock_project = MagicMock()
        mock_gl.projects.get.return_value = mock_project
        yield mock_gl, mock_project


@pytest.fixture
def analyzer(mock_gitlab):
    """Create an analyzer with mocked GitLab API."""
    return GitLabAnalyzer(
        token="test-token",
        api_url="https://gitlab.com/api/v4",
        project_id="123",
    )


def _make_mock_note(note_id, body, system=False):
    """Create a mock MR note."""
    note = MagicMock()
    note.id = note_id
    note.body = body
    note.system = system
    note.created_at = "2026-03-11T10:00:00Z"
    note.updated_at = "2026-03-11T10:00:00Z"
    return note


class TestPostMergeRequestNote:
    """Test MR note posting and update-in-place."""

    @pytest.mark.asyncio
    async def test_creates_new_note_without_marker(self, analyzer, mock_gitlab):
        """Without a marker, always creates a new note."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()
        created_note = _make_mock_note(1, "new body")
        mock_mr.notes.create.return_value = created_note
        mock_project.mergerequests.get.return_value = mock_mr

        result = await analyzer.post_merge_request_note("42", "new body")

        mock_mr.notes.create.assert_called_once_with({"body": "new body"})
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_creates_new_note_when_no_existing(self, analyzer, mock_gitlab):
        """With a marker but no existing note, creates a new one."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()
        mock_mr.notes.list.return_value = []  # paginated call returns empty
        created_note = _make_mock_note(1, "new body")
        mock_mr.notes.create.return_value = created_note
        mock_project.mergerequests.get.return_value = mock_mr

        result = await analyzer.post_merge_request_note(
            "42", "new body", note_marker="<!-- bot -->"
        )

        mock_mr.notes.list.assert_called_once_with(
            page=1, per_page=50, order_by="created_at", sort="desc"
        )
        mock_mr.notes.create.assert_called_once()
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_updates_existing_note_in_place(self, analyzer, mock_gitlab):
        """Existing bot note is edited via save(), not recreated."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()

        old_note = _make_mock_note(99, "<!-- bot -->\nold analysis")
        mock_mr.notes.list.return_value = [old_note]
        mock_project.mergerequests.get.return_value = mock_mr

        await analyzer.post_merge_request_note(
            "42", "<!-- bot -->\nnew analysis", note_marker="<!-- bot -->"
        )

        old_note.save.assert_called_once()
        mock_mr.notes.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_updated_body_contains_collapsed_previous(
        self, analyzer, mock_gitlab
    ):
        """The saved body collapses the old analysis in a <details> block."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()

        old_note = _make_mock_note(99, "<!-- bot -->\nold analysis")
        mock_mr.notes.list.return_value = [old_note]
        mock_project.mergerequests.get.return_value = mock_mr

        await analyzer.post_merge_request_note(
            "42", "<!-- bot -->\nnew analysis", note_marker="<!-- bot -->"
        )

        updated_body = old_note.body
        assert "<!-- bot -->\nnew analysis" in updated_body
        assert "<summary><b>Previous analyses</b></summary>" in updated_body
        assert "old analysis" in updated_body

    @pytest.mark.asyncio
    async def test_ignores_unrelated_notes(self, analyzer, mock_gitlab):
        """Unrelated notes are not touched."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()

        other_note = _make_mock_note(1, "LGTM!")
        mock_mr.notes.list.return_value = [other_note]
        created_note = _make_mock_note(2, "new")
        mock_mr.notes.create.return_value = created_note
        mock_project.mergerequests.get.return_value = mock_mr

        await analyzer.post_merge_request_note(
            "42", "<!-- bot -->\nnew", note_marker="<!-- bot -->"
        )

        other_note.save.assert_not_called()
        mock_mr.notes.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_system_notes(self, analyzer, mock_gitlab):
        """System notes (merge status, label changes) are skipped."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()

        system_note = _make_mock_note(1, "<!-- bot -->\nsystem generated", system=True)
        mock_mr.notes.list.return_value = [system_note]
        created_note = _make_mock_note(2, "new")
        mock_mr.notes.create.return_value = created_note
        mock_project.mergerequests.get.return_value = mock_mr

        await analyzer.post_merge_request_note(
            "42", "<!-- bot -->\nnew", note_marker="<!-- bot -->"
        )

        system_note.save.assert_not_called()
        mock_mr.notes.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_finds_note_with_leading_whitespace(self, analyzer, mock_gitlab):
        """Note with leading whitespace before marker is still matched."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()

        ws_note = _make_mock_note(99, "\n  <!-- bot -->\nold analysis")
        mock_mr.notes.list.return_value = [ws_note]
        mock_project.mergerequests.get.return_value = mock_mr

        await analyzer.post_merge_request_note(
            "42", "<!-- bot -->\nnew analysis", note_marker="<!-- bot -->"
        )

        ws_note.save.assert_called_once()
        mock_mr.notes.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_note_with_none_body(self, analyzer, mock_gitlab):
        """Note with None body is safely skipped."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()

        null_note = _make_mock_note(1, None)
        mock_mr.notes.list.return_value = [null_note]
        created_note = _make_mock_note(2, "new")
        mock_mr.notes.create.return_value = created_note
        mock_project.mergerequests.get.return_value = mock_mr

        await analyzer.post_merge_request_note(
            "42", "<!-- bot -->\nnew", note_marker="<!-- bot -->"
        )

        null_note.save.assert_not_called()
        mock_mr.notes.create.assert_called_once()


class TestPostCommitNote:
    """Test commit note posting and update-in-place via discussions."""

    @pytest.mark.asyncio
    async def test_creates_new_commit_note_without_marker(self, analyzer, mock_gitlab):
        """Without a marker, always creates a new commit comment."""
        _, mock_project = mock_gitlab
        mock_commit = MagicMock()
        mock_note = MagicMock()
        mock_note.id = 1
        mock_note.created_at = "2026-03-11T10:00:00Z"
        mock_note.updated_at = "2026-03-11T10:00:00Z"
        mock_commit.comments.create.return_value = mock_note
        mock_project.commits.get.return_value = mock_commit

        result = await analyzer.post_commit_note("abc123", "new body")

        mock_commit.comments.create.assert_called_once_with({"note": "new body"})
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_creates_new_commit_note_when_no_existing(
        self, analyzer, mock_gitlab
    ):
        """With a marker but no existing discussion, creates a new comment."""
        _, mock_project = mock_gitlab
        mock_commit = MagicMock()
        mock_commit.discussions.list.return_value = []
        mock_note = MagicMock()
        mock_note.id = 2
        mock_note.created_at = "2026-03-11T10:00:00Z"
        mock_note.updated_at = "2026-03-11T10:00:00Z"
        mock_commit.comments.create.return_value = mock_note
        mock_project.commits.get.return_value = mock_commit

        result = await analyzer.post_commit_note(
            "abc123", "<!-- bot -->\nnew", note_marker="<!-- bot -->"
        )

        mock_commit.comments.create.assert_called_once()
        assert result["id"] == 2

    @pytest.mark.asyncio
    async def test_updates_existing_commit_note_in_place(self, analyzer, mock_gitlab):
        """Existing bot commit note is updated via discussions API."""
        _, mock_project = mock_gitlab
        mock_commit = MagicMock()

        # Set up a discussion with a matching bot note
        mock_note_obj = MagicMock()
        mock_note_obj.id = 99
        mock_note_obj.body = "<!-- bot -->\nold analysis"
        mock_note_obj.created_at = "2026-03-11T10:00:00Z"
        mock_note_obj.updated_at = "2026-03-11T10:00:00Z"

        mock_discussion = MagicMock()
        mock_discussion.attributes = {
            "notes": [{"id": 99, "body": "<!-- bot -->\nold analysis", "system": False}]
        }
        mock_discussion.notes.get.return_value = mock_note_obj

        mock_commit.discussions.list.return_value = [mock_discussion]
        mock_project.commits.get.return_value = mock_commit

        await analyzer.post_commit_note(
            "abc123", "<!-- bot -->\nnew analysis", note_marker="<!-- bot -->"
        )

        mock_note_obj.save.assert_called_once()
        mock_commit.comments.create.assert_not_called()
        assert "new analysis" in mock_note_obj.body
        assert "Previous analyses" in mock_note_obj.body

    @pytest.mark.asyncio
    async def test_skips_system_notes_in_commit_discussions(
        self, analyzer, mock_gitlab
    ):
        """System notes in commit discussions are skipped."""
        _, mock_project = mock_gitlab
        mock_commit = MagicMock()

        mock_discussion = MagicMock()
        mock_discussion.attributes = {
            "notes": [{"id": 1, "body": "<!-- bot -->\nsystem", "system": True}]
        }
        mock_commit.discussions.list.return_value = [mock_discussion]

        mock_note = MagicMock()
        mock_note.id = 2
        mock_note.created_at = "2026-03-11T10:00:00Z"
        mock_note.updated_at = "2026-03-11T10:00:00Z"
        mock_commit.comments.create.return_value = mock_note
        mock_project.commits.get.return_value = mock_commit

        await analyzer.post_commit_note(
            "abc123", "<!-- bot -->\nnew", note_marker="<!-- bot -->"
        )

        mock_commit.comments.create.assert_called_once()


class TestBuildUpdatedBody:
    """Test the history collapsing logic."""

    def test_first_update_collapses_old_body(self):
        old = "<!-- bot -->\nfirst analysis\n\n---\nfooter"
        new = "<!-- bot -->\nsecond analysis\n\n---\nfooter"

        result = GitLabAnalyzer._build_updated_body(old, new)

        assert result.startswith("<!-- bot -->\nsecond analysis")
        assert "<summary><b>Previous analyses</b></summary>" in result
        assert "first analysis" in result

    def test_preserves_existing_history(self):
        """Multiple updates accumulate history inside the collapsed block."""
        first = "<!-- bot -->\nfirst"
        second = GitLabAnalyzer._build_updated_body(first, "<!-- bot -->\nsecond")
        third = GitLabAnalyzer._build_updated_body(second, "<!-- bot -->\nthird")

        assert third.startswith("<!-- bot -->\nthird")
        assert "second" in third
        assert "first" in third
        assert third.count("<summary><b>Previous analyses</b></summary>") == 1

    def test_strips_footer_from_collapsed_history(self):
        """Footer is removed from old content before collapsing."""
        old = "<!-- bot -->\nold analysis\n\n<!-- cicaddy-footer -->\n---\n🤖 Generated"
        new = "<!-- bot -->\nnew analysis\n\n<!-- cicaddy-footer -->\n---\n🤖 Generated"

        result = GitLabAnalyzer._build_updated_body(old, new)

        history_start = result.index("<summary>")
        history_section = result[history_start:]
        assert "Generated" not in history_section
        assert result.startswith("<!-- bot -->\nnew analysis")

    def test_does_not_strip_markdown_hr_without_footer_marker(self):
        """Markdown horizontal rules in AI output are preserved."""
        old = "<!-- bot -->\nanalysis\n\n---\n\nmore analysis"
        new = "<!-- bot -->\nnew"

        result = GitLabAnalyzer._build_updated_body(old, new)

        assert "more analysis" in result

    def test_truncates_preserving_partial_history(self):
        """History is trimmed but partially preserved when exceeding limit."""
        old = "<!-- bot -->\n" + "x" * 200_000
        new = "<!-- bot -->\n" + "y" * 100_000

        result = GitLabAnalyzer._build_updated_body(old, new)

        assert result.startswith("<!-- bot -->\n" + "y" * 100)
        assert len(result) <= GitLabAnalyzer.MAX_NOTE_LENGTH
        assert "[Older history truncated" in result
        # Partial history is still present
        assert "Previous analyses" in result

    def test_oversized_new_body_still_preserves_history(self):
        """With the buffer, an oversized new_body is pre-truncated, leaving room for history."""
        old = "<!-- bot -->\nold"
        # Body exceeds the safe limit so it gets truncated, but the
        # buffer ensures there is still room for collapsed history.
        new = "<!-- bot -->\n" + "y" * GitLabAnalyzer.MAX_NOTE_LENGTH

        result = GitLabAnalyzer._build_updated_body(old, new)

        assert "[Analysis truncated" in result
        assert "Previous analyses" in result
        assert "old" in result
        assert len(result) <= GitLabAnalyzer.MAX_NOTE_LENGTH

    def test_truncates_oversized_new_body(self):
        """new_body exceeding MAX_NOTE_LENGTH is safety-truncated."""
        old = "<!-- bot -->\nold"
        new = "x" * (GitLabAnalyzer.MAX_NOTE_LENGTH + 5000)

        result = GitLabAnalyzer._build_updated_body(old, new)

        assert len(result) <= GitLabAnalyzer.MAX_NOTE_LENGTH
        assert "[Analysis truncated" in result

    def test_handles_malformed_details_block(self):
        """Missing </details> tag does not crash the builder."""
        old = (
            "<!-- bot -->\ncurrent\n"
            "\n<details>\n<summary><b>Previous analyses</b></summary>\n"
            "\nolder content without closing tag"
        )
        new = "<!-- bot -->\nlatest"

        result = GitLabAnalyzer._build_updated_body(old, new)

        assert result.startswith("<!-- bot -->\nlatest")
        assert "current" in result
        assert "older content without closing tag" in result
