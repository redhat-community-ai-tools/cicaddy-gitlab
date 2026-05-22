"""Tests for inline review comment functionality.

Tests cover:
- GitLabAnalyzer._is_line_in_diff_range() validation
- GitLabAnalyzer._get_diff_from_api() diff header generation
- GitLabAnalyzer.post_inline_comments() discussion creation
- MergeRequestAgent._format_inline_comment() body formatting
- MergeRequestAgent._post_inline_comments() orchestration
- send_notifications() integration with inline posting
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from cicaddy_gitlab.agent.mr_agent import MergeRequestAgent
from cicaddy_gitlab.gitlab_integration.analyzer import GitLabAnalyzer

# --- Fixtures ---


@pytest.fixture
def mock_gitlab():
    """Create a mock python-gitlab client."""
    with patch("cicaddy_gitlab.gitlab_integration.analyzer.gitlab") as mock_gl_mod:
        mock_gl = MagicMock()
        mock_gl_mod.Gitlab.return_value = mock_gl
        mock_project = MagicMock()
        mock_gl.projects.get.return_value = mock_project
        yield mock_gl, mock_project


@pytest.fixture
def analyzer(mock_gitlab):
    """Create an analyzer with mocked GitLab API."""
    return GitLabAnalyzer(
        token="test-token",
        api_url="https://gitlab.com/api/v4",
        project_id="123",
    )


def _make_agent(**settings_overrides):
    """Create an MR agent with mocked dependencies."""
    agent = MergeRequestAgent.__new__(MergeRequestAgent)
    agent.merge_request_iid = "42"
    agent.settings = MagicMock()
    agent.settings.post_mr_comment = True
    agent.settings.inline_review_comments = False
    agent.platform_analyzer = MagicMock()
    agent.platform_analyzer.post_merge_request_note = AsyncMock()
    agent.platform_analyzer.post_inline_comments = AsyncMock()
    agent.slack_notifier = None
    for k, v in settings_overrides.items():
        setattr(agent.settings, k, v)
    return agent


# --- Unified diff text for testing ---

# Full diff with --- /+++ headers (git diff output)
SAMPLE_DIFF_WITH_HEADERS = """\
--- a/src/main.py
+++ b/src/main.py
@@ -10,6 +10,8 @@ def existing():
     pass

 def new_function():
+    x = 1
+    y = 2
     return x + y

 def another():
"""

# Headerless diff (GitLab API mr.changes() format)
SAMPLE_DIFF_HEADERLESS = """\
@@ -10,6 +10,8 @@ def existing():
     pass

 def new_function():
+    x = 1
+    y = 2
     return x + y

 def another():
"""

# Default uses headerless format to match GitLab API behaviour
SAMPLE_DIFF = SAMPLE_DIFF_HEADERLESS

SAMPLE_CHANGES = [
    {
        "old_path": "src/main.py",
        "new_path": "src/main.py",
        "diff": SAMPLE_DIFF,
    }
]

SAMPLE_CHANGES_WITH_HEADERS = [
    {
        "old_path": "src/main.py",
        "new_path": "src/main.py",
        "diff": SAMPLE_DIFF_WITH_HEADERS,
    }
]


# =============================================================================
# _is_line_in_diff_range tests
# =============================================================================


class TestIsLineInDiffRange:
    """Test static method _is_line_in_diff_range."""

    def test_line_inside_hunk_returns_true(self, analyzer):
        """Line within a diff hunk new-side range returns True."""
        # Lines 10-17 are in the hunk (new_start=10, new_count=8)
        assert (
            GitLabAnalyzer._is_line_in_diff_range(SAMPLE_CHANGES, "src/main.py", 12)
            is True
        )

    def test_line_at_hunk_start_returns_true(self, analyzer):
        """First line of hunk returns True."""
        assert (
            GitLabAnalyzer._is_line_in_diff_range(SAMPLE_CHANGES, "src/main.py", 10)
            is True
        )

    def test_line_at_hunk_end_returns_true(self, analyzer):
        """Last line of hunk returns True."""
        assert (
            GitLabAnalyzer._is_line_in_diff_range(SAMPLE_CHANGES, "src/main.py", 17)
            is True
        )

    def test_line_outside_hunk_returns_false(self, analyzer):
        """Line outside any diff hunk returns False."""
        assert (
            GitLabAnalyzer._is_line_in_diff_range(SAMPLE_CHANGES, "src/main.py", 50)
            is False
        )

    def test_line_before_hunk_returns_false(self, analyzer):
        """Line before the hunk start returns False."""
        assert (
            GitLabAnalyzer._is_line_in_diff_range(SAMPLE_CHANGES, "src/main.py", 1)
            is False
        )

    def test_wrong_file_returns_false(self, analyzer):
        """Line in a file not in changes returns False."""
        assert (
            GitLabAnalyzer._is_line_in_diff_range(SAMPLE_CHANGES, "src/other.py", 12)
            is False
        )

    def test_empty_changes_returns_false(self, analyzer):
        """Empty changes list returns False."""
        assert GitLabAnalyzer._is_line_in_diff_range([], "src/main.py", 12) is False

    def test_change_without_diff_returns_false(self, analyzer):
        """Change entry without diff field returns False."""
        changes = [{"old_path": "src/main.py", "new_path": "src/main.py"}]
        assert (
            GitLabAnalyzer._is_line_in_diff_range(changes, "src/main.py", 10) is False
        )

    def test_multi_hunk_file(self, analyzer):
        """Line in second hunk of a multi-hunk file returns True."""
        multi_hunk_diff = """\
