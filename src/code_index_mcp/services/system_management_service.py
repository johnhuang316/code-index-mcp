"""
System Management Service - Business logic for system configuration and monitoring.

This service handles the business logic for system management operations including
file watcher status, configuration management, and system health monitoring.
It composes technical tools to achieve business goals.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from .index_management_service import IndexManagementService
from .base_service import BaseService
# FileWatcherTool will be imported locally to avoid circular import
from ..tools.config import ProjectConfigTool, SettingsTool


@dataclass
class FileWatcherStatus:
    """Business result for file watcher status operations."""
    available: bool
    active: bool
    status: str
    message: Optional[str]
    error_info: Optional[Dict[str, Any]]
    configuration: Dict[str, Any]
    rebuild_status: Dict[str, Any]
    recommendations: list[str]


class SystemManagementService(BaseService):
    """
    Business service for system configuration and monitoring.

    This service orchestrates system management workflows by composing
    technical tools to achieve business goals like monitoring file watchers,
    managing configurations, and providing system health insights.
    """

    def __init__(self, ctx):
        super().__init__(ctx)
        # Import FileWatcherTool locally to avoid circular import
        from ..tools.monitoring import FileWatcherTool
        self._watcher_tool = FileWatcherTool(ctx)
        self._config_tool = ProjectConfigTool()
        self._settings_tool = SettingsTool()

    def get_file_watcher_status(self) -> Dict[str, Any]:
        """
        Get comprehensive file watcher status with business intelligence.

        This is the main business method that orchestrates the file watcher
        status workflow, analyzing system state, providing recommendations,
        and formatting comprehensive status information.

        Returns:
            Dictionary with comprehensive file watcher status
        """
        # Business workflow: Analyze system state
        status_result = self._analyze_file_watcher_state()

        # Business result formatting
        return self._format_status_result(status_result)

    def configure_file_watcher(self, enabled: Optional[bool] = None,
                             debounce_seconds: Optional[float] = None,
                             additional_exclude_patterns: Optional[list] = None,
                             observer_type: Optional[str] = None) -> str:
        """
        Configure file watcher settings with business validation.

        Args:
            enabled: Whether to enable file watcher
            debounce_seconds: Debounce time in seconds
            additional_exclude_patterns: Additional patterns to exclude
            observer_type: Observer backend type ("auto", "kqueue", "fsevents", "polling")

        Returns:
            Success message with configuration details

        Raises:
            ValueError: If configuration is invalid
        """
        # Business validation
        self._validate_configuration_request(enabled, debounce_seconds, additional_exclude_patterns, observer_type)

        # Business workflow: Apply configuration
        result = self._apply_file_watcher_configuration(enabled, debounce_seconds, additional_exclude_patterns, observer_type)

        return result

    def _analyze_file_watcher_state(self) -> FileWatcherStatus:
        """
        Business logic to analyze comprehensive file watcher state.

        Returns:
            FileWatcherStatus with complete analysis
        """
        # Business step 1: Check for error conditions
        error_info = self._check_for_watcher_errors()
        if error_info:
            return self._create_error_status(error_info)

        # Business step 2: Check initialization state
        watcher_service = self._watcher_tool.get_from_context()
        if not watcher_service:
            return self._create_not_initialized_status()

        # Business step 3: Get active status
        return self._create_active_status(watcher_service)

    def _check_for_watcher_errors(self) -> Optional[Dict[str, Any]]:
        """
        Business logic to check for file watcher error conditions.

        Returns:
            Error information dictionary or None if no errors
        """
        # Check context for recorded errors
        if hasattr(self.ctx.request_context.lifespan_context, 'file_watcher_error'):
            return self.ctx.request_context.lifespan_context.file_watcher_error

        return None

    def _create_error_status(self, error_info: Dict[str, Any]) -> FileWatcherStatus:
        """
        Business logic to create error status with recommendations.

        Args:
            error_info: Error information from context

        Returns:
            FileWatcherStatus for error condition
        """
        # Get configuration if available
        configuration = self._get_file_watcher_configuration()

        # Get rebuild status
        rebuild_status = self._get_rebuild_status()

        # Business logic: Generate error-specific recommendations
        recommendations = [
            "Use refresh_index tool for manual updates",
            "File watcher auto-refresh is disabled due to errors",
            "Consider restarting the project or checking system permissions"
        ]

        return FileWatcherStatus(
            available=True,
            active=False,
            status="error",
            message=error_info.get('message', 'File watcher error occurred'),
            error_info=error_info,
            configuration=configuration,
            rebuild_status=rebuild_status,
            recommendations=recommendations
        )

    def _create_not_initialized_status(self) -> FileWatcherStatus:
        """
        Business logic to create not-initialized status.

        Returns:
            FileWatcherStatus for not-initialized condition
        """
        # Get basic configuration
        configuration = self._get_file_watcher_configuration()

        # Get rebuild status
        rebuild_status = self._get_rebuild_status()

        # Business logic: Generate initialization recommendations
        recommendations = [
            "Use set_project_path tool to initialize file watcher",
            "File monitoring will be enabled after project initialization"
        ]

        return FileWatcherStatus(
            available=True,
            active=False,
            status="not_initialized",
            message="File watcher service not initialized. Set project path to enable auto-refresh.",
            error_info=None,
            configuration=configuration,
            rebuild_status=rebuild_status,
            recommendations=recommendations
        )

    def _create_active_status(self, watcher_service) -> FileWatcherStatus:
        """
        Business logic to create active status with comprehensive information.

        Args:
            watcher_service: Active file watcher service

        Returns:
            FileWatcherStatus for active condition
        """
        # Get detailed status from watcher service
        watcher_status = watcher_service.get_status()

        # Get configuration
        configuration = self._get_file_watcher_configuration()

        # Get rebuild status
        rebuild_status = self._get_rebuild_status()

        # Business logic: Generate status-specific recommendations
        recommendations = self._generate_active_recommendations(watcher_status)

        return FileWatcherStatus(
            available=watcher_status.get('available', True),
            active=watcher_status.get('active', False),
            status=watcher_status.get('status', 'active'),
            message=watcher_status.get('message'),
            error_info=None,
            configuration=configuration,
            rebuild_status=rebuild_status,
            recommendations=recommendations
        )

    def _get_file_watcher_configuration(self) -> Dict[str, Any]:
        """
        Business logic to get file watcher configuration safely.

        Returns:
            Configuration dictionary
        """
        try:
            # Try to get from project settings
            if (hasattr(self.ctx.request_context.lifespan_context, 'settings') and
                self.ctx.request_context.lifespan_context.settings):
                return self.ctx.request_context.lifespan_context.settings.get_file_watcher_config()

            # Fallback to default configuration
            return {
                'enabled': True,
                'debounce_seconds': 6.0,
                'additional_exclude_patterns': [],
                'note': 'Default configuration - project not fully initialized'
            }

        except Exception as e:
            return {
                'error': f'Could not load configuration: {e}',
                'enabled': True,
                'debounce_seconds': 6.0
            }

    def _get_rebuild_status(self) -> Dict[str, Any]:
        """
        Business logic to get index rebuild status safely.

        Returns:
            Rebuild status dictionary
        """
        try:
            index_service = IndexManagementService(self.ctx)
            return index_service.get_rebuild_status()

        except Exception as e:
            return {
                'status': 'unknown',
                'error': f'Could not get rebuild status: {e}'
            }

    def _generate_active_recommendations(self, watcher_status: Dict[str, Any]) -> list[str]:
        """
        Business logic to generate recommendations for active file watcher.

        Args:
            watcher_status: Current watcher status

        Returns:
            List of recommendations
        """
        recommendations = []

        if watcher_status.get('active', False):
            recommendations.append("File watcher is active - automatic index updates enabled")
            recommendations.append("Files will be re-indexed automatically when changed")
        else:
            recommendations.append("File watcher is available but not active")
            recommendations.append("Use refresh_index for manual updates")

        # Add performance recommendations
        restart_attempts = watcher_status.get('restart_attempts', 0)
        if restart_attempts > 0:
            recommendations.append(f"File watcher has restarted {restart_attempts} times - monitor for stability")

        return recommendations

    def _validate_configuration_request(self, enabled: Optional[bool],
                                      debounce_seconds: Optional[float],
                                      additional_exclude_patterns: Optional[list],
                                      observer_type: Optional[str]) -> None:
        """
        Business validation for file watcher configuration.

        Args:
            enabled: Enable flag
            debounce_seconds: Debounce time
            additional_exclude_patterns: Exclude patterns
            observer_type: Observer backend type

        Raises:
            ValueError: If validation fails
        """
        # Business rule: Enabled flag must be boolean if provided
        if enabled is not None and not isinstance(enabled, bool):
            raise ValueError("Enabled flag must be a boolean value")

        # Business rule: Debounce seconds must be reasonable
        if debounce_seconds is not None:
            if debounce_seconds < 0.1:
                raise ValueError("Debounce seconds must be at least 0.1")
            if debounce_seconds > 300:  # 5 minutes
                raise ValueError("Debounce seconds cannot exceed 300 (5 minutes)")

        # Business rule: Exclude patterns must be valid
        if additional_exclude_patterns is not None:
            if not isinstance(additional_exclude_patterns, list):
                raise ValueError("Additional exclude patterns must be a list")

            for pattern in additional_exclude_patterns:
                if not isinstance(pattern, str):
                    raise ValueError("All exclude patterns must be strings")
                if not pattern.strip():
                    raise ValueError("Exclude patterns cannot be empty")

        # Business rule: Observer type must be valid
        if observer_type is not None:
            valid_types = ('auto', 'kqueue', 'fsevents', 'polling')
            if observer_type not in valid_types:
                raise ValueError(f"observer_type must be one of: {valid_types}")

    def _apply_file_watcher_configuration(self, enabled: Optional[bool],
                                        debounce_seconds: Optional[float],
                                        additional_exclude_patterns: Optional[list],
                                        observer_type: Optional[str]) -> str:
        """
        Business logic to apply file watcher configuration.

        Args:
            enabled: Enable flag
            debounce_seconds: Debounce time
            additional_exclude_patterns: Exclude patterns
            observer_type: Observer backend type

        Returns:
            Success message

        Raises:
            ValueError: If configuration cannot be applied
        """
        # Business rule: Settings must be available
        if (not hasattr(self.ctx.request_context.lifespan_context, 'settings') or
            not self.ctx.request_context.lifespan_context.settings):
            raise ValueError("Settings not available - project path not set")

        settings = self.ctx.request_context.lifespan_context.settings

        # Build updates dictionary
        updates = {}
        if enabled is not None:
            updates["enabled"] = enabled
        if debounce_seconds is not None:
            updates["debounce_seconds"] = debounce_seconds
        if additional_exclude_patterns is not None:
            updates["additional_exclude_patterns"] = additional_exclude_patterns
        if observer_type is not None:
            updates["observer_type"] = observer_type

        if not updates:
            return "No configuration changes specified"

        # Apply configuration
        settings.update_file_watcher_config(updates)

        # Business logic: Generate informative result message
        changes_summary = []
        if 'enabled' in updates:
            changes_summary.append(f"enabled={updates['enabled']}")
        if 'debounce_seconds' in updates:
            changes_summary.append(f"debounce={updates['debounce_seconds']}s")
        if 'additional_exclude_patterns' in updates:
            pattern_count = len(updates['additional_exclude_patterns'])
            changes_summary.append(f"exclude_patterns={pattern_count}")
        if 'observer_type' in updates:
            changes_summary.append(f"observer_type={updates['observer_type']}")

        changes_str = ", ".join(changes_summary)

        return (f"File watcher configuration updated: {changes_str}. "
                f"Restart may be required for changes to take effect.")

    def _format_status_result(self, status_result: FileWatcherStatus) -> Dict[str, Any]:
        """
        Format the status result according to business requirements.

        Args:
            status_result: Status analysis result

        Returns:
            Formatted result dictionary for MCP response
        """
        result = {
            'available': status_result.available,
            'active': status_result.active,
            'status': status_result.status,
            'configuration': status_result.configuration,
            'rebuild_status': status_result.rebuild_status,
            'recommendations': status_result.recommendations
        }

        # Add optional fields
        if status_result.message:
            result['message'] = status_result.message

        if status_result.error_info:
            result['error'] = status_result.error_info
            result['manual_refresh_required'] = True

        return result
