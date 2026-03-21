"""Tests for BranchReviewAgent GitLab comment posting."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cicaddy_gitlab.agent.branch_agent import (
    BOT_NOTE_MARKER_PREFIX,
    BOT_NOTE_MARKER_SUFFIX,
    MIGRATION_MARKER,
    BranchReviewAgent,
)


def _make_settings(**overrides):
    settings = MagicMock()
    settings.merge_request_iid = None
    settings.ssl_verify = True
    for k, v in overrides.items():
        setattr(settings, k, v)
    return settings


def _expected_marker(branch="feature"):
    return f"{BOT_NOTE_MARKER_PREFIX}:{branch}{BOT_NOTE_MARKER_SUFFIX}"


def _make_agent(**settings_overrides):
    settings = _make_settings(**settings_overrides)
    agent = BranchReviewAgent.__new__(BranchReviewAgent)
    agent.settings = settings
    agent.source_branch = "feature"
    agent.target_branch = "main"
    agent.platform_analyzer = MagicMock()
    agent.platform_analyzer.post_merge_request_note = AsyncMock(return_value={"id": 10})
    agent.platform_analyzer.post_commit_note = AsyncMock(return_value={"id": 20})
    agent.platform_analyzer.find_bot_note_on_branch = AsyncMock(return_value=None)
    agent.platform_analyzer.delete_commit_note = AsyncMock()
    return agent


class TestPostGitlabComment:
    """Branch review comment posting behavior."""

    @pytest.mark.asyncio
    async def test_posts_to_mr_when_iid_available(self):
        agent = _make_agent(merge_request_iid="99")

        await agent._post_gitlab_comment(
            {"report_id": "r1"}, {"ai_analysis": "looks good", "status": "success"}
        )

        agent.platform_analyzer.post_merge_request_note.assert_awaited_once()
        call_args = agent.platform_analyzer.post_merge_request_note.call_args
        assert call_args[0][0] == "99"
        assert call_args[1]["note_marker"] == _expected_marker()
        agent.platform_analyzer.post_commit_note.assert_not_awaited()

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"CI_COMMIT_SHA": "abc123def"}, clear=False)
    async def test_falls_back_to_commit_when_no_mr(self):
        agent = _make_agent()  # merge_request_iid=None

        await agent._post_gitlab_comment(
            {"report_id": "r1"}, {"ai_analysis": "looks good", "status": "success"}
        )

        agent.platform_analyzer.post_merge_request_note.assert_not_awaited()
        agent.platform_analyzer.post_commit_note.assert_awaited_once()
        call_args = agent.platform_analyzer.post_commit_note.call_args
        assert call_args[0][0] == "abc123def"

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"CI_COMMIT_SHA": "abc123def"}, clear=False)
    async def test_falls_back_to_commit_when_mr_post_fails(self):
        agent = _make_agent(merge_request_iid="99")
        agent.platform_analyzer.post_merge_request_note = AsyncMock(
            side_effect=Exception("API error")
        )

        await agent._post_gitlab_comment(
            {"report_id": "r1"}, {"ai_analysis": "looks good", "status": "success"}
        )

        agent.platform_analyzer.post_commit_note.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_when_no_analyzer(self):
        agent = _make_agent()
        agent.platform_analyzer = None

        # Should not raise
        await agent._post_gitlab_comment(
            {"report_id": "r1"}, {"ai_analysis": "ok", "status": "success"}
        )

    @pytest.mark.asyncio
    @patch.dict("os.environ", {}, clear=True)
    async def test_skips_commit_when_no_sha(self):
        agent = _make_agent()  # no MR IID, no CI_COMMIT_SHA

        await agent._post_gitlab_comment(
            {"report_id": "r1"}, {"ai_analysis": "ok", "status": "success"}
        )

        agent.platform_analyzer.post_merge_request_note.assert_not_awaited()
        agent.platform_analyzer.post_commit_note.assert_not_awaited()

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"CI_COMMIT_SHA": "newcommitsha"}, clear=False)
    async def test_migrates_note_from_previous_commit(self):
        """When a bot note exists on a previous commit, migrate it."""
        old_note = MagicMock()
        old_note.body = "<!-- cicaddy-gitlab:branch-review:feature -->\nOld analysis"
        old_note.id = 5
        old_discussion = MagicMock()
        old_discussion.id = "disc-1"
        agent = _make_agent()
        agent.platform_analyzer.find_bot_note_on_branch = AsyncMock(
            return_value=("oldcommitsha", old_discussion, old_note)
        )
        agent.platform_analyzer._build_updated_body = MagicMock(
            return_value="updated body with collapsed history"
        )

        await agent._post_gitlab_comment(
            {"report_id": "r1"}, {"ai_analysis": "new review", "status": "success"}
        )

        # Should post updated body with migration log in a single call
        agent.platform_analyzer.post_commit_note.assert_awaited_once()
        call_args = agent.platform_analyzer.post_commit_note.call_args
        assert call_args[0][0] == "newcommitsha"
        posted_body = call_args[0][1]
        assert "updated body with collapsed history" in posted_body
        assert MIGRATION_MARKER in posted_body
        assert "oldcommi" in posted_body  # old SHA[:8]
        assert "newcommi" in posted_body  # new SHA[:8]
        assert "migrated" in posted_body

        # Should delete old note AFTER posting the new one
        agent.platform_analyzer.delete_commit_note.assert_awaited_once_with(
            "oldcommitsha", "disc-1", 5
        )

    @pytest.mark.asyncio
    @patch.dict("os.environ", {"CI_COMMIT_SHA": "newcommitsha"}, clear=False)
    async def test_continues_if_old_note_delete_fails(self):
        """Migration should succeed even if deleting the old note fails."""
        old_note = MagicMock()
        old_note.body = "old"
        old_note.id = 5
        old_discussion = MagicMock()
        old_discussion.id = "disc-1"
        agent = _make_agent()
        agent.platform_analyzer.find_bot_note_on_branch = AsyncMock(
            return_value=("oldsha00", old_discussion, old_note)
        )
        agent.platform_analyzer._build_updated_body = MagicMock(return_value="updated")
        agent.platform_analyzer.delete_commit_note = AsyncMock(
            side_effect=Exception("403 Forbidden")
        )

        # Should not raise
        await agent._post_gitlab_comment(
            {"report_id": "r1"}, {"ai_analysis": "ok", "status": "success"}
        )

        agent.platform_analyzer.post_commit_note.assert_awaited_once()
        # Migration log should still be present even if delete failed
        posted_body = agent.platform_analyzer.post_commit_note.call_args[0][1]
        assert "migrated" in posted_body


class TestFormatGitlabComment:
    """Comment formatting matches MR code review style."""

    def test_includes_bot_marker(self):
        agent = _make_agent()
        comment = agent._format_gitlab_comment(
            {"report_id": "r1"}, {"ai_analysis": "All good", "status": "success"}
        )
        assert comment.startswith(_expected_marker())

    def test_includes_ai_analysis(self):
        agent = _make_agent()
        comment = agent._format_gitlab_comment(
            {"report_id": "r1"},
            {"ai_analysis": "Found 2 issues", "status": "warning"},
        )
        assert "Found 2 issues" in comment

    def test_includes_footer_marker(self):
        agent = _make_agent()
        comment = agent._format_gitlab_comment(
            {"report_id": "r1"}, {"ai_analysis": "ok", "status": "success"}
        )
        assert "<!-- cicaddy-footer -->" in comment

    @patch.dict(
        "os.environ",
        {
            "CI_JOB_ID": "123",
            "CI_SERVER_URL": "https://gitlab.example.com",
            "CI_PROJECT_PATH": "group/project",
        },
        clear=False,
    )
    def test_includes_html_report_link_in_ci(self):
        agent = _make_agent()
        comment = agent._format_gitlab_comment(
            {"report_id": "report_001"},
            {"ai_analysis": "ok", "status": "success"},
        )
        assert "View Full HTML Report" in comment
        assert "report_001.html" in comment

    @patch.dict(
        "os.environ",
        {
            "CI_COMMIT_SHA": "abc123def456",
            "CI_SERVER_URL": "https://gitlab.example.com",
            "CI_PROJECT_PATH": "group/project",
            "CI_PIPELINE_ID": "789",
        },
        clear=False,
    )
    def test_includes_commit_reference_header(self):
        agent = _make_agent()
        comment = agent._format_gitlab_comment(
            {"report_id": "r1"}, {"ai_analysis": "ok", "status": "success"}
        )
        assert "**Branch review** for `feature`" in comment
        assert "abc123de" in comment  # short SHA
        assert "pipeline #789" in comment
        assert "gitlab.example.com/group/project/-/commit/abc123def456" in comment

    def test_legacy_format_without_ai_analysis(self):
        agent = _make_agent()
        comment = agent._format_gitlab_comment(
            {"report_id": "r1"},
            {"code_review": {"summary": "clean"}},
        )
        assert _expected_marker() in comment
        assert "<!-- cicaddy-footer -->" in comment


class TestMigrationLog:
    """Migration log formatting and accumulation."""

    def test_format_migration_log(self):
        agent = _make_agent()
        log = agent._format_migration_log("aaa11111", "bbb22222", 10)
        assert MIGRATION_MARKER in log
        assert "Migration log" in log
        assert "aaa11111" in log  # full short SHA in table
        assert "bbb22222" in log
        assert "note 10" in log
        assert "migrated" in log

    def test_accumulates_previous_rows(self):
        agent = _make_agent()
        first_log = agent._format_migration_log("aaa11111", "bbb22222", 1)
        # Extract rows from first log
        previous_rows = agent._extract_migration_rows(first_log)
        assert "aaa11111" in previous_rows

        # Build second log with accumulated rows
        second_log = agent._format_migration_log(
            "bbb22222",
            "ccc33333",
            2,
            previous_rows=previous_rows,
        )
        # Should contain both old and new migration entries
        assert "aaa11111" in second_log
        assert "ccc33333" in second_log
        # Should have exactly 2 data rows
        extracted = agent._extract_migration_rows(second_log)
        assert len(extracted.strip().splitlines()) == 2

    def test_extract_migration_rows_empty(self):
        """Returns empty string when no migration marker present."""
        assert BranchReviewAgent._extract_migration_rows("no marker here") == ""

    def test_strips_migration_log_before_collapsing(self):
        """Migration log is stripped from old body before _build_updated_body."""
        body = (
            "<!-- cicaddy-gitlab:branch-review:feature -->\nAnalysis content"
            f"\n{MIGRATION_MARKER}\n| 2026-01-01 | old | new | deleted |"
        )
        # Splitting at marker should give clean content
        clean = body.split(MIGRATION_MARKER, 1)[0].rstrip()
        assert MIGRATION_MARKER not in clean
        assert "Analysis content" in clean
