"""Tests for cicaddy-gitlab plugin entry points."""


class TestGetDelegationBlockedTools:
    """Test delegation blocked tools registration."""

    def test_returns_set(self):
        from cicaddy_gitlab.plugin import get_delegation_blocked_tools

        result = get_delegation_blocked_tools()
        assert isinstance(result, set)

    def test_blocks_mr_note_tools(self):
        from cicaddy_gitlab.plugin import get_delegation_blocked_tools

        blocked = get_delegation_blocked_tools()
        assert "post_merge_request_note" in blocked
        assert "update_merge_request_note" in blocked
        assert "post_commit_note" in blocked
        assert "delete_commit_note" in blocked
        assert "create_merge_request_note" in blocked
        assert "create_note" in blocked

    def test_blocks_merge_and_update(self):
        from cicaddy_gitlab.plugin import get_delegation_blocked_tools

        blocked = get_delegation_blocked_tools()
        assert "update_merge_request" in blocked
        assert "merge_merge_request" in blocked

    def test_blocks_approve_operations(self):
        from cicaddy_gitlab.plugin import get_delegation_blocked_tools

        blocked = get_delegation_blocked_tools()
        assert "approve_merge_request" in blocked
        assert "unapprove_merge_request" in blocked

    def test_blocks_issue_mutations(self):
        from cicaddy_gitlab.plugin import get_delegation_blocked_tools

        blocked = get_delegation_blocked_tools()
        assert "create_issue" in blocked
        assert "update_issue" in blocked
        assert "close_issue" in blocked

    def test_blocks_branch_operations(self):
        from cicaddy_gitlab.plugin import get_delegation_blocked_tools

        blocked = get_delegation_blocked_tools()
        assert "create_branch" in blocked
        assert "delete_branch" in blocked

    def test_blocks_pipeline_and_tag_operations(self):
        from cicaddy_gitlab.plugin import get_delegation_blocked_tools

        blocked = get_delegation_blocked_tools()
        assert "create_pipeline" in blocked
        assert "cancel_pipeline" in blocked
        assert "retry_pipeline" in blocked
        assert "create_tag" in blocked
        assert "delete_tag" in blocked
        assert "create_release" in blocked

    def test_blocks_label_operations(self):
        from cicaddy_gitlab.plugin import get_delegation_blocked_tools

        blocked = get_delegation_blocked_tools()
        assert "add_label" in blocked
        assert "remove_label" in blocked

    def test_blocks_file_mutation_tools(self):
        from cicaddy_gitlab.plugin import get_delegation_blocked_tools

        blocked = get_delegation_blocked_tools()
        assert "create_file" in blocked
        assert "update_file" in blocked
        assert "delete_file" in blocked
        assert "cherry_pick" in blocked
        assert "revert" in blocked

    def test_blocks_notification_tools(self):
        from cicaddy_gitlab.plugin import get_delegation_blocked_tools

        blocked = get_delegation_blocked_tools()
        assert "send_slack_message" in blocked

    def test_does_not_block_read_operations(self):
        from cicaddy_gitlab.plugin import get_delegation_blocked_tools

        blocked = get_delegation_blocked_tools()
        assert "read_file" not in blocked
        assert "list_directory" not in blocked
        assert "get_merge_request" not in blocked
