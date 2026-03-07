"""Tests for GitLab settings configuration."""

import os
from unittest.mock import patch

import pytest


class TestSettings:
    """Test GitLab Settings class."""

    @patch.dict(os.environ, {
        "GITLAB_TOKEN": "test-token",
        "CI_API_V4_URL": "https://gitlab.com/api/v4",
        "CI_PROJECT_ID": "123",
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-key",
        "MCP_SERVERS_CONFIG": "[]",
    }, clear=False)
    def test_settings_loads_gitlab_vars(self):
        """Test that Settings loads GitLab CI variables."""
        from cicaddy_gitlab.config.settings import Settings

        settings = Settings(
            gitlab_token="test-token",
            gitlab_api_url="https://gitlab.com/api/v4",
            project_id="123",
            ai_provider="gemini",
            gemini_api_key="test-key",
            mcp_servers_config="[]",
        )
        assert settings.gitlab_token == "test-token"
        assert settings.gitlab_api_url == "https://gitlab.com/api/v4"
        assert settings.project_id == "123"

    @patch.dict(os.environ, {
        "CI_API_V4_URL": "https://gitlab.com/api/v4",
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-key",
        "MCP_SERVERS_CONFIG": "[]",
    }, clear=False)
    def test_settings_defaults(self):
        """Test Settings default values."""
        from cicaddy_gitlab.config.settings import Settings

        settings = Settings(
            ai_provider="gemini",
            gemini_api_key="test-key",
            mcp_servers_config="[]",
            gitlab_api_url="https://gitlab.com/api/v4",
        )
        assert settings.gitlab_token == ""
        assert settings.default_branch == "main"
        assert settings.merge_request_iid is None
        assert settings.project_id is None

    @patch.dict(os.environ, {
        "GITLAB_TOKEN": "test-token",
        "CI_API_V4_URL": "https://gitlab.com/api/v4",
        "CI_PROJECT_ID": "my-group/my-project",
        "CI_MERGE_REQUEST_IID": "42",
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-key",
        "MCP_SERVERS_CONFIG": "[]",
    }, clear=False)
    def test_settings_with_mr_iid(self):
        """Test Settings with merge request IID."""
        from cicaddy_gitlab.config.settings import Settings

        settings = Settings(
            gitlab_token="test-token",
            gitlab_api_url="https://gitlab.com/api/v4",
            project_id="my-group/my-project",
            merge_request_iid="42",
            ai_provider="gemini",
            gemini_api_key="test-key",
            mcp_servers_config="[]",
        )
        assert settings.merge_request_iid == "42"
        assert settings.project_id == "my-group/my-project"


class TestLoadSettings:
    """Test load_settings function."""

    @patch.dict(os.environ, {
        "GITLAB_TOKEN": "test-token",
        "CI_SERVER_URL": "https://gitlab.example.com",
        "CI_PROJECT_ID": "123",
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-key",
    }, clear=False)
    def test_load_settings_constructs_api_url(self):
        """Test that load_settings constructs API URL from CI_SERVER_URL."""
        # Remove CI_API_V4_URL to test auto-construction
        env = os.environ.copy()
        env.pop("CI_API_V4_URL", None)

        with patch.dict(os.environ, env, clear=True):
            from cicaddy_gitlab.config.settings import load_settings

            settings = load_settings()
            assert "gitlab.example.com" in settings.gitlab_api_url

    @patch.dict(os.environ, {
        "CI_JOB_TOKEN": "job-token-123",
        "CI_SERVER_URL": "https://gitlab.com",
        "CI_PROJECT_ID": "456",
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-key",
    }, clear=False)
    def test_load_settings_falls_back_to_job_token(self):
        """Test that load_settings uses CI_JOB_TOKEN when GITLAB_TOKEN missing."""
        env = os.environ.copy()
        env.pop("GITLAB_TOKEN", None)
        env.pop("CI_API_V4_URL", None)

        with patch.dict(os.environ, env, clear=True):
            from cicaddy_gitlab.config.settings import load_settings

            settings = load_settings()
            assert settings.gitlab_token == "job-token-123"
