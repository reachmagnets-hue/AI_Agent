"""Custom exception classes for better error handling."""

from typing import Optional, Dict, Any


class APIError(Exception):
    """Base API error exception"""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or f"ERR_{status_code}"
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(APIError):
    """Validation error for invalid input data"""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=400,
            error_code="VALIDATION_ERROR",
            details={"field": field, **(details or {})}
        )


class AuthenticationError(APIError):
    """Authentication error for invalid credentials or tokens"""

    def __init__(self, message: str = "Invalid authentication credentials"):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTH_ERROR"
        )


class AuthorizationError(APIError):
    """Authorization error for insufficient permissions"""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            status_code=403,
            error_code="FORBIDDEN"
        )


class NotFoundError(APIError):
    """Resource not found error"""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(
            message=message,
            status_code=404,
            error_code="NOT_FOUND"
        )


class ConflictError(APIError):
    """Conflict error for duplicate resources"""

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT"
        )


class RateLimitError(APIError):
    """Rate limit exceeded error"""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": 60}
        )


class ExternalServiceError(APIError):
    """External service (Vapi, Supabase) error"""

    def __init__(
        self,
        service: str,
        message: str = "External service error",
        status_code: int = 502
    ):
        super().__init__(
            message=f"{service}: {message}",
            status_code=status_code,
            error_code=f"{service.upper()}_ERROR",
            details={"service": service}
        )


def error_response(error: Exception) -> Dict[str, Any]:
    """Convert exception to standardized error response"""
    if isinstance(error, APIError):
        return {
            "error": {
                "message": error.message,
                "status_code": error.status_code,
                "error_code": error.error_code,
                "details": error.details
            }
        }
    else:
        # Convert generic exceptions to API errors
        return {
            "error": {
                "message": str(error),
                "status_code": 500,
                "error_code": "INTERNAL_ERROR",
                "details": {"type": type(error).__name__}
            }
        }