@@ -5,3 +5,4 @@ def foo():
     a = 1
     b = 2
+    c = 3
     return a + b
@@ -20,3 +21,4 @@ def bar():
     x = 10
     y = 20
+    z = 30
     return x + y
"""
        changes = [
            {
                "old_path": "src/app.py",
                "new_path": "src/app.py",
                "diff": multi_hunk_diff,
            }
        ]
        # First hunk: new lines 5-8
        assert GitLabAnalyzer._is_line_in_diff_range(changes, "src/app.py", 7) is True
        # Second hunk: new lines 21-24
        assert GitLabAnalyzer._is_line_in_diff_range(changes, "src/app.py", 23) is True
        # Gap between hunks
        assert GitLabAnalyzer._is_line_in_diff_range(changes, "src/app.py", 15) is False

    def test_headerless_diff_works(self, analyzer):
        """GitLab API headerless diff is handled by prepending synthetic headers."""
        assert (
            GitLabAnalyzer._is_line_in_diff_range(SAMPLE_CHANGES, "src/main.py", 12)
            is True
        )

    def test_diff_with_headers_works(self, analyzer):
        """Diff that already has --- /+++ headers is handled correctly."""
        assert (
            GitLabAnalyzer._is_line_in_diff_range(
                SAMPLE_CHANGES_WITH_HEADERS, "src/main.py", 12
            )
            is True
        )

    def test_string_line_number_coerced(self, analyzer):
        """String line numbers are coerced to int."""
        assert (
            GitLabAnalyzer._is_line_in_diff_range(SAMPLE_CHANGES, "src/main.py", "12")
            is True
        )

    def test_invalid_line_type_returns_false(self, analyzer):
        """Non-numeric line value returns False."""
        assert (
            GitLabAnalyzer._is_line_in_diff_range(SAMPLE_CHANGES, "src/main.py", "abc")
            is False
        )

    def test_none_line_returns_false(self, analyzer):
        """None line value returns False."""
        assert (
            GitLabAnalyzer._is_line_in_diff_range(SAMPLE_CHANGES, "src/main.py", None)
            is False
        )

    def test_multiple_matching_entries_checked(self, analyzer):
        """Multiple change entries for same file are all checked (continue, not return False)."""
        # First entry has no matching line, second entry does
        changes = [
            {
                "old_path": "src/main.py",
                "new_path": "src/main.py",
                "diff": "@@ -1,3 +1,3 @@\n a\n-b\n+c\n d\n",
            },
            {
                "old_path": "src/main.py",
                "new_path": "src/main.py",
                "diff": "@@ -50,3 +50,4 @@\n x\n y\n+z\n w\n",
            },
        ]
        # Line 52 is in the second entry's hunk (50-53), not the first's (1-3)
        assert GitLabAnalyzer._is_line_in_diff_range(changes, "src/main.py", 52) is True

    def test_empty_diff_entry_skipped_to_check_next(self):
        """Empty diff in first entry does not prevent checking subsequent entries."""
        changes = [
            {
                "old_path": "src/main.py",
                "new_path": "src/main.py",
                "diff": "",
            },
            {
                "old_path": "src/main.py",
                "new_path": "src/main.py",
                "diff": "@@ -10,3 +10,4 @@\n a\n b\n+c\n d\n",
            },
        ]
        assert GitLabAnalyzer._is_line_in_diff_range(changes, "src/main.py", 12) is True


# =============================================================================
# _get_diff_from_api tests
# =============================================================================


class TestGetDiffFromApi:
    """Test _get_diff_from_api diff header generation."""

    @pytest.mark.asyncio
    async def test_prepends_git_diff_headers(self, analyzer, mock_gitlab):
        """Generates diff --git, ---, +++ headers for each change."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()
        mock_mr.changes.return_value = {
            "changes": [
                {
                    "old_path": "src/main.py",
                    "new_path": "src/main.py",
                    "diff": "@@ -1,3 +1,4 @@\n line1\n+line2\n line3\n",
                }
            ]
        }

        result = await analyzer._get_diff_from_api(mock_mr)

        assert "diff --git a/src/main.py b/src/main.py" in result
        assert "--- a/src/main.py" in result
        assert "+++ b/src/main.py" in result
        assert "@@ -1,3 +1,4 @@" in result

    @pytest.mark.asyncio
    async def test_skips_empty_diff(self, analyzer, mock_gitlab):
        """Changes with empty diff text are skipped."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()
        mock_mr.changes.return_value = {
            "changes": [
                {"old_path": "empty.py", "new_path": "empty.py", "diff": ""},
                {
                    "old_path": "real.py",
                    "new_path": "real.py",
                    "diff": "@@ -1 +1 @@\n-old\n+new\n",
                },
            ]
        }

        result = await analyzer._get_diff_from_api(mock_mr)

        assert "empty.py" not in result
        assert "diff --git a/real.py b/real.py" in result

    @pytest.mark.asyncio
    async def test_renamed_file_uses_both_paths(self, analyzer, mock_gitlab):
        """Renamed files show old_path in --- and new_path in +++."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()
        mock_mr.changes.return_value = {
            "changes": [
                {
                    "old_path": "old_name.py",
                    "new_path": "new_name.py",
                    "diff": "@@ -1 +1 @@\n-old\n+new\n",
                }
            ]
        }

        result = await analyzer._get_diff_from_api(mock_mr)

        assert "diff --git a/old_name.py b/new_name.py" in result
        assert "--- a/old_name.py" in result
        assert "+++ b/new_name.py" in result

    @pytest.mark.asyncio
    async def test_multiple_files(self, analyzer, mock_gitlab):
        """Multiple changes produce concatenated diff output."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()
        mock_mr.changes.return_value = {
            "changes": [
                {
                    "old_path": "a.py",
                    "new_path": "a.py",
                    "diff": "@@ -1 +1 @@\n-x\n+y\n",
                },
                {
                    "old_path": "b.py",
                    "new_path": "b.py",
                    "diff": "@@ -1 +1 @@\n-1\n+2\n",
                },
            ]
        }

        result = await analyzer._get_diff_from_api(mock_mr)

        assert "diff --git a/a.py b/a.py" in result
        assert "diff --git a/b.py b/b.py" in result

    @pytest.mark.asyncio
    async def test_no_changes_returns_empty(self, analyzer, mock_gitlab):
        """Empty changes list returns empty string."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()
        mock_mr.changes.return_value = {"changes": []}

        result = await analyzer._get_diff_from_api(mock_mr)

        assert result == ""

    @pytest.mark.asyncio
    async def test_iid_string_fetches_mr(self, analyzer, mock_gitlab):
        """Passing a string IID fetches the MR from the project."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()
        mock_mr.changes.return_value = {
            "changes": [
                {
                    "old_path": "f.py",
                    "new_path": "f.py",
                    "diff": "@@ -1 +1 @@\n-a\n+b\n",
                }
            ]
        }
        mock_project.mergerequests.get.return_value = mock_mr

        result = await analyzer._get_diff_from_api("99")

        mock_project.mergerequests.get.assert_called_once_with("99")
        assert "diff --git a/f.py b/f.py" in result

    @pytest.mark.asyncio
    async def test_does_not_double_headers(self, analyzer, mock_gitlab):
        """Diff text already containing --- headers is not re-wrapped."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()
        mock_mr.changes.return_value = {
            "changes": [
                {
                    "old_path": "src/main.py",
                    "new_path": "src/main.py",
                    "diff": "--- a/src/main.py\n+++ b/src/main.py\n@@ -1 +1 @@\n-old\n+new\n",
                }
            ]
        }

        result = await analyzer._get_diff_from_api(mock_mr)

        assert result.count("--- a/src/main.py") == 1
        assert "diff --git" not in result


