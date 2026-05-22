"""Logging utilities with structured logging support."""

import logging
import sys
from typing import Optional


class SensitiveDataFilter(logging.Filter):
    """Filter out sensitive data from logs"""

    sensitive_patterns = [
        "password",
        "token",
        "secret",
        "key",
        "api_key",
        "authorization",
        "auth",
        "jwt",
        "bearer"
    ]

    def filter(self, record):
        """Remove sensitive data from log records"""
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            for pattern in self.sensitive_patterns:
                # Simple pattern matching for sensitive data
                record.msg = self._redact_pattern(record.msg, pattern)
        return True

    def _redact_pattern(self, message: str, pattern: str) -> str:
        """Redact sensitive patterns from message"""
        import re
        # Match pattern followed by : or = and then alphanumeric characters
        regex = rf"({pattern})[^\w]*([\w-]+)"
        return re.sub(regex, r"\1=***REDACTED***", message, flags=re.IGNORECASE)


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance"""
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        # Import here to avoid circular imports
        from app.core.config import get_settings_lazy
        settings = get_settings_lazy()

        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

        # Create handlers
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setLevel(logging.DEBUG)

        # Create formatter
        formatter = logging.Formatter(
            settings.LOG_FORMAT,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        stream_handler.setFormatter(formatter)

        # Add sensitive data filter
        stream_handler.addFilter(SensitiveDataFilter())

        # Add handler to logger
        logger.addHandler(stream_handler)

        # Prevent propagation to avoid duplicate logs
        logger.propagate = False

    return logger


def log_error(logger: logging.Logger, error: Exception, context: Optional[dict] = None):
    """Log error with context"""
    error_data = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context or {}
    }
    logger.error(f"Error occurred: {error_data}", exc_info=True)


def log_api_call(logger: logging.Logger, method: str, path: str, status_code: int, duration: float):
    """Log API call details"""
    logger.info(
        f"API Call: {method} {path} - Status: {status_code} - Duration: {duration:.2f}ms"
    )