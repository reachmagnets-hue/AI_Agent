"""Redis caching utilities."""

import json
import hashlib
from typing import Any, Optional, Dict
import asyncio
import redis.asyncio as redis

from ..utils.logging import get_logger

logger = get_logger(__name__)


async def cache_get(key: str, default: Any = None) -> Any:
    """Get value from Redis cache"""
    try:
        # Import here to avoid circular imports
        from app.core.config import get_settings_lazy
        settings = get_settings_lazy()

        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        value = await redis_client.get(key)

        if value is None:
            return default

        # Try to parse as JSON
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    except Exception as e:
        logger.warning(f"Cache get error: {str(e)}")
        return default


async def cache_set(
    key: str,
    value: Any,
    ttl: int = 3600,
    nx: bool = False  # Only set if not exists
) -> bool:
    """Set value in Redis cache"""
    try:
        # Import here to avoid circular imports
        from app.core.config import get_settings_lazy
        settings = get_settings_lazy()

        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

        # Serialize value
        if isinstance(value, (dict, list)):
            serialized = json.dumps(value, default=str)
        else:
            serialized = str(value)

        if nx:
            result = await redis_client.setnx(key, serialized)
            if result:
                await redis_client.expire(key, ttl)
        else:
            result = await redis_client.setex(key, ttl, serialized)

        return bool(result)

    except Exception as e:
        logger.warning(f"Cache set error: {str(e)}")
        return False


async def cache_delete(key: str) -> bool:
    """Delete key from Redis cache"""
    try:
        # Import here to avoid circular imports
        from app.core.config import get_settings_lazy
        settings = get_settings_lazy()

        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        result = await redis_client.delete(key)
        return result > 0

    except Exception as e:
        logger.warning(f"Cache delete error: {str(e)}")
        return False


async def cache_exists(key: str) -> bool:
    """Check if key exists in cache"""
    try:
        # Import here to avoid circular imports
        from app.core.config import get_settings_lazy
        settings = get_settings_lazy()

        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return bool(await redis_client.exists(key))

    except Exception as e:
        logger.warning(f"Cache exists error: {str(e)}")
        return False


async def cache_increment(key: str, amount: int = 1) -> int:
    """Increment counter in cache"""
    try:
        # Import here to avoid circular imports
        from app.core.config import get_settings_lazy
        settings = get_settings_lazy()

        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return await redis_client.incrby(key, amount)

    except Exception as e:
        logger.warning(f"Cache increment error: {str(e)}")
        return 0


async def cache_decrement(key: str, amount: int = 1) -> int:
    """Decrement counter in cache"""
    try:
        # Import here to avoid circular imports
        from app.core.config import get_settings_lazy
        settings = get_settings_lazy()

        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return await redis_client.decrby(key, amount)

    except Exception as e:
        logger.warning(f"Cache decrement error: {str(e)}")
        return 0


def generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """Generate cache key from arguments"""
    data = {
        "args": [str(arg) for arg in args],
        "kwargs": {k: str(v) for k, v in kwargs.items()}
    }
    key_str = json.dumps(data, sort_keys=True)
    hash_str = hashlib.md5(key_str.encode()).hexdigest()
    return f"{prefix}:{hash_str}"


class CacheManager:
    """Cache manager for complex operations"""

    def __init__(self, prefix: str = "app"):
        self.prefix = prefix

    def key(self, suffix: str) -> str:
        """Generate namespaced key"""
        return f"{self.prefix}:{suffix}"

    async def get(self, suffix: str, default: Any = None) -> Any:
        """Get cached value"""
        return await cache_get(self.key(suffix), default)

    async def set(self, suffix: str, value: Any, ttl: int = 3600) -> bool:
        """Set cached value"""
        return await cache_set(self.key(suffix), value, ttl)

    async def delete(self, suffix: str) -> bool:
        """Delete cached value"""
        return await cache_delete(self.key(suffix))

    async def exists(self, suffix: str) -> bool:
        """Check if cache exists"""
        return await cache_exists(self.key(suffix))

    async def increment(self, suffix: str, amount: int = 1) -> int:
        """Increment counter"""
        return await cache_increment(self.key(suffix), amount)

    async def decrement(self, suffix: str, amount: int = 1) -> int:
        """Decrement counter"""
        return await cache_decrement(self.key(suffix), amount)


# Default cache manager
default_cache = CacheManager(prefix="rm")