# =============================================================================
# post_inline_comments tests
# =============================================================================


def _setup_mr_mock(mock_project, changes=None, diff_refs=None):
    """Set up a mock MR with changes and diff version for post_inline_comments."""
    mock_mr = MagicMock()
    mock_mr.changes.return_value = {"changes": changes or SAMPLE_CHANGES}

    mock_diff_version = MagicMock()
    refs = diff_refs or {"base": "aaa", "head": "bbb", "start": "ccc"}
    mock_diff_version.base_commit_sha = refs["base"]
    mock_diff_version.head_commit_sha = refs["head"]
    mock_diff_version.start_commit_sha = refs["start"]
    mock_mr.diffs.list.return_value = [mock_diff_version]

    mock_project.mergerequests.get.return_value = mock_mr
    return mock_mr


class TestPostInlineComments:
    """Test post_inline_comments discussion creation."""

    @pytest.mark.asyncio
    async def test_posts_valid_inline_comment(self, analyzer, mock_gitlab):
        """Inline comment posted for finding with line in diff range."""
        _, mock_project = mock_gitlab
        mock_mr = _setup_mr_mock(mock_project)
        mock_mr.discussions.create.return_value = MagicMock()

        findings = [{"file": "src/main.py", "line": 12, "body": "Fix this."}]

        result = await analyzer.post_inline_comments(
            mr_iid="42",
            findings=findings,
        )

        assert result["posted"] == 1
        assert result["skipped"] == 0
        assert result["failed"] == 0
        mock_mr.discussions.create.assert_called_once()
        call_args = mock_mr.discussions.create.call_args[0][0]
        assert call_args["body"] == "Fix this."
        assert call_args["position"]["new_line"] == 12
        assert call_args["position"]["new_path"] == "src/main.py"
        assert call_args["position"]["position_type"] == "text"

    @pytest.mark.asyncio
    async def test_skips_finding_outside_diff(self, analyzer, mock_gitlab):
        """Finding with line outside diff range is skipped."""
        _, mock_project = mock_gitlab
        mock_mr = _setup_mr_mock(mock_project)

        findings = [{"file": "src/main.py", "line": 999, "body": "Out of range."}]

        result = await analyzer.post_inline_comments(
            mr_iid="42",
            findings=findings,
        )

        assert result["posted"] == 0
        assert result["skipped"] == 1
        mock_mr.discussions.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_api_error(self, analyzer, mock_gitlab):
        """API error during discussion creation counts as failed."""
        _, mock_project = mock_gitlab
        mock_mr = _setup_mr_mock(mock_project)
        mock_mr.discussions.create.side_effect = Exception("API error")

        findings = [{"file": "src/main.py", "line": 12, "body": "Fix this."}]

        result = await analyzer.post_inline_comments(
            mr_iid="42",
            findings=findings,
        )

        assert result["posted"] == 0
        assert result["failed"] == 1

    @pytest.mark.asyncio
    async def test_mixed_valid_and_invalid_findings(self, analyzer, mock_gitlab):
        """Processes multiple findings: some posted, some skipped."""
        _, mock_project = mock_gitlab
        mock_mr = _setup_mr_mock(mock_project)
        mock_mr.discussions.create.return_value = MagicMock()

        findings = [
            {"file": "src/main.py", "line": 12, "body": "Valid."},
            {"file": "src/main.py", "line": 999, "body": "Out of range."},
            {"file": "src/other.py", "line": 5, "body": "Wrong file."},
        ]

        result = await analyzer.post_inline_comments(
            mr_iid="42",
            findings=findings,
        )

        assert result["posted"] == 1
        assert result["skipped"] == 2

    @pytest.mark.asyncio
    async def test_empty_findings_list(self, analyzer, mock_gitlab):
        """Empty findings list returns zero counts."""
        _, mock_project = mock_gitlab
        _setup_mr_mock(mock_project)

        result = await analyzer.post_inline_comments(
            mr_iid="42",
            findings=[],
        )

        assert result["posted"] == 0
        assert result["skipped"] == 0
        assert result["failed"] == 0

    @pytest.mark.asyncio
    async def test_renamed_file_uses_old_path(self, analyzer, mock_gitlab):
        """Renamed file uses old_path from change entry, not new_path."""
        _, mock_project = mock_gitlab
        renamed_changes = [
            {
                "old_path": "src/old_name.py",
                "new_path": "src/new_name.py",
                "diff": SAMPLE_DIFF,
            }
        ]
        mock_mr = _setup_mr_mock(mock_project, changes=renamed_changes)
        mock_mr.discussions.create.return_value = MagicMock()

        findings = [{"file": "src/new_name.py", "line": 12, "body": "Fix this."}]

        result = await analyzer.post_inline_comments(
            mr_iid="42",
            findings=findings,
        )

        assert result["posted"] == 1
        call_args = mock_mr.discussions.create.call_args[0][0]
        assert call_args["position"]["new_path"] == "src/new_name.py"
        assert call_args["position"]["old_path"] == "src/old_name.py"

    @pytest.mark.asyncio
    async def test_fetches_diff_refs_internally(self, analyzer, mock_gitlab):
        """post_inline_comments fetches diff refs from MR diffs API."""
        _, mock_project = mock_gitlab
        mock_mr = _setup_mr_mock(
            mock_project,
            diff_refs={"base": "base123", "head": "head456", "start": "start789"},
        )
        mock_mr.discussions.create.return_value = MagicMock()

        findings = [{"file": "src/main.py", "line": 12, "body": "Fix."}]

        await analyzer.post_inline_comments(mr_iid="42", findings=findings)

        call_args = mock_mr.discussions.create.call_args[0][0]
        assert call_args["position"]["base_sha"] == "base123"
        assert call_args["position"]["head_sha"] == "head456"
        assert call_args["position"]["start_sha"] == "start789"

    @pytest.mark.asyncio
    async def test_returns_early_on_empty_diffs(self, analyzer, mock_gitlab):
        """Returns all-skipped when MR has no diff versions."""
        _, mock_project = mock_gitlab
        mock_mr = MagicMock()
        mock_mr.changes.return_value = {"changes": SAMPLE_CHANGES}
        mock_mr.diffs.list.return_value = []
        mock_project.mergerequests.get.return_value = mock_mr

        findings = [{"file": "src/main.py", "line": 12, "body": "Fix."}]

        result = await analyzer.post_inline_comments(mr_iid="42", findings=findings)

        assert result == {"posted": 0, "skipped": 1, "failed": 0}
        mock_mr.discussions.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_coerces_string_line_to_int(self, analyzer, mock_gitlab):
        """String line numbers are coerced to int for the API position."""
        _, mock_project = mock_gitlab
        mock_mr = _setup_mr_mock(mock_project)
        mock_mr.discussions.create.return_value = MagicMock()

        findings = [{"file": "src/main.py", "line": "12", "body": "Fix."}]

        result = await analyzer.post_inline_comments(mr_iid="42", findings=findings)

        assert result["posted"] == 1
        call_args = mock_mr.discussions.create.call_args[0][0]
        assert call_args["position"]["new_line"] == 12
        assert isinstance(call_args["position"]["new_line"], int)

    @pytest.mark.asyncio
    async def test_skips_invalid_line_type(self, analyzer, mock_gitlab):
        """Findings with non-numeric line values are skipped."""
        _, mock_project = mock_gitlab
        _setup_mr_mock(mock_project)

        findings = [{"file": "src/main.py", "line": "abc", "body": "Bad."}]

        result = await analyzer.post_inline_comments(mr_iid="42", findings=findings)

        assert result["skipped"] == 1
        assert result["posted"] == 0

    @pytest.mark.asyncio
    async def test_caps_at_max_comments(self, analyzer, mock_gitlab):
        """Findings beyond the cap are not posted."""
        _, mock_project = mock_gitlab
        mock_mr = _setup_mr_mock(mock_project)
        mock_mr.discussions.create.return_value = MagicMock()

        findings = [
            {"file": "src/main.py", "line": 12, "body": f"Issue {i}"} for i in range(30)
        ]

        result = await analyzer.post_inline_comments(mr_iid="42", findings=findings)

        assert result["posted"] + result["skipped"] + result["failed"] == 25
        assert mock_mr.discussions.create.call_count == 25


