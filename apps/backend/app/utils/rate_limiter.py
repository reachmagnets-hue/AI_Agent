"""
Rate limiter using SlowAPI for FastAPI integration.
Provides global rate limiting configuration.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import get_settings_lazy

settings = get_settings_lazy()

# Global limiter instance
limiter = Limiter(key_func=get_remote_address)


def get_limiter():
    """Get the global limiter instance"""
    return limiter


def configure_rate_limiting():
    """Configure rate limiting settings"""
    return {
        "default_limits": [f"{settings.RATE_LIMIT_PER_MINUTE} per minute"],
        "webhook_limits": [f"{settings.WEBHOOK_RATE_LIMIT_PER_MINUTE} per minute"]
    }