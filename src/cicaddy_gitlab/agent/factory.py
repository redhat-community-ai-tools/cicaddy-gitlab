"""GitLab-specific agent type detection for cicaddy plugin."""

import os
from typing import Optional

from cicaddy.utils.logger import get_logger

logger = get_logger(__name__)


def _detect_gitlab_agent_type(settings) -> Optional[str]:
    """Detect GitLab-specific agent types from CI environment variables."""
    ci_mr_iid = os.getenv("CI_MERGE_REQUEST_IID")
    if ci_mr_iid:
        logger.info(f"Detected merge request context: CI_MERGE_REQUEST_IID={ci_mr_iid}")
        return "merge_request"

    mr_iid = getattr(settings, "merge_request_iid", None)
    if mr_iid:
        logger.info(f"Found merge request IID in settings: {mr_iid}")
        return "merge_request"

    return None
