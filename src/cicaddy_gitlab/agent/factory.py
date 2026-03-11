"""GitLab-specific agent type detection for cicaddy plugin."""

import os
from typing import Optional

from cicaddy.utils.logger import get_logger

logger = get_logger(__name__)


def _detect_gitlab_agent_type(settings) -> Optional[str]:
    """Detect GitLab-specific agent types from CI environment variables.

    Handles merge_request, branch_review, and task detection from GitLab CI
    variables. Runs at priority 40 (before cicaddy core's detector at 50).
    """
    # Merge request context
    ci_mr_iid = os.getenv("CI_MERGE_REQUEST_IID")
    if ci_mr_iid:
        logger.info(f"Detected merge request context: CI_MERGE_REQUEST_IID={ci_mr_iid}")
        return "merge_request"

    mr_iid = getattr(settings, "merge_request_iid", None)
    if mr_iid:
        logger.info(f"Found merge request IID in settings: {mr_iid}")
        return "merge_request"

    # Task/scheduled context
    task_type = os.getenv("TASK_TYPE") or os.getenv("CRON_TASK_TYPE")
    if task_type:
        logger.info(f"Detected task context: TASK_TYPE={task_type}")
        return "task"

    # GitLab CI pipeline source detection
    pipeline_source = os.getenv("CI_PIPELINE_SOURCE")
    if pipeline_source == "merge_request_event":
        logger.info(
            f"Detected merge request context: CI_PIPELINE_SOURCE={pipeline_source}"
        )
        return "merge_request"
    elif pipeline_source == "schedule":
        logger.info(
            f"Detected task context: CI_PIPELINE_SOURCE={pipeline_source}, "
            f"TASK_TYPE={task_type}"
        )
        return "task"
    elif pipeline_source == "push":
        ci_commit_branch = os.getenv("CI_COMMIT_BRANCH")
        ci_default_branch = os.getenv("CI_DEFAULT_BRANCH", "main")
        if ci_commit_branch and ci_commit_branch != ci_default_branch:
            logger.info(
                f"Detected branch push context: CI_PIPELINE_SOURCE={pipeline_source}, "
                f"branch={ci_commit_branch}"
            )
            return "branch_review"

    return None
