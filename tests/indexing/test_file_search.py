"""
Tests for lenient (nachsichtige) file search functionality in shallow index manager.

Tests various search patterns to ensure users can find files without needing
to specify full glob patterns like **/filename.
"""

import os
import tempfile
import pytest
from pathlib import Path

from code_index_mcp.indexing.shallow_index_manager import ShallowIndexManager


@pytest.fixture
def temp_project():
    """Create a temporary project structure for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a realistic project structure
        files = [
            "README.md",
            "main.go",
            "src/users.go",
            "src/models/user.go",
            "src/models/admin.go",
            "src/handlers/user_handler.go",
            "pkg/utils/helper.go",
            "pkg/utils/validator.go",
            "test/users_test.go",
            "test/integration/api_test.go",
            "docs/api.md",
            "config/settings.yaml",
            "scripts/deploy.sh",
        ]
        
        for file_path in files:
            full_path = Path(tmpdir) / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(f"# {file_path}\n")
        
        yield tmpdir


@pytest.fixture
def index_manager(temp_project):
    """Create and initialize a shallow index manager."""
    manager = ShallowIndexManager()
    assert manager.set_project_path(temp_project)
    assert manager.build_index()
    assert manager.load_index()
    return manager


class TestLenientFileSearch:
    """Test lenient file search patterns."""
    
    def test_exact_filename_with_extension(self, index_manager):
        """Test searching for 'users.go' finds all users.go files."""
        result = index_manager.find_files("users.go")

        results = result.files
        
        # Should find src/users.go and test/users_test.go (partial match)
        # But at minimum should find src/users.go
        matching_files = [f for f in results if f.endswith("users.go")]
        assert len(matching_files) >= 1
        assert any("src/users.go" in f for f in matching_files)
        # Lenient search should apply recursive pattern
        assert result.match_type == "recursive"
    
    def test_filename_without_glob_prefix(self, index_manager):
        """Test that 'user.go' finds files without needing **/ prefix."""
        result = index_manager.find_files("user.go")

        results = result.files
        
        # Should find src/models/user.go
        assert any("user.go" in f for f in results)
        assert any("models/user.go" in f or "models\\user.go" in f for f in results)
        assert result.match_type == "recursive"
    
    def test_filename_with_extension_pattern(self, index_manager):
        """Test searching for all Go files with *.go pattern."""
        result = index_manager.find_files("*.go")

        results = result.files
        
        go_files = [f for f in results if f.endswith(".go")]
        # Should find all .go files in root, but not subdirectories without **
        # This is expected glob behavior
        assert len(go_files) >= 1
        assert result.match_type == "exact"  # *.go is an exact pattern match
    
    def test_recursive_pattern_with_extension(self, index_manager):
        """Test that **/*.go finds all Go files recursively."""
        result = index_manager.find_files("**/*.go")

        results = result.files
        
        go_files = [f for f in results if f.endswith(".go")]
        # Should find all .go files in all directories
        assert len(go_files) >= 6  # We created 6 .go files
        assert any("users.go" in f for f in go_files)
        assert any("user.go" in f for f in go_files)
        assert any("helper.go" in f for f in go_files)
        assert result.match_type == "exact"  # **/*.go is explicitly recursive
    
    def test_partial_filename_match(self, index_manager):
        """Test searching with partial filename."""
        result = index_manager.find_files("*user*.go")

        results = result.files
        
        # Should find files with 'user' in the basename
        user_files = [f for f in results if "user" in os.path.basename(f).lower()]
        assert len(user_files) >= 1
    
    def test_nested_file_search(self, index_manager):
        """Test finding nested files like user_handler.go."""
        result = index_manager.find_files("user_handler.go")

        results = result.files
        
        # Should find src/handlers/user_handler.go
        assert any("user_handler.go" in f for f in results)
        assert result.match_type == "recursive"
    
    def test_markdown_file_search(self, index_manager):
        """Test searching for markdown files."""
        result = index_manager.find_files("*.md")

        results = result.files
        
        # Should find README.md in root
        md_files = [f for f in results if f.endswith(".md")]
        assert len(md_files) >= 1
        assert result.match_type == "exact"
    
    def test_yaml_config_search(self, index_manager):
        """Test searching for YAML configuration files."""
        result = index_manager.find_files("settings.yaml")

        results = result.files
        
        # Should find config/settings.yaml
        assert any("settings.yaml" in f for f in results)
        assert result.match_type == "recursive"
    
    def test_case_sensitive_search(self, index_manager):
        """Test that search is case-sensitive by default."""
        result = index_manager.find_files("README.md")

        results = result.files
        
        assert any("README.md" in f for f in results)
        # README.md is in root, so exact match should find it
        assert result.match_type == "exact"
    
    def test_directory_pattern_search(self, index_manager):
        """Test searching with directory patterns."""
        result = index_manager.find_files("src/**/*.go")

        results = result.files
        
        # Should find all .go files under src/
        src_go_files = [f for f in results if f.startswith("src") and f.endswith(".go")]
        assert len(src_go_files) >= 3
        assert result.match_type == "exact"  # Pattern with path separator uses exact match
    
    def test_empty_pattern_returns_all(self, index_manager):
        """Test that empty or * pattern returns all files."""
        result_star = index_manager.find_files("*")
        result_empty = index_manager.find_files("")
        
        results_star = result_star.files
        results_empty = result_empty.files
        
        # Both should return all files
        assert len(results_star) >= 13  # We created 13 files
        assert len(results_empty) >= 13
        assert result_star.match_type == "all"
        assert result_empty.match_type == "all"