# =============================================================================
# _format_inline_comment tests
# =============================================================================


class TestFormatInlineComment:
    """Test static method _format_inline_comment."""

    def test_critical_severity(self):
        finding = {
            "severity": "critical",
            "message": "SQL injection vulnerability",
            "suggestion": "Use parameterized queries",
            "agent_source": "security-reviewer",
        }
        result = MergeRequestAgent._format_inline_comment(finding)
        assert result.startswith("\U0001f534 **CRITICAL**")
        assert "SQL injection vulnerability" in result
        assert "**Suggestion**: Use parameterized queries" in result
        assert "<sub>Source: security-reviewer</sub>" in result

    def test_major_severity(self):
        finding = {"severity": "major", "message": "Missing null check"}
        result = MergeRequestAgent._format_inline_comment(finding)
        assert result.startswith("\U0001f7e0 **MAJOR**")
        assert "Missing null check" in result

    def test_minor_severity(self):
        finding = {"severity": "minor", "message": "Consider renaming"}
        result = MergeRequestAgent._format_inline_comment(finding)
        assert result.startswith("\U0001f7e1 **MINOR**")

    def test_nit_severity(self):
        finding = {"severity": "nit", "message": "Trailing whitespace"}
        result = MergeRequestAgent._format_inline_comment(finding)
        assert result.startswith("\U0001f535 **NIT**")

    def test_high_severity(self):
        finding = {"severity": "high", "message": "Unsafe deserialization"}
        result = MergeRequestAgent._format_inline_comment(finding)
        assert result.startswith("\U0001f534 **HIGH**")

    def test_medium_severity(self):
        finding = {"severity": "medium", "message": "Missing input validation"}
        result = MergeRequestAgent._format_inline_comment(finding)
        assert result.startswith("\U0001f7e0 **MEDIUM**")

    def test_low_severity(self):
        finding = {"severity": "low", "message": "Consider adding docstring"}
        result = MergeRequestAgent._format_inline_comment(finding)
        assert result.startswith("\U0001f7e1 **LOW**")

    def test_info_severity(self):
        finding = {"severity": "info", "message": "FYI note"}
        result = MergeRequestAgent._format_inline_comment(finding)
        assert result.startswith("\U0001f535 **INFO**")

    def test_warning_severity(self):
        finding = {"severity": "warning", "message": "Deprecated API"}
        result = MergeRequestAgent._format_inline_comment(finding)
        assert result.startswith("\U0001f7e1 **WARNING**")

    def test_unknown_severity_uses_info_emoji(self):
        finding = {"severity": "unknown", "message": "Something"}
        result = MergeRequestAgent._format_inline_comment(finding)
        assert result.startswith("ℹ️ **UNKNOWN**")

    def test_missing_severity_defaults_to_info(self):
        finding = {"message": "No severity specified"}
        result = MergeRequestAgent._format_inline_comment(finding)
        assert "\U0001f535 **INFO**" in result

    def test_no_suggestion_omitted(self):
        finding = {"severity": "major", "message": "Issue found"}
        result = MergeRequestAgent._format_inline_comment(finding)
        assert "Suggestion" not in result

    def test_no_agent_source_omitted(self):
        finding = {"severity": "minor", "message": "Note"}
        result = MergeRequestAgent._format_inline_comment(finding)
        assert "Source" not in result


