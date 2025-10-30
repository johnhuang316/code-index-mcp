"""
Response formatting utilities for the MCP server.

This module provides consistent response formatting functions used across
services to ensure uniform response structures and formats.
"""

import json
from typing import Any, Dict, List, Optional, Union

from ..indexing.qualified_names import generate_qualified_name


class ResponseFormatter:
    """
    Helper class for formatting responses consistently across services.
    
    This class provides static methods for formatting different types of
    responses in a consistent manner.
    """
    
    @staticmethod
    def _resolve_qualified_names_in_relationships(
        file_path: str,
        relationship_list: List[str],
        duplicate_names: set,
        index_cache: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Convert simple names to qualified names when duplicates exist.
        
        Args:
            file_path: Current file path for context
            relationship_list: List of function/class names that may need qualification
            duplicate_names: Set of names that have duplicates in the project
            index_cache: Optional index cache for duplicate detection
            
        Returns:
            List with qualified names where duplicates exist
        """
        if not relationship_list or not duplicate_names:
            return relationship_list
        
        qualified_list = []
        for name in relationship_list:
            if name in duplicate_names:
                # Convert to qualified name if this name has duplicates
                if index_cache and 'files' in index_cache:
                    # Try to find the actual file where this name is defined
                    # For now, we'll use the current file path as context
                    qualified_name = generate_qualified_name(file_path, name)
                    qualified_list.append(qualified_name)
                else:
                    # Fallback: keep original name if we can't resolve
                    qualified_list.append(name)
            else:
                # No duplicates, keep original name
                qualified_list.append(name)
        
        return qualified_list
    
    @staticmethod
    def _get_duplicate_names_from_index(index_cache: Optional[Dict[str, Any]] = None) -> Dict[str, set]:
        """
        Extract duplicate function and class names from index cache.
        
        Args:
            index_cache: Optional index cache
            
        Returns:
            Dictionary with 'functions' and 'classes' sets of duplicate names
        """
        duplicates = {'functions': set(), 'classes': set()}
        
        if not index_cache:
            return duplicates
        
        # Duplicate detection functionality removed - was legacy code
        # Return empty duplicates as this feature is no longer used
        
        return duplicates
    
    @staticmethod
    def success_response(message: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Format a successful operation response.
        
        Args:
            message: Success message
            data: Optional additional data to include
            
        Returns:
            Formatted success response dictionary
        """
        response = {"status": "success", "message": message}
        if data:
            response.update(data)
        return response
    
    @staticmethod
    def error_response(message: str, error_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Format an error response.
        
        Args:
            message: Error message
            error_code: Optional error code for categorization
            
        Returns:
            Formatted error response dictionary
        """
        response = {"error": message}
        if error_code:
            response["error_code"] = error_code
        return response
    
    @staticmethod
    def file_list_response(files: List[str], status_message: str) -> Dict[str, Any]:
        """
        Format a file list response for find_files operations.
        
        Args:
            files: List of file paths
            status_message: Status message describing the operation result
            
        Returns:
            Formatted file list response
        """
        return {
            "files": files,
            "status": status_message
        }
    
    @staticmethod
    def search_results_response(
        results: List[Dict[str, Any]],
        pagination: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format search results response.
        
        Args:
            results: List of search result dictionaries
            
        Returns:
            Formatted search results response
        """
        response = {
            "results": results
        }

        if pagination is not None:
            response["pagination"] = pagination

        return response
    
    @staticmethod
    def config_response(config_data: Dict[str, Any]) -> str:
        """
        Format configuration data as JSON string.
        
        Args:
            config_data: Configuration data dictionary
            
        Returns:
            JSON formatted configuration string
        """
        return json.dumps(config_data, indent=2)
    
    @staticmethod
    def stats_response(stats_data: Dict[str, Any]) -> str:
        """
        Format statistics data as JSON string.
        
        Args:
            stats_data: Statistics data dictionary
            
        Returns:
            JSON formatted statistics string
        """
        return json.dumps(stats_data, indent=2)
    
    @staticmethod
    def file_summary_response(
        file_path: str,
        line_count: int,
        size_bytes: int,
        extension: str,
        language: str = "unknown",
        functions: Optional[Union[List[str], List[Dict[str, Any]]]] = None,
        classes: Optional[Union[List[str], List[Dict[str, Any]]]] = None,
        imports: Optional[Union[List[str], List[Dict[str, Any]]]] = None,
        language_specific: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        index_cache: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Format file summary response from index data.
        
        Args:
            file_path: Path to the file
            line_count: Number of lines in the file
            size_bytes: File size in bytes
            extension: File extension
            language: Programming language detected
            functions: List of function names (strings) or complete function objects (dicts)
            classes: List of class names (strings) or complete class objects (dicts)
            imports: List of import statements (strings) or complete import objects (dicts)
            language_specific: Language-specific analysis data
            error: Error message if analysis failed
            index_cache: Optional index cache for duplicate name resolution
            
        Returns:
            Formatted file summary response
        """
        # Get duplicate names from index for qualified name resolution
        duplicate_names = ResponseFormatter._get_duplicate_names_from_index(index_cache)
        
        # Handle backward compatibility for functions
        processed_functions = []
        if functions:
            for func in functions:
                if isinstance(func, str):
                    # Legacy format - convert string to basic object
                    processed_functions.append({"name": func})
                elif isinstance(func, dict):
                    # New format - use complete object and resolve qualified names in relationships
                    processed_func = func.copy()
                    
                    # Resolve qualified names in relationship fields
                    if 'calls' in processed_func and isinstance(processed_func['calls'], list):
                        processed_func['calls'] = ResponseFormatter._resolve_qualified_names_in_relationships(
                            file_path, processed_func['calls'], duplicate_names['functions'], index_cache
                        )
                    
                    if 'called_by' in processed_func and isinstance(processed_func['called_by'], list):
                        processed_func['called_by'] = ResponseFormatter._resolve_qualified_names_in_relationships(
                            file_path, processed_func['called_by'], duplicate_names['functions'], index_cache
                        )
                    
                    processed_functions.append(processed_func)
        
        # Handle backward compatibility for classes
        processed_classes = []
        if classes:
            for cls in classes:
                if isinstance(cls, str):
                    # Legacy format - convert string to basic object
                    processed_classes.append({"name": cls})
                elif isinstance(cls, dict):
                    # New format - use complete object and resolve qualified names in relationships
                    processed_cls = cls.copy()
                    
                    # Resolve qualified names in relationship fields
                    if 'instantiated_by' in processed_cls and isinstance(processed_cls['instantiated_by'], list):
                        processed_cls['instantiated_by'] = ResponseFormatter._resolve_qualified_names_in_relationships(
                            file_path, processed_cls['instantiated_by'], duplicate_names['functions'], index_cache
                        )
                    
                    processed_classes.append(processed_cls)
        
        # Handle backward compatibility for imports
        processed_imports = []
        if imports:
            for imp in imports:
                if isinstance(imp, str):
                    # Legacy format - convert string to basic object
                    processed_imports.append({"module": imp, "import_type": "unknown"})
                elif isinstance(imp, dict):
                    # New format - use complete object
                    processed_imports.append(imp)
        
        response = {
            "file_path": file_path,
            "line_count": line_count,
            "size_bytes": size_bytes,
            "extension": extension,
            "language": language,
            "functions": processed_functions,
            "classes": processed_classes,
            "imports": processed_imports,
            "language_specific": language_specific or {}
        }
        
        if error:
            response["error"] = error
        
        return response
    
    @staticmethod
    def directory_info_response(
        temp_directory: str,
        exists: bool,
        is_directory: bool = False,
        contents: Optional[List[str]] = None,
        subdirectories: Optional[List[Dict[str, Any]]] = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format directory information response.
        
        Args:
            temp_directory: Path to the directory
            exists: Whether the directory exists
            is_directory: Whether the path is a directory
            contents: List of directory contents
            subdirectories: List of subdirectory information
            error: Error message if operation failed
            
        Returns:
            Formatted directory info response
        """
        response = {
            "temp_directory": temp_directory,
            "exists": exists,
            "is_directory": is_directory
        }
        
        if contents is not None:
            response["contents"] = contents
        
        if subdirectories is not None:
            response["subdirectories"] = subdirectories
        
        if error:
            response["error"] = error
        
        return response
    
    @staticmethod
    def settings_info_response(
        settings_directory: str,
        temp_directory: str,
        temp_directory_exists: bool,
        config: Dict[str, Any],
        stats: Dict[str, Any],
        exists: bool,
        status: str = "configured",
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format settings information response.
        
        Args:
            settings_directory: Path to settings directory
            temp_directory: Path to temp directory
            temp_directory_exists: Whether temp directory exists
            config: Configuration data
            stats: Statistics data
            exists: Whether settings directory exists
            status: Status of the configuration
            message: Optional status message
            
        Returns:
            Formatted settings info response
        """
        response = {
            "settings_directory": settings_directory,
            "temp_directory": temp_directory,
            "temp_directory_exists": temp_directory_exists,
            "config": config,
            "stats": stats,
            "exists": exists
        }
        
        if status != "configured":
            response["status"] = status
        
        if message:
            response["message"] = message
        
        return response
