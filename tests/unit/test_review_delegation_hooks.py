"""Tests for BaseReviewAgent delegation hook forwarding to cicaddy core."""

from unittest.mock import MagicMock

from cicaddy.delegation.registry import SubAgentSpec
from cicaddy.delegation.triage import DelegationEntry, DelegationPlan

from cicaddy_gitlab.agent.base_review_agent import BaseReviewAgent


def _make_review_agent():
    """Create a minimal BaseReviewAgent with mocked settings."""

    class ConcreteReviewAgent(BaseReviewAgent):
        async def get_diff_content(self):
            return ""

        async def get_review_context(self):
            return {}

        def build_analysis_prompt(self, context):
            return ""

        def get_session_id(self):
            return "test"

    agent = ConcreteReviewAgent.__new__(ConcreteReviewAgent)
    agent.settings = MagicMock()
    return agent


class TestDelegationHookForwarding:
    """Verify delegation hooks forward to cicaddy core correctly."""

    def test_get_agent_type_returns_review(self):
        """_get_agent_type must return 'review' so registry loads review agents."""
        agent = _make_review_agent()
        assert agent._get_agent_type() == "review"

    def test_get_delegation_context_structures_diff(self):
        """_get_delegation_context should extract diff and changed files."""
        agent = _make_review_agent()
        context = {
            "project": {"name": "test"},
            "diff": (
                "diff --git a/app.py b/app.py\n"
                "+import os\n"
                "diff --git a/lib.py b/lib.py\n"
                "+pass\n"
            ),
            "diff_lines": 4,
            "mr_title": "Fix auth",
            "analysis_type": "merge_request",
        }
        result = agent._get_delegation_context(context)

        assert result["project"] == {"name": "test"}
        assert "diff" in result
        assert result["changed_files"] == ["app.py", "lib.py"]
        assert result["mr_title"] == "Fix auth"
        assert result["diff_lines"] == 4

    def test_post_process_plan_injects_general_reviewer(self):
        """_post_process_plan should inject general-reviewer when missing."""
        agent = _make_review_agent()
        plan = DelegationPlan(
            entries=[
                DelegationEntry(
                    agent_name="security-reviewer",
                    categories=["security"],
                    rationale="test",
                    priority=10,
                )
            ]
        )
        registry = {
            "security-reviewer": SubAgentSpec(
                name="security-reviewer",
                persona="sec",
                description="Security review",
                categories=["security"],
                priority=10,
                agent_type="review",
            ),
            "general-reviewer": SubAgentSpec(
                name="general-reviewer",
                persona="eng",
                description="General review",
                categories=["code_quality"],
                priority=100,
                agent_type="review",
            ),
        }

        result = agent._post_process_plan(plan, registry)
        names = [e.agent_name for e in result.entries]
        assert "general-reviewer" in names
        assert len(result.entries) == 2
        # Sorted by priority
        assert result.entries[0].agent_name == "security-reviewer"
        assert result.entries[1].agent_name == "general-reviewer"

    def test_post_process_plan_no_duplicate(self):
        """Should not add general-reviewer if already present."""
        agent = _make_review_agent()
        plan = DelegationPlan(
            entries=[
                DelegationEntry(
                    agent_name="general-reviewer",
                    categories=["code_quality"],
                    rationale="test",
                    priority=100,
                )
            ]
        )
        registry = {
            "general-reviewer": SubAgentSpec(
                name="general-reviewer",
                persona="eng",
                description="General review",
                categories=["code_quality"],
                priority=100,
                agent_type="review",
            ),
        }

        result = agent._post_process_plan(plan, registry)
        assert len(result.entries) == 1
