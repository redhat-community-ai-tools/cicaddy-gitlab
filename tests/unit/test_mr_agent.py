"""Tests for MergeRequestAgent delegation metadata in comments."""

from unittest.mock import MagicMock

from cicaddy_gitlab.agent.mr_agent import MergeRequestAgent


def _make_agent():
    agent = MergeRequestAgent.__new__(MergeRequestAgent)
    agent.merge_request_iid = "42"
    agent.settings = MagicMock()
    return agent


class TestFormatGitlabCommentDelegation:
    """Test _format_gitlab_comment delegation metadata rendering."""

    def test_delegation_metadata_included(self):
        """Delegation details block rendered when delegation_mode=auto."""
        agent = _make_agent()
        result = agent._format_gitlab_comment(
            {"report_id": "test"},
            {
                "ai_analysis": "Review text.",
                "delegation_mode": "auto",
                "delegation_plan": {
                    "agents": [
                        {"name": "security-reviewer", "rationale": "Auth changes"},
                        {"name": "general-reviewer", "rationale": "General review"},
                    ],
                },
                "agents_succeeded": 2,
                "agents_failed": 0,
                "total_execution_time": 8.3,
            },
        )
        assert "Delegation details: 2 agent(s) succeeded" in result
        assert "8.3s" in result
        assert "security-reviewer" in result
        assert "general-reviewer" in result
        assert "Auth changes" in result
        assert "<details>" in result

    def test_delegation_metadata_shows_failures(self):
        """Failed agent count appears in summary."""
        agent = _make_agent()
        result = agent._format_gitlab_comment(
            {"report_id": "test"},
            {
                "ai_analysis": "Review.",
                "delegation_mode": "auto",
                "delegation_plan": {
                    "agents": [{"name": "sec", "rationale": "x"}],
                },
                "agents_succeeded": 1,
                "agents_failed": 2,
                "total_execution_time": 5.0,
            },
        )
        assert "1 agent(s) succeeded" in result
        assert "2 failed" in result

    def test_delegation_metadata_handles_missing_execution_time(self):
        """Missing total_execution_time renders as 0.0s."""
        agent = _make_agent()
        result = agent._format_gitlab_comment(
            {"report_id": "test"},
            {
                "ai_analysis": "Review.",
                "delegation_mode": "auto",
                "delegation_plan": {
                    "agents": [{"name": "general-reviewer", "rationale": ""}],
                },
                "agents_succeeded": 1,
                "agents_failed": 0,
                "total_execution_time": None,
            },
        )
        assert "0.0s" in result
        assert "Delegation details" in result

    def test_no_delegation_metadata_without_auto(self):
        """No delegation block when delegation_mode is not auto."""
        agent = _make_agent()
        result = agent._format_gitlab_comment(
            {"report_id": "test"},
            {
                "ai_analysis": "Review text.",
            },
        )
        assert "Delegation details" not in result

    def test_no_delegation_metadata_without_agents(self):
        """No delegation block when delegation_plan has no agents."""
        agent = _make_agent()
        result = agent._format_gitlab_comment(
            {"report_id": "test"},
            {
                "ai_analysis": "Review.",
                "delegation_mode": "auto",
                "delegation_plan": {"agents": []},
                "agents_succeeded": 0,
                "agents_failed": 0,
            },
        )
        assert "Delegation details" not in result
