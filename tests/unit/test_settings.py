"""Tests for GitLab settings configuration."""

import os
from unittest.mock import patch


class TestSettings:
    """Test GitLab Settings class."""

    @patch.dict(
        os.environ,
        {
            "GITLAB_TOKEN": "test-token",
            "CI_API_V4_URL": "https://gitlab.com/api/v4",
            "CI_PROJECT_ID": "123",
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-key",
            "MCP_SERVERS_CONFIG": "[]",
        },
        clear=False,
    )
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

    @patch.dict(
        os.environ,
        {
            "CI_API_V4_URL": "https://gitlab.com/api/v4",
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-key",
            "MCP_SERVERS_CONFIG": "[]",
        },
        clear=False,
    )
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

    @patch.dict(
        os.environ,
        {
            "GITLAB_TOKEN": "test-token",
            "CI_API_V4_URL": "https://gitlab.com/api/v4",
            "CI_PROJECT_ID": "my-group/my-project",
            "CI_MERGE_REQUEST_IID": "42",
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-key",
            "MCP_SERVERS_CONFIG": "[]",
        },
        clear=False,
    )
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

    @patch.dict(
        os.environ,
        {
            "CI_API_V4_URL": "https://gitlab.com/api/v4",
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-key",
            "MCP_SERVERS_CONFIG": "[]",
        },
        clear=False,
    )
    def test_post_mr_comment_defaults_true(self):
        """Test that post_mr_comment defaults to True."""
        from cicaddy_gitlab.config.settings import Settings

        settings = Settings(
            ai_provider="gemini",
            gemini_api_key="test-key",
            mcp_servers_config="[]",
            gitlab_api_url="https://gitlab.com/api/v4",
        )
        assert settings.post_mr_comment is True

    @patch.dict(
        os.environ,
        {
            "CI_API_V4_URL": "https://gitlab.com/api/v4",
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-key",
            "MCP_SERVERS_CONFIG": "[]",
            "POST_MR_COMMENT": "false",
        },
        clear=False,
    )
    def test_post_mr_comment_can_be_disabled(self):
        """Test that POST_MR_COMMENT=false disables comment posting."""
        from cicaddy_gitlab.config.settings import Settings

        settings = Settings(
            ai_provider="gemini",
            gemini_api_key="test-key",
            mcp_servers_config="[]",
            gitlab_api_url="https://gitlab.com/api/v4",
            post_mr_comment=False,
        )
        assert settings.post_mr_comment is False


