"""BaseAIAgent with GitLab platform integration."""

from cicaddy.agent.base import BaseAIAgent as _CicaddyBaseAIAgent
from cicaddy.utils.logger import get_logger

logger = get_logger(__name__)


class BaseAIAgent(_CicaddyBaseAIAgent):
    """BaseAIAgent with GitLab _setup_platform_integration override."""

    async def _setup_platform_integration(self):
        """Setup GitLab platform integration if project_id is available."""
        project_id = getattr(self.settings, "project_id", None)
        if project_id:
            from cicaddy_gitlab.gitlab_integration.analyzer import GitLabAnalyzer

            gitlab_api_url = getattr(self.settings, "gitlab_api_url", "")
            gitlab_token = getattr(self.settings, "gitlab_token", "")
            logger.info(f"Initializing GitLab analyzer with URL: {gitlab_api_url}")
            logger.info(f"Project ID: {project_id}")
            self.platform_analyzer = GitLabAnalyzer(
                token=gitlab_token,
                api_url=gitlab_api_url,
                project_id=project_id,
                ssl_verify=self.settings.ssl_verify,
            )
        else:
            logger.warning("No project ID available - platform analyzer disabled")
