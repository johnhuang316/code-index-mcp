"""
Centralized file filtering logic for the Code Index MCP server.

This module provides unified filtering capabilities used across all components
that need to determine which files and directories should be processed or excluded.
"""

import fnmatch
from pathlib import Path
from typing import List, Optional, Set

from ..constants import FILTER_CONFIG


class FileFilter:
    """Centralized file filtering logic."""
    
    def __init__(self, additional_excludes: Optional[List[str]] = None, extra_extensions: Optional[List[str]] = None):
        """
        Initialize the file filter.

        Args:
            additional_excludes: Additional directory patterns to exclude
            extra_extensions: Additional file extensions to include (e.g., ['.rsc', '.conf'])
        """
        self.exclude_dirs = set(FILTER_CONFIG["exclude_directories"])
        self.exclude_files = set(FILTER_CONFIG["exclude_files"])
        self.supported_extensions = set(FILTER_CONFIG["supported_extensions"])

        # Add user-defined exclusions
        if additional_excludes:
            self.exclude_dirs.update(additional_excludes)

        # Add user-defined extra extensions
        if extra_extensions:
            for ext in extra_extensions:
                ext = ext.strip().lower()
                if ext and not ext.startswith('.'):
                    ext = '.' + ext
                if ext:
                    self.supported_extensions.add(ext)
    
    def should_exclude_directory(self, dir_name: str) -> bool:
        """
        Check if directory should be excluded from processing.
        
        Args:
            dir_name: Directory name to check
            
        Returns:
            True if directory should be excluded, False otherwise
        """
        # Skip hidden directories except for specific allowed ones
        if dir_name.startswith('.') and dir_name not in {'.env', '.gitignore'}:
            return True
            
        # Check against exclude patterns
        return dir_name in self.exclude_dirs
    
    def should_exclude_file(self, file_path: Path) -> bool:
        """
        Check if file should be excluded from processing.
        
        Args:
            file_path: Path object for the file to check
            
        Returns:
            True if file should be excluded, False otherwise
        """
        # Extension check - only process supported file types
        if file_path.suffix.lower() not in self.supported_extensions:
            return True
            
        # Hidden files (except specific allowed ones)
        if file_path.name.startswith('.') and file_path.name not in {'.gitignore', '.env'}:
            return True
        
        # Filename pattern check using glob patterns
        for pattern in self.exclude_files:
            if fnmatch.fnmatch(file_path.name, pattern):
                return True
                
        return False
    
    def should_process_path(self, path: Path, base_path: Path) -> bool:
        """
        Unified path processing logic to determine if a file should be processed.
        
        Args:
            path: File path to check
            base_path: Project base path for relative path calculation
            
        Returns:
            True if file should be processed, False otherwise
        """
        try:
            # Ensure we're working with absolute paths
            if not path.is_absolute():
                path = base_path / path
                
            # Get relative path from base
            relative_path = path.relative_to(base_path)
            
            # Check each path component for excluded directories
            for part in relative_path.parts[:-1]:  # Exclude filename
                if self.should_exclude_directory(part):
                    return False
                    
            # Check file itself
            return not self.should_exclude_file(path)
            
        except (ValueError, OSError):
            # Path not relative to base_path or other path errors
            return False
    
    def is_supported_file_type(self, file_path: Path) -> bool:
        """
        Check if file type is supported for indexing.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file type is supported, False otherwise
        """
        return file_path.suffix.lower() in self.supported_extensions
    
    def is_temporary_file(self, file_path: Path) -> bool:
        """
        Check if file appears to be a temporary file.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file appears temporary, False otherwise
        """
        name = file_path.name
        
        # Common temporary file patterns
        temp_patterns = ['*.tmp', '*.temp', '*.swp', '*.swo', '*~']
        
        for pattern in temp_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        
        # Files ending in .bak or .orig
        if name.endswith(('.bak', '.orig')):
            return True
            
        return False
    
    def filter_file_list(self, files: List[str], base_path: str) -> List[str]:
        """
        Filter a list of file paths, keeping only those that should be processed.
        
        Args:
            files: List of file paths (absolute or relative)
            base_path: Project base path
            
        Returns:
            Filtered list of file paths that should be processed
        """
        base = Path(base_path)
        filtered = []
        
        for file_path_str in files:
            file_path = Path(file_path_str)
            if self.should_process_path(file_path, base):
                filtered.append(file_path_str)
                
        return filtered
    
    def get_exclude_summary(self) -> dict:
        """
        Get summary of current exclusion configuration.
        
        Returns:
            Dictionary with exclusion configuration details
        """
        return {
            "exclude_directories_count": len(self.exclude_dirs),
            "exclude_files_count": len(self.exclude_files),
            "supported_extensions_count": len(self.supported_extensions),
            "exclude_directories": sorted(self.exclude_dirs),
            "exclude_files": sorted(self.exclude_files)
        }