class TestLoadSettings:
    """Test load_settings function."""

    @patch.dict(
        os.environ,
        {
            "GITLAB_TOKEN": "test-token",
            "CI_SERVER_URL": "https://gitlab.example.com",
            "CI_PROJECT_ID": "123",
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-key",
        },
        clear=False,
    )
    def test_load_settings_constructs_api_url(self):
        """Test that load_settings constructs API URL from CI_SERVER_URL."""
        # Remove CI_API_V4_URL to test auto-construction
        env = os.environ.copy()
        env.pop("CI_API_V4_URL", None)

        with patch.dict(os.environ, env, clear=True):
            from cicaddy_gitlab.config.settings import load_settings

            settings = load_settings()
            assert "gitlab.example.com" in settings.gitlab_api_url

    @patch.dict(
        os.environ,
        {
            "CI_JOB_TOKEN": "job-token-123",
            "CI_SERVER_URL": "https://gitlab.com",
            "CI_PROJECT_ID": "456",
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-key",
        },
        clear=False,
    )
    def test_load_settings_falls_back_to_job_token(self):
        """Test that load_settings uses CI_JOB_TOKEN when GITLAB_TOKEN missing."""
        env = os.environ.copy()
        env.pop("GITLAB_TOKEN", None)
        env.pop("CI_API_V4_URL", None)

        with patch.dict(os.environ, env, clear=True):
            from cicaddy_gitlab.config.settings import load_settings

            settings = load_settings()
            assert settings.gitlab_token == "job-token-123"

    @patch.dict(
        os.environ,
        {
            "GITLAB_TOKEN": "test-token",
            "CI_SERVER_URL": "https://gitlab.com",
            "CI_PROJECT_ID": "789",
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-key",
            "POST_MR_COMMENT": "false",
        },
        clear=False,
    )
    def test_load_settings_respects_post_mr_comment_false(self):
        """Test that load_settings parses POST_MR_COMMENT=false."""
        env = os.environ.copy()
        env.pop("CI_API_V4_URL", None)

        with patch.dict(os.environ, env, clear=True):
            from cicaddy_gitlab.config.settings import load_settings

            settings = load_settings()
            assert settings.post_mr_comment is False

    @patch.dict(
        os.environ,
        {
            "GITLAB_TOKEN": "test-token",
            "CI_SERVER_URL": "https://gitlab.com",
            "CI_PROJECT_ID": "789",
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-key",
            "POST_MR_COMMENT": "maybe",
        },
        clear=False,
    )
    def test_load_settings_warns_on_unrecognized_post_mr_comment(self):
        """Test that unrecognized POST_MR_COMMENT values log a warning and default to true."""
        env = os.environ.copy()
        env.pop("CI_API_V4_URL", None)

        with patch.dict(os.environ, env, clear=True):
            with patch("cicaddy_gitlab.config.settings.logger") as mock_logger:
                from cicaddy_gitlab.config.settings import load_settings

                settings = load_settings()
                assert settings.post_mr_comment is True
                mock_logger.warning.assert_any_call(
                    "Unrecognized POST_MR_COMMENT value 'maybe' — "
                    "expected true/false/1/0/yes/no. Defaulting to true."
                )

    @patch.dict(
        os.environ,
        {
            "GITLAB_TOKEN": "test-token",
            "CI_SERVER_URL": "https://gitlab.com",
            "CI_PROJECT_ID": "789",
            "AI_PROVIDER": "gemini-vertex",
            "GOOGLE_CLOUD_PROJECT": "my-gcp-project",
            "GOOGLE_CLOUD_LOCATION": "us-central1",
        },
        clear=False,
    )
    def test_load_settings_passes_google_cloud_project(self):
        """Test that GOOGLE_CLOUD_PROJECT is passed through to settings."""
        env = os.environ.copy()
        env.pop("CI_API_V4_URL", None)

        with patch.dict(os.environ, env, clear=True):
            from cicaddy_gitlab.config.settings import load_settings

            settings = load_settings()
            assert settings.google_cloud_project == "my-gcp-project"
            assert settings.google_cloud_location == "us-central1"

    @patch.dict(
        os.environ,
        {
            "GITLAB_TOKEN": "test-token",
            "CI_SERVER_URL": "https://gitlab.com",
            "CI_PROJECT_ID": "789",
            "AI_PROVIDER": "gemini-vertex",
            "GOOGLE_CLOUD_PROJECT": "my-gcp-project",
        },
        clear=False,
    )
    def test_load_settings_google_cloud_location_defaults(self):
        """Test that GOOGLE_CLOUD_LOCATION defaults to 'global' when not set."""
        env = os.environ.copy()
        env.pop("CI_API_V4_URL", None)
        env.pop("GOOGLE_CLOUD_LOCATION", None)

        with patch.dict(os.environ, env, clear=True):
            from cicaddy_gitlab.config.settings import load_settings

            settings = load_settings()
            assert settings.google_cloud_project == "my-gcp-project"
            assert settings.google_cloud_location == "global"

    @patch.dict(
        os.environ,
        {
            "GITLAB_TOKEN": "test-token",
            "CI_SERVER_URL": "https://gitlab.com",
            "CI_PROJECT_ID": "789",
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-key",
        },
        clear=False,
    )
    def test_load_settings_google_cloud_project_absent(self):
        """Test that GOOGLE_CLOUD_PROJECT absent results in None."""
        env = os.environ.copy()
        env.pop("CI_API_V4_URL", None)
        env.pop("GOOGLE_CLOUD_PROJECT", None)
        env.pop("GOOGLE_CLOUD_LOCATION", None)

        with patch.dict(os.environ, env, clear=True):
            from cicaddy_gitlab.config.settings import load_settings

            settings = load_settings()
            assert settings.google_cloud_project is None

    @patch.dict(
        os.environ,
        {
            "GITLAB_TOKEN": "test-token",
            "CI_SERVER_URL": "https://gitlab.com",
            "CI_PROJECT_ID": "789",
            "AI_PROVIDER": "gemini",
            "GEMINI_API_KEY": "test-key",
            "GOOGLE_CLOUD_PROJECT": "",
        },
        clear=False,
    )
    def test_load_settings_google_cloud_project_empty_string(self):
        """Test that empty string GOOGLE_CLOUD_PROJECT is not passed through."""
        env = os.environ.copy()
        env.pop("CI_API_V4_URL", None)

        with patch.dict(os.environ, env, clear=True):
            from cicaddy_gitlab.config.settings import load_settings

            settings = load_settings()
            assert settings.google_cloud_project is None

    @patch.dict(
        os.environ,
        {
            "GITLAB_TOKEN": "test-token",
            "CI_SERVER_URL": "https://gitlab.com",
            "CI_PROJECT_ID": "789",
            "AI_PROVIDER": "anthropic-vertex",
            "GOOGLE_CLOUD_PROJECT": "my-gcp-project",
            "ANTHROPIC_VERTEX_PROJECT_ID": "my-vertex-project",
        },
        clear=False,
    )
    def test_load_settings_anthropic_vertex_with_google_cloud_project(self):
        """Test anthropic-vertex provider uses GOOGLE_CLOUD_PROJECT for settings."""
        env = os.environ.copy()
        env.pop("CI_API_V4_URL", None)

        with patch.dict(os.environ, env, clear=True):
            from cicaddy_gitlab.config.settings import load_settings

            settings = load_settings()
            assert settings.google_cloud_project == "my-gcp-project"
            assert settings.anthropic_vertex_project_id == "my-vertex-project"
