# cache_manager.py
import asyncio
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
# --- Cache Implementation with Expiry ---
class CacheWithExpiry:

    def __init__(self, expiry_seconds: int):
        self.cache = {}
        self.expiry_seconds = expiry_seconds
        self._lock = asyncio.Lock()

    async def get(self, key):
        """Get item from cache if it exists and is not expired (async safe)"""
        async with self._lock:
            if key in self.cache:
                item, timestamp = self.cache[key]
                if time.time() - timestamp < self.expiry_seconds:
                    logger.debug(f"Cache hit for key: {key}")
                    return item
                else:
                    logger.debug(f"Cache expired for key: {key}")
                    del self.cache[key]
            logger.debug(f"Cache miss for key: {key}")
            return None

    async def set(self, key, value):
        """Add item to cache with current timestamp (async safe)"""
        async with self._lock:
            self.cache[key] = (value, time.time())
            logger.debug(f"Cached value for key: {key}")

    async def clear_expired(self) -> int:
        """Remove all expired items from cache (async safe)"""
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                k for k, (_, t) in self.cache.items()
                if current_time - t >= self.expiry_seconds
            ]
            count = 0
            for key in expired_keys:
                try:
                    del self.cache[key]
                    count += 1
                except KeyError:
                    pass  # Should not happen, but for robustness
            return count


class CacheManager:

    def __init__(self, cache_expiry_days: int):
        self.cache_expiry_seconds = cache_expiry_days * 24 * 60 * 60
        self.product_cache = CacheWithExpiry(self.cache_expiry_seconds)
        self.link_cache = CacheWithExpiry(self.cache_expiry_seconds)
        self.resolved_url_cache = CacheWithExpiry(self.cache_expiry_seconds)
        logger.info(f"Cache expiry set to {cache_expiry_days} days.")

    async def periodic_cache_cleanup(self, context):
        """Periodically clean up expired cache items (Job Queue callback)"""
        try:
            product_expired = await self.product_cache.clear_expired()
            link_expired = await self.link_cache.clear_expired()
            resolved_expired = await self.resolved_url_cache.clear_expired()
            logger.info(
                f"Cache cleanup: Removed {product_expired} product, {link_expired} link, {resolved_expired} resolved URL items."
            )
            logger.info(
                f"Cache stats: {len(self.product_cache.cache)} products, {len(self.link_cache.cache)} links, {len(self.resolved_url_cache.cache)} resolved URLs in cache."
            )
        except Exception as e:
            logger.error(f"Error in periodic cache cleanup job: {e}")