# =============================================================================
# _post_inline_comments (MR agent orchestration) tests
# =============================================================================


class TestMrAgentPostInlineComments:
    """Test MergeRequestAgent._post_inline_comments orchestration."""

    @pytest.mark.asyncio
    async def test_calls_analyzer_post_inline(self):
        """Orchestrates formatting and posting (diff refs fetched by analyzer)."""
        agent = _make_agent(inline_review_comments=True)
        agent.platform_analyzer.post_inline_comments.return_value = {
            "posted": 1,
            "skipped": 0,
            "failed": 0,
        }

        findings = [
            {
                "file": "src/main.py",
                "line": 12,
                "severity": "major",
                "message": "Fix this",
            }
        ]

        await agent._post_inline_comments(findings)

        agent.platform_analyzer.post_inline_comments.assert_awaited_once()
        call_kwargs = agent.platform_analyzer.post_inline_comments.call_args
        # Verify the findings passed have formatted bodies
        posted_findings = (
            call_kwargs[1]["findings"] if call_kwargs[1] else call_kwargs[0][1]
        )
        assert len(posted_findings) == 1

    @pytest.mark.asyncio
    async def test_formats_finding_bodies(self):
        """Each finding gets a formatted body via _format_inline_comment."""
        agent = _make_agent(inline_review_comments=True)
        agent.platform_analyzer.post_inline_comments.return_value = {
            "posted": 1,
            "skipped": 0,
            "failed": 0,
        }

        findings = [
            {
                "file": "src/main.py",
                "line": 12,
                "severity": "critical",
                "message": "Security issue",
                "suggestion": "Fix it",
            }
        ]

        await agent._post_inline_comments(findings)

        call_args = agent.platform_analyzer.post_inline_comments.call_args
        posted_findings = call_args[1]["findings"]
        assert "\U0001f534 **CRITICAL**" in posted_findings[0]["body"]


