"""
Main index builder that coordinates all indexing components.

This module provides the main IndexBuilder class that orchestrates the entire
indexing process, from file scanning to relationship analysis to final index assembly.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from .models import CodeIndex, FileInfo, FileAnalysisResult, ValidationResult
from .scanner import ProjectScanner
from .analyzers import LanguageAnalyzerManager
from .relationships import RelationshipTracker


class IndexBuilder:
    """Main builder class that coordinates all indexing components."""

    def __init__(self, max_workers: Optional[int] = None):
        """
        Initialize the index builder.

        Args:
            max_workers: Maximum number of worker threads for parallel processing.
        """
        self.max_workers = max_workers
        self.analyzer_manager = LanguageAnalyzerManager(max_workers)
        self.relationship_tracker = RelationshipTracker()
        self.project_path = ""  # Initialize project_path

    def build_index(self, project_path: str, generate_log_file: bool = False) -> CodeIndex:
        """
        Build complete code index for a project.

        Args:
            project_path: Path to the project root directory

        Returns:
            Complete CodeIndex structure
        """
        start_time = datetime.now()
        self.project_path = project_path  # Store for file path resolution

        try:
            # Step 1: Scan project directory
            scanner = ProjectScanner(project_path, generate_log_file)
            scan_result = scanner.scan_project()

            # Step 2: Read file contents and analyze in parallel
            analysis_results = self._analyze_files(scan_result.file_list)

            # Step 3: Build relationships between code elements
            relationships = self.relationship_tracker.build_relationships(analysis_results)

            # Step 4: Assemble final index structure
            index = self._assemble_index(scan_result, analysis_results, relationships)

            # Step 5: Add timing and metadata
            end_time = datetime.now()
            analysis_time_ms = int((end_time - start_time).total_seconds() * 1000)

            index.index_metadata.update({
                'analysis_time_ms': analysis_time_ms,
                'files_with_errors': self._collect_files_with_errors(analysis_results),
                'languages_analyzed': self._collect_analyzed_languages(analysis_results)
            })

            # Step 6: Validate the index
            validation_result = self._validate_index(index)
            if not validation_result.is_valid:
                # Log warnings but don't fail the build
                print(f"Index validation warnings: {validation_result.warnings}")
                if validation_result.errors:
                    print(f"Index validation errors: {validation_result.errors}")

            return index

        except (OSError, IOError, ValueError, RuntimeError) as e:
            # Create a minimal index on failure
            return self._create_fallback_index(project_path, str(e))

    def _analyze_files(self, file_list: List[FileInfo]) -> List[FileAnalysisResult]:
        """
        Analyze all files in parallel.

        Args:
            file_list: List of FileInfo objects to analyze

        Returns:
            List of FileAnalysisResult objects
        """
        # Read file contents
        files_with_content = []

        for file_info in file_list:
            try:
                content = self._read_file_content(file_info.path)
                if content is not None:
                    files_with_content.append((file_info, content))
            except (OSError, IOError, UnicodeDecodeError, PermissionError) as e:
                # Log error and add empty content for unreadable files
                print(f"Failed to read file {file_info.path}: {str(e)}")
                files_with_content.append((file_info, ""))  # Empty content for error case

        # Analyze files using the analyzer manager
        return self.analyzer_manager.analyze_files(files_with_content)

    def _read_file_content(self, file_path: str) -> Optional[str]:
        """
        Read content from a file.

        Args:
            file_path: Path to the file (relative to project root)

        Returns:
            File content as string, or None if unreadable
        """
        try:
            # Convert relative path to absolute based on project path
            if not os.path.isabs(file_path):
                full_path = os.path.join(self.project_path, file_path)
            else:
                full_path = file_path

            # Try different encodings
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']

            for encoding in encodings:
                try:
                    with open(full_path, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue

            # If all encodings fail, return None
            return None

        except (OSError, PermissionError, FileNotFoundError):
            return None

    def _assemble_index(
        self,
        scan_result,
        analysis_results: List[FileAnalysisResult],
        relationships
    ) -> CodeIndex:
        """
        Assemble the final index structure.

        Args:
            scan_result: Project scanning results
            analysis_results: File analysis results
            relationships: Relationship graph

        Returns:
            Complete CodeIndex structure
        """
        # Build file entries
        files = []
        for result in analysis_results:
            file_entry = {
                'id': result.file_info.id,
                'path': result.file_info.path,
                'size': result.file_info.size,
                'line_count': self._estimate_line_count(result),
                'language': result.file_info.language,
                'functions': [self._serialize_function(func) for func in result.functions],
                'classes': [self._serialize_class(cls) for cls in result.classes],
                'imports': [self._serialize_import(imp) for imp in result.imports],
                'language_specific': result.language_specific,
                'imported_by': []  # Will be populated by relationship analysis
            }
            files.append(file_entry)

        # Build lookup tables
        lookups = self._build_lookup_tables(analysis_results)

        # Build reverse lookups from relationships
        reverse_lookups = relationships.reverse_lookups

        # Create index metadata
        index_metadata = {
            'version': '4.0',  # Updated for duplicate names support
            'duplicate_names_support': True,
            'qualified_names_support': True
        }

        return CodeIndex(
            project_metadata=scan_result.project_metadata,
            directory_tree=scan_result.directory_tree,
            files=files,
            lookups=lookups,
            reverse_lookups=reverse_lookups,
            special_files=scan_result.special_files,
            index_metadata=index_metadata
        )

    def _serialize_function(self, func) -> Dict[str, Any]:
        """Serialize a FunctionInfo object to dictionary."""
        return {
            'name': func.name,
            'parameters': func.parameters,
            'line_start': func.line_start,
            'line_end': func.line_end,
            'line_count': func.line_count,
            'calls': func.calls,
            'called_by': func.called_by,
            'is_async': func.is_async,
            'decorators': func.decorators
        }

    def _serialize_class(self, cls) -> Dict[str, Any]:
        """Serialize a ClassInfo object to dictionary."""
        return {
            'name': cls.name,
            'line_start': cls.line_start,
            'line_end': cls.line_end,
            'line_count': cls.line_count,
            'methods': cls.methods,
            'inherits_from': cls.inherits_from,
            'instantiated_by': cls.instantiated_by
        }

    def _serialize_import(self, imp) -> Dict[str, Any]:
        """Serialize an ImportInfo object to dictionary."""
        return {
            'module': imp.module,
            'imported_names': imp.imported_names,
            'import_type': imp.import_type,
            'line_number': imp.line_number
        }

    def _build_lookup_tables(self, analysis_results: List[FileAnalysisResult]) -> Dict[str, Any]:
        """Build forward lookup tables with support for duplicate names."""
        lookups = {
            'path_to_id': {},
            'function_to_file_id': {},
            'class_to_file_id': {}
        }

        duplicate_functions = set()
        duplicate_classes = set()

        for result in analysis_results:
            file_id = result.file_info.id
            file_path = result.file_info.path

            # Path to ID lookup (unchanged)
            lookups['path_to_id'][file_path] = file_id

            # Function to file ID lookup - support multiple files per function name
            for func in result.functions:
                if func.name not in lookups['function_to_file_id']:
                    lookups['function_to_file_id'][func.name] = []
                else:
                    duplicate_functions.add(func.name)
                
                # Avoid duplicate file IDs for the same function name
                if file_id not in lookups['function_to_file_id'][func.name]:
                    lookups['function_to_file_id'][func.name].append(file_id)

            # Class to file ID lookup - support multiple files per class name
            for cls in result.classes:
                if cls.name not in lookups['class_to_file_id']:
                    lookups['class_to_file_id'][cls.name] = []
                else:
                    duplicate_classes.add(cls.name)
                
                # Avoid duplicate file IDs for the same class name
                if file_id not in lookups['class_to_file_id'][cls.name]:
                    lookups['class_to_file_id'][cls.name].append(file_id)

        # Log duplicate detection statistics
        if duplicate_functions:
            print(f"Detected {len(duplicate_functions)} duplicate function names: {sorted(list(duplicate_functions))[:5]}{'...' if len(duplicate_functions) > 5 else ''}")
        
        if duplicate_classes:
            print(f"Detected {len(duplicate_classes)} duplicate class names: {sorted(list(duplicate_classes))[:5]}{'...' if len(duplicate_classes) > 5 else ''}")

        return lookups

    def _estimate_line_count(self, result: FileAnalysisResult) -> int:
        """Estimate line count from analysis result."""
        # If we have functions or classes, use their line ranges
        max_line = 0

        for func in result.functions:
            max_line = max(max_line, func.line_end)

        for cls in result.classes:
            max_line = max(max_line, cls.line_end)

        # If no functions/classes, try to get from language-specific data
        if max_line == 0:
            for lang_data in result.language_specific.values():
                if isinstance(lang_data, dict) and 'line_count' in lang_data:
                    max_line = max(max_line, lang_data['line_count'])

        return max_line if max_line > 0 else 1

    def _collect_files_with_errors(self, analysis_results: List[FileAnalysisResult]) -> List[str]:
        """Collect files that had analysis errors."""
        files_with_errors = []

        for result in analysis_results:
            if result.analysis_errors:
                files_with_errors.append(result.file_info.path)

        return files_with_errors

    def _collect_analyzed_languages(self, analysis_results: List[FileAnalysisResult]) -> List[str]:
        """Collect unique languages that were analyzed."""
        languages = set()

        for result in analysis_results:
            languages.add(result.file_info.language)

        return sorted(list(languages))

    def _validate_index(self, index: CodeIndex) -> ValidationResult:
        """Validate the completed index for consistency."""
        errors = []
        warnings = []

        # Check required fields
        if not index.project_metadata:
            errors.append("Missing project_metadata")

        if not index.files:
            warnings.append("No files in index")

        # Check file ID consistency
        file_ids = set()
        for file_entry in index.files:
            file_id = file_entry.get('id')
            if file_id is None:
                errors.append(f"File missing ID: {file_entry.get('path', 'unknown')}")
            elif file_id in file_ids:
                errors.append(f"Duplicate file ID: {file_id}")
            else:
                file_ids.add(file_id)

        # Check lookup table consistency
        if 'path_to_id' in index.lookups:
            for path, file_id in index.lookups['path_to_id'].items():
                if file_id not in file_ids:
                    errors.append(
                        f"Lookup references non-existent file ID: {file_id} for path {path}"
                    )

        # Check version
        version = index.index_metadata.get('version')
        if not version or version < '4.0':
            warnings.append(f"Index version {version} may be outdated")
        
        # Validate duplicate names support in lookup tables
        if 'function_to_file_id' in index.lookups:
            for func_name, file_ids in index.lookups['function_to_file_id'].items():
                if not isinstance(file_ids, list):
                    errors.append(f"Function lookup for '{func_name}' should be a list, got {type(file_ids)}")
                elif not all(isinstance(fid, int) for fid in file_ids):
                    errors.append(f"All file IDs in function lookup for '{func_name}' should be integers")
        
        if 'class_to_file_id' in index.lookups:
            for class_name, file_ids in index.lookups['class_to_file_id'].items():
                if not isinstance(file_ids, list):
                    errors.append(f"Class lookup for '{class_name}' should be a list, got {type(file_ids)}")
                elif not all(isinstance(fid, int) for fid in file_ids):
                    errors.append(f"All file IDs in class lookup for '{class_name}' should be integers")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _create_fallback_index(self, project_path: str, error_message: str) -> CodeIndex:
        """Create a minimal fallback index when building fails."""
        project_name = Path(project_path).name

        return CodeIndex(
            project_metadata={
                'name': project_name,
                'root_path': project_path,
                'indexed_at': datetime.now(),
                'total_files': 0,
                'total_lines': 0
            },
            directory_tree={},
            files=[],
            lookups={
                'path_to_id': {},
                'function_to_file_id': {},
                'class_to_file_id': {}
            },
            reverse_lookups={
                'function_callers': {},
                'class_instantiators': {},
                'imports_module': {},
                'has_decorator': {}
            },
            special_files={
                'entry_points': [],
                'config_files': [],
                'documentation': [],
                'build_files': []
            },
            index_metadata={
                'version': '4.0',
                'duplicate_names_support': True,
                'qualified_names_support': True,
                'build_error': error_message,
                'analysis_time_ms': 0,
                'files_with_errors': [],
                'languages_analyzed': []
            }
        )
