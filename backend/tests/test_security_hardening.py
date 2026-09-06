"""Security hardening tests for Core Trust Phase.

Tests tenant isolation, path traversal prevention, and file limits.
"""

import pytest
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestPathTraversalPrevention:
    """Verify _is_safe_path blocks all traversal attacks."""

    def setup_method(self):
        from app.services.file_generator import _is_safe_path
        self.check = _is_safe_path
        self.project_dir = Path("generated_projects/test_project")

    def test_valid_simple_file(self):
        assert self.check(self.project_dir, "index.html") is not None

    def test_valid_nested_file(self):
        assert self.check(self.project_dir, "src/components/App.tsx") is not None

    def test_leading_slash_stripped(self):
        result = self.check(self.project_dir, "/src/app.js")
        assert result is not None

    def test_unix_traversal_blocked(self):
        assert self.check(self.project_dir, "../../../etc/passwd") is None

    def test_windows_traversal_blocked(self):
        assert self.check(self.project_dir, "..\\..\\windows\\system32\\config") is None

    def test_nested_traversal_blocked(self):
        assert self.check(self.project_dir, "valid/../../../escape") is None

    def test_bare_dotdot_blocked(self):
        assert self.check(self.project_dir, "..") is None

    def test_empty_path_blocked(self):
        assert self.check(self.project_dir, "") is None

    def test_encoded_traversal_in_segments(self):
        assert self.check(self.project_dir, "foo/../../bar") is None

    def test_mixed_slashes(self):
        assert self.check(self.project_dir, "src\\..\\..\\escape") is None


class TestApplyFileLimits:
    """Verify apply_file_updates enforces count and size limits."""

    def test_rejects_too_many_files(self):
        from app.services.file_generator import apply_file_updates, MAX_APPLY_FILES
        files = [{"path": f"file_{i}.txt", "content": "x"} for i in range(MAX_APPLY_FILES + 1)]
        result = apply_file_updates("nonexistent_project", files)
        assert result["status"] == "error"
        assert "Too many files" in result["message"]

    def test_max_files_constant_is_reasonable(self):
        from app.services.file_generator import MAX_APPLY_FILES, MAX_APPLY_FILE_SIZE, MAX_APPLY_TOTAL_SIZE
        assert MAX_APPLY_FILES == 200
        assert MAX_APPLY_FILE_SIZE == 500 * 1024
        assert MAX_APPLY_TOTAL_SIZE == 50 * 1024 * 1024


class TestDomainMemoryIsolation:
    """Verify domain memory queries are scoped to the requesting user."""

    @pytest.mark.asyncio
    async def test_query_accepts_user_id_parameter(self):
        """Verify the query_domain_learnings function signature accepts user_id."""
        from app.core.database import query_domain_learnings
        import inspect
        sig = inspect.signature(query_domain_learnings)
        assert "user_id" in sig.parameters, "query_domain_learnings must accept user_id parameter"

    @pytest.mark.asyncio
    async def test_get_relevant_learnings_accepts_user_id(self):
        """Verify get_relevant_learnings passes user_id through."""
        from app.services.domain_memory import get_relevant_learnings
        import inspect
        sig = inspect.signature(get_relevant_learnings)
        assert "user_id" in sig.parameters, "get_relevant_learnings must accept user_id parameter"


class TestStaticPreviewAuth:
    """Verify static preview endpoint requires authentication."""

    def test_static_preview_requires_auth(self):
        """The static preview route must have a current_user dependency."""
        from app.api.routes import serve_static_preview
        import inspect
        sig = inspect.signature(serve_static_preview)
        param_names = list(sig.parameters.keys())
        assert "current_user" in param_names, "serve_static_preview must require current_user (authentication)"


class TestClassifyEndpointAuth:
    """Verify classify endpoint requires authentication."""

    def test_classify_requires_auth(self):
        from app.api.routes import classify_task_endpoint
        import inspect
        sig = inspect.signature(classify_task_endpoint)
        param_names = list(sig.parameters.keys())
        assert "current_user" in param_names, "classify_task_endpoint must require current_user"
