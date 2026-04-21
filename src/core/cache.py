import json
import logging
from typing import Optional, Any
import redis.asyncio as redis
from src.core.config import settings

logger = logging.getLogger(__name__)

redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)

async def get_cached(key: str) -> Optional[Any]:
    """Get value from cache and deserialize JSON."""
    try:
        data = await redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Cache get error: {e}")
    return None

async def set_cached(key: str, value: Any, ttl: int = 3600):
    """Serialize to JSON and store in Redis with TTL."""
    try:
        await redis_client.setex(key, ttl, json.dumps(value))
    except Exception as e:
        logger.warning(f"Cache set error: {e}")

async def delete_cached(key: str):
    try:
        await redis_client.delete(key)
    except Exception as e:
        logger.warning(f"Cache delete error: {e}")

# Specific cache keys
def places_cache_key(query: str, destination: str) -> str:
    return f"places:{query}:{destination}"