# =============================================================================
# send_notifications integration tests
# =============================================================================


class TestSendNotificationsInline:
    """Test send_notifications with inline review comment integration."""

    @pytest.mark.asyncio
    async def test_inline_comments_posted_when_enabled(self):
        """Inline comments are posted when setting is enabled and findings exist."""
        agent = _make_agent(inline_review_comments=True)
        agent.platform_analyzer.post_inline_comments.return_value = {
            "posted": 1,
            "skipped": 0,
            "failed": 0,
        }

        analysis_result = {
            "ai_analysis": "Review text.",
            "findings": [
                {
                    "file": "src/main.py",
                    "line": 12,
                    "severity": "major",
                    "message": "Issue found",
                }
            ],
        }

        await agent.send_notifications({"report_id": "r1"}, analysis_result)

        # Summary comment posted
        agent.platform_analyzer.post_merge_request_note.assert_awaited_once()
        # Inline comments posted
        agent.platform_analyzer.post_inline_comments.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_inline_comments_skipped_when_disabled(self):
        """Inline comments are NOT posted when setting is disabled."""
        agent = _make_agent(inline_review_comments=False)

        analysis_result = {
            "ai_analysis": "Review text.",
            "findings": [
                {
                    "file": "src/main.py",
                    "line": 12,
                    "severity": "major",
                    "message": "Issue found",
                }
            ],
        }

        await agent.send_notifications({"report_id": "r1"}, analysis_result)

        # Summary comment posted
        agent.platform_analyzer.post_merge_request_note.assert_awaited_once()
        # Inline comments NOT posted
        agent.platform_analyzer.post_inline_comments.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_inline_comments_skipped_without_findings(self):
        """Inline comments are NOT posted when there are no findings."""
        agent = _make_agent(inline_review_comments=True)

        analysis_result = {
            "ai_analysis": "Review text.",
            "findings": [],
        }

        await agent.send_notifications({"report_id": "r1"}, analysis_result)

        agent.platform_analyzer.post_inline_comments.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_inline_comments_skipped_without_line_findings(self):
        """Findings without line numbers do not trigger inline posting."""
        agent = _make_agent(inline_review_comments=True)

        analysis_result = {
            "ai_analysis": "Review text.",
            "findings": [
                {"file": "src/main.py", "severity": "major", "message": "No line"},
                {"line": 10, "severity": "minor", "message": "No file"},
            ],
        }

        await agent.send_notifications({"report_id": "r1"}, analysis_result)

        agent.platform_analyzer.post_inline_comments.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_inline_comments_error_does_not_break_notifications(self):
        """Error in inline posting does not prevent other notifications."""
        agent = _make_agent(inline_review_comments=True)
        agent.platform_analyzer.post_inline_comments.side_effect = Exception("API down")

        analysis_result = {
            "ai_analysis": "Review text.",
            "findings": [
                {
                    "file": "src/main.py",
                    "line": 12,
                    "severity": "major",
                    "message": "Bug",
                },
            ],
        }

        # Should not raise
        await agent.send_notifications({"report_id": "r1"}, analysis_result)

        # Summary comment still posted
        agent.platform_analyzer.post_merge_request_note.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_inline_comments_skipped_no_platform_analyzer(self):
        """No inline posting when platform_analyzer is None."""
        agent = _make_agent(inline_review_comments=True)
        agent.platform_analyzer = None

        analysis_result = {
            "ai_analysis": "Review text.",
            "findings": [
                {
                    "file": "src/main.py",
                    "line": 12,
                    "severity": "major",
                    "message": "Bug",
                },
            ],
        }

        # Should not raise (no platform_analyzer means skip all comments)
        await agent.send_notifications({"report_id": "r1"}, analysis_result)

    @pytest.mark.asyncio
    async def test_no_findings_key_in_result(self):
        """Missing 'findings' key in analysis_result does not trigger inline."""
        agent = _make_agent(inline_review_comments=True)

        analysis_result = {"ai_analysis": "Review text."}

        await agent.send_notifications({"report_id": "r1"}, analysis_result)

        agent.platform_analyzer.post_inline_comments.assert_not_awaited()


