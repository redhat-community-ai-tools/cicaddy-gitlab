"""Tests for GitLab agent type detection."""

from unittest.mock import MagicMock, patch

from cicaddy_gitlab.agent.factory import _detect_gitlab_agent_type


def _make_settings(**overrides):
    settings = MagicMock()
    settings.merge_request_iid = None
    for k, v in overrides.items():
        setattr(settings, k, v)
    return settings


class TestDetectMergeRequest:
    """Merge request detection from CI environment."""

    @patch.dict("os.environ", {"CI_MERGE_REQUEST_IID": "42"}, clear=True)
    def test_ci_merge_request_iid(self):
        assert _detect_gitlab_agent_type(_make_settings()) == "merge_request"

    def test_settings_merge_request_iid(self):
        settings = _make_settings(merge_request_iid="42")
        assert _detect_gitlab_agent_type(settings) == "merge_request"

    @patch.dict(
        "os.environ",
        {"CI_PIPELINE_SOURCE": "merge_request_event"},
        clear=True,
    )
    def test_pipeline_source_merge_request_event(self):
        assert _detect_gitlab_agent_type(_make_settings()) == "merge_request"


class TestDetectTask:
    """Task agent detection from CI environment."""

    @patch.dict("os.environ", {"TASK_TYPE": "custom"}, clear=True)
    def test_task_type_env(self):
        assert _detect_gitlab_agent_type(_make_settings()) == "task"

    @patch.dict("os.environ", {"CRON_TASK_TYPE": "security_audit"}, clear=True)
    def test_cron_task_type_env(self):
        assert _detect_gitlab_agent_type(_make_settings()) == "task"

    @patch.dict("os.environ", {"CI_PIPELINE_SOURCE": "schedule"}, clear=True)
    def test_pipeline_source_schedule(self):
        assert _detect_gitlab_agent_type(_make_settings()) == "task"


class TestDetectBranchReview:
    """Branch review detection from CI environment."""

    @patch.dict(
        "os.environ",
        {
            "CI_PIPELINE_SOURCE": "push",
            "CI_COMMIT_BRANCH": "feature-branch",
            "CI_DEFAULT_BRANCH": "main",
        },
        clear=True,
    )
    def test_push_to_non_default_branch(self):
        assert _detect_gitlab_agent_type(_make_settings()) == "branch_review"

    @patch.dict(
        "os.environ",
        {
            "CI_PIPELINE_SOURCE": "push",
            "CI_COMMIT_BRANCH": "main",
            "CI_DEFAULT_BRANCH": "main",
        },
        clear=True,
    )
    def test_push_to_default_branch_returns_none(self):
        assert _detect_gitlab_agent_type(_make_settings()) is None


class TestDetectNone:
    """Returns None when no GitLab context is detected."""

    @patch.dict("os.environ", {}, clear=True)
    def test_no_env_vars(self):
        assert _detect_gitlab_agent_type(_make_settings()) is None
