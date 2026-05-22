"""Decorator utilities for rate limiting, retry logic, and caching."""

import time
import functools
import asyncio
from typing import Callable, Any, Optional, TypeVar
from datetime import datetime, timedelta
import hashlib
import json
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type,
    before_sleep_log, after_log
)
import logging
import redis.asyncio as redis

from ..utils.logging import get_logger

T = TypeVar('T')
logger = get_logger(__name__)


def rate_limit(
    key_prefix: str,
    limit: int,
    window_seconds: int = 60,
    identifier_func: Optional[Callable[..., str]] = None
):
    """Rate limiting decorator using Redis"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Get identifier (default to function name)
            identifier = identifier_func(*args, **kwargs) if identifier_func else func.__name__

            # Create Redis key
            key = f"rate_limit:{key_prefix}:{identifier}"

            try:
                # Import here to avoid circular imports
                from app.core.config import get_settings_lazy
                settings = get_settings_lazy()

                redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True
                )

                # Get current count
                count = await redis_client.get(key)
                count = int(count) if count else 0

                # Check limit
                if count >= limit:
                    ttl = await redis_client.ttl(key)
                    raise Exception(f"Rate limit exceeded. Retry after {ttl} seconds")

                # Increment counter
                pipe = redis_client.pipeline()
                pipe.incr(key)
                pipe.expire(key, window_seconds)
                await pipe.execute()

                # Call original function
                return await func(*args, **kwargs)

            except Exception as e:
                logger.warning(f"Rate limiting error: {str(e)}")
                raise

        return wrapper
    return decorator


def cache_result(ttl_seconds: int = 300):
    """Cache function results using Redis"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            key_data = {
                "func": func.__name__,
                "args": [str(arg) for arg in args],
                "kwargs": {k: str(v) for k, v in kwargs.items()}
            }
            cache_key = f"cache:{hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()}"

            try:
                # Import here to avoid circular imports
                from app.core.config import get_settings_lazy
                settings = get_settings_lazy()

                redis_client = redis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True
                )

                # Try to get from cache
                cached_result = await redis_client.get(cache_key)
                if cached_result:
                    logger.debug(f"Cache hit: {cache_key}")
                    return json.loads(cached_result)

                # Call function and cache result
                result = await func(*args, **kwargs)
                if result:
                    await redis_client.setex(
                        cache_key,
                        ttl_seconds,
                        json.dumps(result, default=str)
                    )
                    logger.debug(f"Cache set: {cache_key}")

                return result

            except Exception as e:
                logger.warning(f"Cache error: {str(e)}")
                # Fallback to calling function directly
                return await func(*args, **kwargs)

        return wrapper
    return decorator


def persistent_cache(ttl_seconds: int = 3600):
    """Persistent cache for important data"""
    return cache_result(ttl_seconds=ttl_seconds)


def retry_on_failure(
    max_attempts: int = 3,
    wait_seconds: int = 1,
    exponential: bool = True
):
    """Retry decorator with exponential backoff"""
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @retry(
                wait=wait_exponential(multiplier=wait_seconds, min=1, max=60) if exponential
                else wait_fixed(wait_seconds),
                stop=stop_after_attempt(max_attempts),
                retry=retry_if_exception_type(Exception),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                after=after_log(logger, logging.INFO),
                reraise=True
            )
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await func(*args, **kwargs)

            return async_wrapper
        else:
            @retry(
                wait=wait_exponential(multiplier=wait_seconds, min=1, max=60) if exponential
                else wait_fixed(wait_seconds),
                stop=stop_after_attempt(max_attempts),
                retry=retry_if_exception_type(Exception),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                after=after_log(logger, logging.INFO),
                reraise=True
            )
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return sync_wrapper
    return decorator