# =============================================================================
# Settings tests
# =============================================================================


class TestInlineReviewSettings:
    """Test the inline_review_comments setting."""

    def test_defaults_to_false(self):
        """inline_review_comments defaults to False."""
        from cicaddy_gitlab.config.settings import Settings

        settings = Settings(
            ai_provider="gemini",
            gemini_api_key="test-key",
            mcp_servers_config="[]",
            gitlab_api_url="https://gitlab.com/api/v4",
        )
        assert settings.inline_review_comments is False

    def test_can_be_enabled(self):
        """inline_review_comments can be set to True via env var."""
        import os
        from unittest.mock import patch as mock_patch

        with mock_patch.dict(
            os.environ,
            {
                "CI_API_V4_URL": "https://gitlab.com/api/v4",
                "AI_PROVIDER": "gemini",
                "GEMINI_API_KEY": "test-key",
                "MCP_SERVERS_CONFIG": "[]",
                "INLINE_REVIEW_COMMENTS": "true",
            },
            clear=False,
        ):
            from cicaddy_gitlab.config.settings import Settings

            settings = Settings(
                ai_provider="gemini",
                gemini_api_key="test-key",
                mcp_servers_config="[]",
                gitlab_api_url="https://gitlab.com/api/v4",
            )
            assert settings.inline_review_comments is True

    def test_load_settings_wires_inline_review_true(self):
        """load_settings() parses INLINE_REVIEW_COMMENTS env var."""
        import os
        from unittest.mock import patch as mock_patch

        with mock_patch.dict(
            os.environ,
            {
                "CI_API_V4_URL": "https://gitlab.com/api/v4",
                "AI_PROVIDER": "gemini",
                "GEMINI_API_KEY": "test-key",
                "MCP_SERVERS_CONFIG": "[]",
                "INLINE_REVIEW_COMMENTS": "true",
            },
            clear=False,
        ):
            from cicaddy_gitlab.config.settings import load_settings

            settings = load_settings()
            assert settings.inline_review_comments is True

    def test_load_settings_wires_inline_review_false(self):
        """load_settings() parses INLINE_REVIEW_COMMENTS=false."""
        import os
        from unittest.mock import patch as mock_patch

        with mock_patch.dict(
            os.environ,
            {
                "CI_API_V4_URL": "https://gitlab.com/api/v4",
                "AI_PROVIDER": "gemini",
                "GEMINI_API_KEY": "test-key",
                "MCP_SERVERS_CONFIG": "[]",
                "INLINE_REVIEW_COMMENTS": "false",
            },
            clear=False,
        ):
            from cicaddy_gitlab.config.settings import load_settings

            settings = load_settings()
            assert settings.inline_review_comments is False

    def test_load_settings_inline_review_invalid_value_warns(self):
        """load_settings() warns on unrecognized INLINE_REVIEW_COMMENTS value."""
        import os
        from unittest.mock import patch as mock_patch

        with mock_patch.dict(
            os.environ,
            {
                "CI_API_V4_URL": "https://gitlab.com/api/v4",
                "AI_PROVIDER": "gemini",
                "GEMINI_API_KEY": "test-key",
                "MCP_SERVERS_CONFIG": "[]",
                "INLINE_REVIEW_COMMENTS": "invalid",
            },
            clear=False,
        ):
            from cicaddy_gitlab.config.settings import load_settings

            settings = load_settings()
            # Invalid value should fall back to default (False)
            assert settings.inline_review_comments is False


class TestFormatInlineCommentMissingMessage:
    """Test _format_inline_comment with missing message key (Fix #4 / #11)."""

    def test_missing_message_key_uses_default(self):
        """Finding without 'message' key uses default text."""
        finding = {"severity": "major"}
        result = MergeRequestAgent._format_inline_comment(finding)
        assert "No description provided" in result
        assert "**MAJOR**" in result
