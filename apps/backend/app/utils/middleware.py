"""Custom middleware for security, logging, and monitoring."""

import time
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, Response
from starlette.types import ASGIApp

from .logging import get_logger
from .exceptions import APIError

logger = get_logger(__name__)


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware to track request timing and metrics"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log request details
        logger.info(
            f"{request.method} {request.url.path}",
            status_code=response.status_code,
            duration=f"{duration_ms:.2f}ms",
            client_ip=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("user-agent", "unknown")
        )

        # Add timing header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}"

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses"""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )

        # Remove server identification headers
        response.headers.pop("server", None)
        response.headers.pop("x-powered-by", None)

        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for global error handling"""

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except APIError as api_error:
            # Handle custom API errors
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=api_error.status_code,
                content={"error": api_error.message, "error_code": api_error.error_code}
            )
        except Exception as exc:
            # Log the error
            logger.exception(f"Unhandled error: {str(exc)}")

            # Return generic error response
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal server error",
                    "error_code": "INTERNAL_ERROR"
                }
            )


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging"""

    async def dispatch(self, request: Request, call_next):
        # Log request
        logger.info(
            f"Request: {request.method} {request.url.path}",
            client_ip=request.client.host if request.client else "unknown",
            content_length=request.headers.get("content-length"),
            user_agent=request.headers.get("user-agent")
        )

        response = await call_next(request)

        # Log response
        logger.info(
            f"Response: {request.method} {request.url.path}",
            status_code=response.status_code,
            content_length=response.headers.get("content-length")
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware"""

    def __init__(self, app: ASGIApp, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"

        # Clean old entries
        current_time = time.time()
        if client_ip in self.requests:
            self.requests[client_ip] = [
                req_time for req_time in self.requests[client_ip]
                if current_time - req_time < self.window_seconds
            ]

        # Check rate limit
        request_times = self.requests.get(client_ip, [])
        if len(request_times) >= self.max_requests:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests"}
            )

        # Add current request
        request_times.append(current_time)
        self.requests[client_ip] = request_times

        return await call_next(request)