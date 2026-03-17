"""Tests for BranchReviewAgent GitLab comment posting."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cicaddy_gitlab.agent.branch_agent import BOT_NOTE_MARKER, BranchReviewAgent


def _make_settings(**overrides):
    settings = MagicMock()
    settings.merge_request_iid = None
    settings.ssl_verify = True
    for k, v in overrides.items():
        setattr(settings, k, v)
    return settings


def _make_agent(**settings_overrides):
    settings = _make_settings(**settings_overrides)
    agent = BranchReviewAgent.__new__(BranchReviewAgent)
    agent.settings = settings
    agent.source_branch = "feature"
    agent.target_branch = "main"
    agent.platform_analyzer = MagicMock()
    agent.platform_analyzer.post_merge_request_note = AsyncMock(return_value={"id": 10})
    agent.platform_analyzer.post_commit_note = AsyncMock(return_value={"id": 20})
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
        assert call_args[1]["note_marker"] == BOT_NOTE_MARKER
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
        assert call_args[1]["note_marker"] == BOT_NOTE_MARKER

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


class TestFormatGitlabComment:
    """Comment formatting matches MR code review style."""

    def test_includes_bot_marker(self):
        agent = _make_agent()
        comment = agent._format_gitlab_comment(
            {"report_id": "r1"}, {"ai_analysis": "All good", "status": "success"}
        )
        assert comment.startswith(BOT_NOTE_MARKER)

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

    def test_legacy_format_without_ai_analysis(self):
        agent = _make_agent()
        comment = agent._format_gitlab_comment(
            {"report_id": "r1"},
            {"code_review": {"summary": "clean"}},
        )
        assert BOT_NOTE_MARKER in comment
        assert "<!-- cicaddy-footer -->" in comment
