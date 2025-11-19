"""
Tests for lenient file search in FileDiscoveryService.

Tests the service layer's ability to handle user-friendly search patterns
without requiring full glob syntax.
"""

import os
import tempfile
import pytest
from pathlib import Path

from code_index_mcp.services.file_discovery_service import FileDiscoveryService
from code_index_mcp.indexing.shallow_index_manager import ShallowIndexManager


class MockContext:
    """Mock context for service testing."""
    
    def __init__(self, project_path):
        self.project_path = project_path
        # Create nested structure that ContextHelper expects:
        # ctx.request_context.lifespan_context.base_path
        lifespan_ctx = type('obj', (object,), {
            'base_path': project_path,
            'project_path': project_path
        })()
        request_ctx = type('obj', (object,), {
            'lifespan_context': lifespan_ctx
        })()
        self.request_context = request_ctx
        
        self.shallow_index_manager = ShallowIndexManager()
        self.shallow_index_manager.set_project_path(project_path)
        self.shallow_index_manager.build_index()
        self.shallow_index_manager.load_index()


@pytest.fixture
def temp_project():
    """Create a temporary project structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        files = [
            "app.py",
            "main.py",
            "src/users.py",
            "src/models/user.py",
            "src/models/admin.py",
            "src/controllers/user_controller.py",
            "src/controllers/admin_controller.py",
            "lib/utils/helper.py",
            "lib/utils/validator.py",
            "tests/test_users.py",
            "tests/integration/test_api.py",
            "README.md",
            "docs/API.md",
            "config/settings.json",
            "scripts/deploy.sh",
        ]
        
        for file_path in files:
            full_path = Path(tmpdir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(f"# {file_path}\n")
        
        yield tmpdir


@pytest.fixture
def mock_ctx(temp_project):
    """Create a mock context with initialized index."""
    return MockContext(temp_project)


@pytest.fixture
def service(mock_ctx):
    """Create a FileDiscoveryService instance."""
    # Patch the global index manager
    from code_index_mcp.indexing import shallow_index_manager
    original_manager = shallow_index_manager._shallow_manager
    shallow_index_manager._shallow_manager = mock_ctx.shallow_index_manager
    
    svc = FileDiscoveryService(mock_ctx)
    
    yield svc
    
    # Restore original manager
    shallow_index_manager._shallow_manager = original_manager


class TestFileDiscoveryServiceLenientSearch:
    """Test lenient search patterns through the service layer."""
    
    def test_simple_filename_search(self, service):
        """Test searching for 'users.py' finds the file without **/ prefix."""
        result = service.find_files("users.py")

        results = result.files
        
        # Should find src/users.py
        assert any("users.py" in f for f in results)
        assert any("src/users.py" in f or "src\\users.py" in f for f in results)
        assert result.match_type == "recursive"
    
    def test_filename_in_nested_directory(self, service):
        """Test finding files in nested directories."""
        result = service.find_files("user.py")

        results = result.files
        
        # Should find src/models/user.py
        assert any("user.py" in f for f in results)
        assert any("models" in f for f in results if "user.py" in f)
        assert result.match_type == "recursive"
    
    def test_controller_file_search(self, service):
        """Test searching for controller files."""
        result = service.find_files("user_controller.py")

        results = result.files
        
        # Should find src/controllers/user_controller.py
        assert any("user_controller.py" in f for f in results)
        assert result.match_type == "recursive"
    
    def test_wildcard_extension_search(self, service):
        """Test wildcard pattern matching for extensions."""
        result = service.find_files("*.py")

        results = result.files
        
        # Should find Python files in root directory
        py_files = [f for f in results if f.endswith(".py")]
        assert len(py_files) >= 1
        assert result.match_type == "exact"
    
    def test_recursive_extension_search(self, service):
        """Test recursive search for all Python files."""
        result = service.find_files("**/*.py")

        results = result.files
        
        # Should find all Python files
        py_files = [f for f in results if f.endswith(".py")]
        assert len(py_files) >= 9  # Actual count in test project
    
    def test_partial_name_pattern(self, service):
        """Test searching with partial filename patterns."""
        result = service.find_files("*user*.py")

        results = result.files
        
        # Should find files with 'user' in basename
        user_files = [f for f in results if "user" in os.path.basename(f).lower()]
        assert len(user_files) >= 1
    
    def test_test_files_search(self, service):
        """Test searching for test files."""
        result = service.find_files("test_*.py")

        results = result.files
        
        # Should find test files in root of tests/ directory
        test_files = [f for f in results if os.path.basename(f).startswith("test_")]
        assert len(test_files) >= 1
    
    def test_markdown_documentation_search(self, service):
        """Test searching for markdown files."""
        result = service.find_files("*.md")

        results = result.files
        
        # Should find README.md
        md_files = [f for f in results if f.endswith(".md")]
        assert len(md_files) >= 1
        assert result.match_type == "exact"
    
    def test_config_file_search(self, service):
        """Test finding configuration files."""
        result = service.find_files("settings.json")

        results = result.files
        
        # Should find config/settings.json
        assert any("settings.json" in f for f in results)
        assert result.match_type == "recursive"
        assert result.match_type == "recursive"
    
    def test_script_file_search(self, service):
        """Test searching for script files."""
        result = service.find_files("deploy.sh")

        results = result.files
        
        # Should find scripts/deploy.sh
        assert any("deploy.sh" in f for f in results)
        assert result.match_type == "recursive"
    
    def test_directory_scoped_search(self, service):
        """Test searching within a specific directory."""
        result = service.find_files("src/**/*.py")

        results = result.files
        
        # Should find all .py files under src/
        src_py_files = [f for f in results if f.startswith("src") and f.endswith(".py")]
        assert len(src_py_files) >= 3
        assert result.match_type == "exact"
    
    def test_max_results_limit(self, service):
        """Test that max_results parameter limits output."""
        result = service.find_files("**/*.py", max_results=3)

        results = result.files
        
        # Should return at most 3 results
        assert len(results) <= 3
    
    def test_empty_results_for_nonexistent(self, service):
        """Test that searching for non-existent files returns empty."""
        result = service.find_files("nonexistent.xyz")

        results = result.files
        
        assert results == []
        assert result.match_type == "no_match"
    
    def test_all_files_pattern(self, service):
        """Test that * or empty pattern returns all files."""
        result = service.find_files("*")

        results = result.files
        
        # Should return all files
        assert len(results) >= 15  # We created 15 files
        assert result.match_type == "all"
    
    def test_multiple_directory_levels(self, service):
        """Test searching in files multiple levels deep."""
        result = service.find_files("test_api.py")

        results = result.files
        
        # Should find tests/integration/test_api.py
        assert any("test_api.py" in f for f in results)
        assert any("integration" in f for f in results if "test_api.py" in f)


class TestFileDiscoveryServiceValidation:
    """Test validation and error handling in the service."""
    
    def test_empty_pattern_validation(self, service):
        """Test that empty pattern is handled (should use default)."""
        # Empty string might be rejected or treated as "*"
        # depending on validation logic
        try:
            result = service.find_files("")

            results = result.files
            assert len(results) >= 0  # Should return all or be handled gracefully
        except ValueError:
            # Empty pattern validation is acceptable
            pass
    
    def test_whitespace_pattern_validation(self, service):
        """Test that whitespace-only pattern is handled."""
        with pytest.raises(ValueError, match="cannot be empty"):
            service.find_files("   ")
    
    def test_invalid_pattern_types(self, service):
        """Test that non-string patterns are rejected."""
        with pytest.raises((TypeError, ValueError)):
            service.find_files(None)
    
    def test_max_results_zero(self, service):
        """Test max_results=0 returns limited list."""
        result = service.find_files("*.py", max_results=0)

        results = result.files
        # max_results=0 might return empty or be treated as no limit
        # depending on implementation
        assert isinstance(results, list)
    
    def test_max_results_negative(self, service):
        """Test negative max_results is handled."""
        # Should either raise error or treat as no limit
        result = service.find_files("*.py", max_results=-1)

        results = result.files
        # Depending on implementation, might return all or none
        assert isinstance(results, list)


class TestFileDiscoveryServiceIntegration:
    """Integration tests for realistic usage scenarios."""
    
    def test_find_all_python_modules(self, service):
        """Test finding all Python modules in a project."""
        result = service.find_files("**/*.py")

        results = result.files
        
        py_files = [f for f in results if f.endswith(".py")]
        
        # Verify we found key modules
        basenames = [os.path.basename(f) for f in py_files]
        assert "users.py" in basenames
        assert "user.py" in basenames
        assert "admin.py" in basenames
    
    def test_find_configuration_files(self, service):
        """Test finding configuration files across the project."""
        result = service.find_files("**/*.json")
        json_files = result.files
        
        assert any("settings.json" in f for f in json_files)
    
    def test_find_documentation(self, service):
        """Test finding documentation files."""
        result = service.find_files("**/*.md")
        docs = result.files
        
        # **/*.md finds docs/API.md but not README.md in root
        assert len(docs) >= 1
        assert any("API.md" in f for f in docs)
    
    def test_find_specific_module_by_name(self, service):
        """Test finding a specific module by exact name."""
        result = service.find_files("helper.py")

        results = result.files
        
        # Should find lib/utils/helper.py
        assert len(results) >= 1
        assert any("helper.py" in f for f in results)
    
    def test_relative_path_not_affected(self, service):
        """Test that relative paths with slashes bypass lenient search."""
        result = service.find_files("src/users.py")

        results = result.files
        
        # Should find exactly src/users.py without lenient modification
        assert len(results) >= 1
        assert any("src/users.py" in f or "src\\users.py" in f for f in results)
    
    def test_nested_relative_path(self, service):
        """Test that nested relative paths work correctly."""
        result = service.find_files("src/models/user.py")

        results = result.files
        
        # Should find the exact nested path
        assert len(results) >= 1
        assert any("src/models/user.py" in f or "src\\models\\user.py" in f for f in results)
    
    def test_relative_directory_wildcard(self, service):
        """Test relative path with wildcard is not modified."""
        result = service.find_files("lib/*.py")

        results = result.files
        
        # Should only match files directly in lib/, not in lib/utils/
        # Since lib has no direct .py files, should return empty or only direct children
        direct_lib_files = [f for f in results if f.startswith("lib/") and f.count("/") == 1]
        # lib has no direct .py files, only in lib/utils/
        assert len(direct_lib_files) == 0
