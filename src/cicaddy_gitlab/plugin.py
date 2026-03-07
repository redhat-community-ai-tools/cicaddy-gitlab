"""Entry point callables for cicaddy plugin registration."""


def register_agents():
    """Register GitLab agents and detector with cicaddy.

    MergeRequestAgent and BranchReviewAgent are registered here because they
    require the GitLab BaseAIAgent (with GitLabAnalyzer for posting MR/commit
    comments). TaskAgent stays in cicaddy core — it doesn't need GitLab API.
    """
    from cicaddy.agent.factory import AgentFactory

    from cicaddy_gitlab.agent.branch_agent import BranchReviewAgent
    from cicaddy_gitlab.agent.factory import _detect_gitlab_agent_type
    from cicaddy_gitlab.agent.mr_agent import MergeRequestAgent

    AgentFactory.register("merge_request", MergeRequestAgent)
    AgentFactory.register("branch_review", BranchReviewAgent)
    AgentFactory.register_detector(_detect_gitlab_agent_type, priority=40)


def get_cli_args():
    """Return additional CLI argument mappings."""
    from cicaddy.cli.arg_mapping import ArgMapping

    return [
        ArgMapping(
            cli_arg="--project-url",
            env_var="CI_PROJECT_URL",
            help_text="GitLab project URL",
        ),
        ArgMapping(
            cli_arg="--mr-iid",
            env_var="CI_MERGE_REQUEST_IID",
            help_text="Merge request IID",
        ),
    ]


def get_env_vars():
    """Return additional environment variable names."""
    return [
        "GITLAB_TOKEN",
        "CI_PROJECT_ID",
        "CI_PROJECT_NAME",
        "CI_COMMIT_SHA",
        "CI_PIPELINE_ID",
    ]


def config_section(config, mask_fn, sensitive_vars):
    """Display GitLab Settings in config show."""
    print("\n[GitLab Settings]")
    for var in [
        "GITLAB_TOKEN",
        "CI_PROJECT_URL",
        "CI_PROJECT_ID",
        "CI_PROJECT_NAME",
        "CI_MERGE_REQUEST_IID",
    ]:
        value = config.get(var)
        if var in sensitive_vars:
            print(f"  {var}: {mask_fn(value)}")
        else:
            print(f"  {var}: {value or '(not set)'}")


def validate(config):
    """Validate GitLab-specific configuration."""
    import os

    errors, warnings = [], []
    print("\n[GitLab Integration]")

    # Check GITLAB_TOKEN
    token = config.get("GITLAB_TOKEN") or os.getenv("GITLAB_TOKEN")
    agent_type = config.get("AGENT_TYPE")
    if token:
        from cicaddy.cli.env_loader import mask_sensitive_value

        print(f"  GITLAB_TOKEN: {mask_sensitive_value(token)} ✓")
    elif agent_type in ("mr", "merge_request", "branch_review"):
        errors.append("GITLAB_TOKEN is required for MR/branch agents")
        print("  GITLAB_TOKEN: (not set) ✗")
    else:
        warnings.append("GITLAB_TOKEN not set")
        print("  GITLAB_TOKEN: (not set) ~")

    # Check project ID/URL
    pid = config.get("CI_PROJECT_ID") or os.getenv("CI_PROJECT_ID")
    purl = config.get("CI_PROJECT_URL") or os.getenv("CI_PROJECT_URL")
    if pid or purl:
        print(f"  CI_PROJECT_ID: {pid or '(from URL)'} ✓")
    elif agent_type in ("mr", "merge_request", "branch_review"):
        errors.append("CI_PROJECT_ID or CI_PROJECT_URL is required")
        print("  CI_PROJECT_ID: (not set) ✗")

    # Check MR IID
    mr_iid = config.get("CI_MERGE_REQUEST_IID") or os.getenv("CI_MERGE_REQUEST_IID")
    if agent_type in ("mr", "merge_request"):
        if mr_iid:
            print(f"  CI_MERGE_REQUEST_IID: {mr_iid} ✓")
        else:
            errors.append("CI_MERGE_REQUEST_IID is required for MR agent")
            print("  CI_MERGE_REQUEST_IID: (not set) ✗")

    return errors, warnings
