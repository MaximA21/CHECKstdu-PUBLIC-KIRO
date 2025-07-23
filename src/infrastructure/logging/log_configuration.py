"""Log configuration implementation wrapping existing logging_config functionality."""

import os
from typing import Dict, Any
from ...application.interfaces.logging import ILogConfiguration, LogLevel, LogFormat


class LogConfiguration(ILogConfiguration):
    """Log configuration implementation using environment variables."""

    def __init__(self):
        """Initialize log configuration."""
        self._current_level = self._parse_log_level(os.environ.get("LOG_LEVEL", "INFO"))
        structured_enabled = os.environ.get("STRUCTURED_LOGS", "false").lower() == "true"
        self._current_format = LogFormat.STRUCTURED if structured_enabled else LogFormat.PLAIN
        self._structured_enabled = structured_enabled

    def get_log_level(self) -> LogLevel:
        """Get the current log level."""
        return self._current_level

    def set_log_level(self, level: LogLevel) -> None:
        """Set the log level."""
        self._current_level = level
        # Update environment variable to affect new logger instances
        os.environ["LOG_LEVEL"] = level.value

    def get_log_format(self) -> LogFormat:
        """Get the current log format."""
        return self._current_format

    def set_log_format(self, format_type: LogFormat) -> None:
        """Set the log format."""
        self._current_format = format_type

        # Update structured logging setting
        if format_type == LogFormat.STRUCTURED or format_type == LogFormat.JSON:
            self._structured_enabled = True
            os.environ["STRUCTURED_LOGS"] = "true"
        else:
            self._structured_enabled = False
            os.environ["STRUCTURED_LOGS"] = "false"

    def is_structured_logging_enabled(self) -> bool:
        """Check if structured logging is enabled."""
        return self._structured_enabled

    def enable_structured_logging(self, enabled: bool = True) -> None:
        """Enable or disable structured logging."""
        self._structured_enabled = enabled
        os.environ["STRUCTURED_LOGS"] = "true" if enabled else "false"

        # Update format accordingly
        if enabled:
            self._current_format = LogFormat.STRUCTURED
        else:
            self._current_format = LogFormat.PLAIN

    def get_configuration(self) -> Dict[str, Any]:
        """Get the current logging configuration."""
        return {
            "level": self._current_level.value,
            "format": self._current_format.value,
            "structured_enabled": self._structured_enabled,
            "environment_variables": {
                "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
                "STRUCTURED_LOGS": os.environ.get("STRUCTURED_LOGS", "false"),
            },
        }

    def update_configuration(self, config: Dict[str, Any]) -> None:
        """Update the logging configuration."""
        if "level" in config:
            level_str = config["level"]
            if isinstance(level_str, str):
                try:
                    level = LogLevel(level_str.upper())
                    self.set_log_level(level)
                except ValueError:
                    pass  # Invalid level, ignore

        if "format" in config:
            format_str = config["format"]
            if isinstance(format_str, str):
                try:
                    format_type = LogFormat(format_str.lower())
                    self.set_log_format(format_type)
                except ValueError:
                    pass  # Invalid format, ignore

        if "structured_enabled" in config:
            enabled = bool(config["structured_enabled"])
            self.enable_structured_logging(enabled)

        # log_format_string is no longer used in this implementation

    def reset_to_environment(self) -> None:
        """Reset configuration to environment variable values."""
        self._current_level = self._parse_log_level(os.environ.get("LOG_LEVEL", "INFO"))
        structured_enabled = os.environ.get("STRUCTURED_LOGS", "false").lower() == "true"
        self._structured_enabled = structured_enabled
        self._current_format = LogFormat.STRUCTURED if structured_enabled else LogFormat.PLAIN

    def get_effective_log_level_for_logger(self, logger_name: str) -> LogLevel:
        """
        Get the effective log level for a specific logger.

        Args:
            logger_name: Name of the logger

        Returns:
            LogLevel: Effective log level
        """
        # Check for logger-specific environment variable
        env_var = f'LOG_LEVEL_{logger_name.upper().replace(".", "_")}'
        logger_level = os.environ.get(env_var)

        if logger_level:
            try:
                return LogLevel(logger_level.upper())
            except ValueError:
                pass

        return self._current_level

    def set_logger_level(self, logger_name: str, level: LogLevel) -> None:
        """
        Set log level for a specific logger.

        Args:
            logger_name: Name of the logger
            level: Log level to set
        """
        env_var = f'LOG_LEVEL_{logger_name.upper().replace(".", "_")}'
        os.environ[env_var] = level.value

    @staticmethod
    def _parse_log_level(level_str: str) -> LogLevel:
        """Parse log level string to LogLevel enum."""
        try:
            return LogLevel(level_str.upper())
        except ValueError:
            return LogLevel.INFO  # Default fallback

    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate the current configuration.

        Returns:
            Dict[str, Any]: Validation results with any issues found
        """
        issues = []
        warnings = []

        # Check if log level is valid
        try:
            LogLevel(self._current_level.value.upper())
        except ValueError:
            issues.append(f"Invalid log level: {self._current_level.value}")

        # Check environment consistency
        env_level = os.environ.get("LOG_LEVEL", "INFO")
        if env_level.upper() != self._current_level.value:
            warnings.append(f"Environment LOG_LEVEL ({env_level}) differs from current level ({self._current_level.value})")

        env_structured = os.environ.get("STRUCTURED_LOGS", "false").lower() == "true"
        if env_structured != self._structured_enabled:
            warnings.append(f"Environment STRUCTURED_LOGS differs from current setting")

        return {"valid": len(issues) == 0, "issues": issues, "warnings": warnings, "configuration": self.get_configuration()}