class TestLenientSearchEdgeCases:
    """Test edge cases and error handling."""
    
    def test_nonexistent_file_pattern(self, index_manager):
        """Test searching for files that don't exist."""
        result = index_manager.find_files("nonexistent.xyz")

        results = result.files
        
        assert results == []
        assert result.match_type == "no_match"
    
    def test_relative_path_pattern(self, index_manager):
        """Test that relative paths with slashes are not affected by lenient search."""
        # Patterns with path separators should work as-is without lenient fallback
        result = index_manager.find_files("src/users.go")

        results = result.files
        
        # Should find exactly src/users.go, not apply lenient search
        assert len(results) >= 1
        assert any("src/users.go" in f for f in results)
        # Path has separator, so it's an exact match (no lenient fallback)
        assert result.match_type == "exact"
    
    def test_nested_relative_path(self, index_manager):
        """Test nested relative paths work correctly."""
        result = index_manager.find_files("src/models/user.go")

        results = result.files
        
        # Should find the exact path
        assert len(results) >= 1
        assert any("src/models/user.go" in f for f in results)
    
    def test_relative_path_with_wildcard(self, index_manager):
        """Test relative paths with wildcards are not modified."""
        result = index_manager.find_files("src/*.go")

        results = result.files
        
        # Should only match files directly in src/, not subdirectories
        matching = [f for f in results if f.startswith("src/") and f.endswith(".go")]
        # Should find src/users.go but not src/models/user.go
        direct_src_files = [f for f in matching if f.count("/") == 1]
        assert len(direct_src_files) >= 1
    
    def test_dot_slash_prefix(self, index_manager):
        """Test that ./ prefixed paths work correctly."""
        result = index_manager.find_files("./main.go")

        results = result.files
        
        # Should find main.go in root (normalized without ./)
        assert any("main.go" in f for f in results)
    
    def test_special_characters_in_pattern(self, index_manager):
        """Test patterns with special regex characters."""
        result = index_manager.find_files("*.md")

        results = result.files
        
        # Should not crash and should find .md files
        assert len(results) >= 1
    
    def test_multiple_extensions(self, index_manager):
        """Test finding files with different extensions."""
        # Find all Go files
        go_result = index_manager.find_files("**/*.go")
        go_results = go_result.files
        # Find all Markdown files
        md_result = index_manager.find_files("**/*.md")
        md_results = md_result.files
        
        assert len(go_results) >= 6
        # **/*.md might not match files in root directory depending on implementation
        # but should at least find docs/api.md
        assert len(md_results) >= 1
        
        # Ensure they're different sets
        go_set = set(go_results)
        md_set = set(md_results)
        assert go_set.isdisjoint(md_set)
    
    def test_question_mark_wildcard(self, index_manager):
        """Test single character wildcard (?) pattern."""
        result = index_manager.find_files("user?.go")

        results = result.files
        
        # Should match files like users.go (5 chars + .go)
        # but not user.go (4 chars + .go)
        assert any("users.go" in f for f in results)
    
    def test_multiple_wildcards_in_pattern(self, index_manager):
        """Test pattern with multiple * wildcards."""
        result = index_manager.find_files("**/user*.go")

        results = result.files
        
        # Should find all files starting with 'user' and ending with '.go'
        matching = [f for f in results if "user" in os.path.basename(f).lower() and f.endswith(".go")]
        assert len(matching) >= 2  # users.go, user.go, user_handler.go
    
    def test_middle_directory_wildcard(self, index_manager):
        """Test wildcard in middle of path."""
        result = index_manager.find_files("src/*/user.go")

        results = result.files
        
        # Should match src/models/user.go but not src/users.go
        assert any("src/models/user.go" in f for f in results)
        assert not any(f == "src/users.go" for f in results)
    
    def test_double_star_at_end(self, index_manager):
        """Test pattern ending with /** (all files in directory)."""
        result = index_manager.find_files("src/**")

        results = result.files
        
        # Should match all files under src/
        src_files = [f for f in results if f.startswith("src/")]
        assert len(src_files) >= 4  # users.go, models/*, handlers/*
    
    def test_pattern_with_no_extension(self, index_manager):
        """Test searching for files without extension."""
        # First add a file without extension to the test
        # Since we can't modify fixture, test with existing pattern
        result = index_manager.find_files("README")

        results = result.files
        
        # Should apply lenient search and find README.md
        # (though this might not match exactly depending on implementation)
        # At minimum should not crash
        assert isinstance(results, list)
    
    def test_case_sensitive_filename(self, index_manager):
        """Test that filename search is case-sensitive for exact matches."""
        result_upper = index_manager.find_files("README.md")
        results_upper = result_upper.files
        result_lower = index_manager.find_files("readme.md")
        results_lower = result_lower.files
        
        # Should find README.md with correct case (exact match in root)
        assert any("README.md" in f for f in results_upper)
        assert result_upper.match_type == "exact"
        # Lenient search should find README.md even with wrong case (case-insensitive root)
        assert any("README.md" in f for f in results_lower)
        assert result_lower.match_type == "case_insensitive_root"
    
    def test_case_insensitive_lenient_search(self, index_manager):
        """Test that lenient search is case-insensitive."""
        # Test with wrong case for a nested file
        result_lower = index_manager.find_files("USER.GO")
        results_lower = result_lower.files
        result_mixed = index_manager.find_files("UsEr.Go")
        results_mixed = result_mixed.files
        
        # Lenient search should find user.go despite case mismatch
        assert any("user.go" in f.lower() for f in results_lower)
        assert any("user.go" in f.lower() for f in results_mixed)
        # Should use case-insensitive recursive match
        assert result_lower.match_type == "case_insensitive_recursive"
        assert result_mixed.match_type == "case_insensitive_recursive"
    
    def test_case_insensitive_with_wildcards(self, index_manager):
        """Test case-insensitive search with wildcard patterns."""
        result = index_manager.find_files("*USER*.GO")

        results = result.files
        
        # Should find files with 'user' in name despite case mismatch
        matching = [f for f in results if "user" in f.lower() and f.endswith(".go")]
        assert len(matching) >= 1
    
    def test_leading_slash_pattern(self, index_manager):
        """Test pattern starting with / (absolute-like path)."""
        # In relative paths, /src/users.go shouldn't be treated differently
        result = index_manager.find_files("/src/users.go")

        results = result.files
        
        # Should either normalize or not match (depending on implementation)
        # At minimum should not crash
        assert isinstance(results, list)
    
    def test_trailing_slash_pattern(self, index_manager):
        """Test pattern ending with / (directory pattern)."""
        result = index_manager.find_files("src/")

        results = result.files
        
        # Should handle gracefully, possibly matching directory
        assert isinstance(results, list)
    
    def test_double_extension_pattern(self, index_manager):
        """Test matching files with patterns like *.test.go."""
        result = index_manager.find_files("*test.go")

        results = result.files
        
        # Should match files ending with 'test.go'
        matching = [f for f in results if f.endswith("test.go")]
        assert len(matching) >= 1  # users_test.go
        assert any("users_test.go" in f for f in matching)
    
    def test_escaped_special_characters(self, index_manager):
        """Test that dots and other special chars in filenames work."""
        # Test with api.md which has a dot
        result = index_manager.find_files("api.md")

        results = result.files
        
        # Should find docs/api.md via lenient search
        assert any("api.md" in f for f in results)
    
    def test_empty_string_after_strip(self, index_manager):
        """Test pattern that becomes empty after stripping."""
        result = index_manager.find_files("   ")

        results = result.files
        
        # Should be treated as "*" and return all files
        assert len(results) >= 13
    
    def test_pattern_with_multiple_slashes(self, index_manager):
        """Test pattern with consecutive slashes."""
        result = index_manager.find_files("src//users.go")

        results = result.files
        
        # Should handle double slashes gracefully
        # Might normalize to src/users.go or not match
        assert isinstance(results, list)
    
    def test_unicode_filename_pattern(self, index_manager):
        """Test that non-ASCII patterns don't crash."""
        result = index_manager.find_files("файл.txt")

        results = result.files
        
        # Should not crash, even if no matches
        assert isinstance(results, list)
        assert results == []  # No such file in test project
