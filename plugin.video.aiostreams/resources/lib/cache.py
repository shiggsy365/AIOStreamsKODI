# -*- coding: utf-8 -*-
"""
Tiered caching system for AIOStreams addon.
Three-tier architecture: Memory -> Disk -> Network
Based on Seren's cache patterns for optimal performance.
"""
import os
import json
import time
import hashlib
import functools
import threading
import xbmc
import xbmcaddon
import xbmcvfs


class MemoryCache:
    """
    In-memory cache layer for hot data.
    Thread-safe with automatic expiration.
    """

    def __init__(self, max_size=500):
        """
        Initialize memory cache.

        Args:
            max_size: Maximum number of entries to keep in memory
        """
        self._cache = {}
        self._max_size = max_size
        self._lock = threading.RLock()
        self._access_order = []  # For LRU eviction

    def get(self, key, ttl_seconds=None):
        """
        Get value from memory cache.

        Args:
            key: Cache key
            ttl_seconds: Optional TTL to check against

        Returns:
            Cached data or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]
            timestamp = entry.get('timestamp', 0)

            # Check expiration if TTL provided
            if ttl_seconds is not None and time.time() - timestamp >= ttl_seconds:
                self._remove(key)
                return None

            # Update access order for LRU
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

            return entry.get('data')

    def set(self, key, data, timestamp=None):
        """
        Set value in memory cache.

        Args:
            key: Cache key
            data: Data to cache
            timestamp: Optional timestamp (defaults to now)
        """
        with self._lock:
            # Evict oldest entries if at capacity
            while len(self._cache) >= self._max_size and self._access_order:
                oldest_key = self._access_order.pop(0)
                self._cache.pop(oldest_key, None)

            self._cache[key] = {
                'data': data,
                'timestamp': timestamp or time.time()
            }

            # Update access order
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)

    def _remove(self, key):
        """Remove entry from cache."""
        self._cache.pop(key, None)
        if key in self._access_order:
            self._access_order.remove(key)

    def invalidate(self, key):
        """Invalidate a specific cache entry."""
        with self._lock:
            self._remove(key)

    def invalidate_prefix(self, prefix):
        """Invalidate all entries with keys starting with prefix."""
        with self._lock:
            keys_to_remove = [k for k in self._cache.keys() if k.startswith(prefix)]
            for key in keys_to_remove:
                self._remove(key)

    def clear(self):
        """Clear all entries from memory cache."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()

    def get_stats(self):
        """Get cache statistics."""
        with self._lock:
            return {
                'entries': len(self._cache),
                'max_size': self._max_size
            }


class TieredCache:
    """
    Three-tier cache: Memory -> Disk -> Network.
    Automatically promotes frequently accessed data to faster tiers.
    """

    # Default TTLs by cache type
    DEFAULT_TTLS = {
        'manifest': 86400,      # 24 hours
        'catalog': 21600,       # 6 hours
        'metadata': 2592000,    # 30 days
        'http_headers': 31536000,  # 1 year
        'search': 3600,         # 1 hour
        'streams': 300,         # 5 minutes
    }

    def __init__(self, memory_size=100):
        """
        Initialize tiered cache.

        Args:
            memory_size: Max entries for memory cache
        """
        self._memory = MemoryCache(max_size=memory_size)
        self._cache_dir = None
        self._pending_writes = {}
        self._write_lock = threading.Lock()

    def _get_cache_dir(self, cache_type=None):
        """
        Get cache directory path, creating if needed.
        
        Uses shared cache for metadata and HTTP headers (accessible by all Kodi profiles).
        Uses profile-specific cache for other data types.
        
        Args:
            cache_type: Type of cache (metadata, http_headers, etc.)
        
        Returns:
            str: Cache directory path
        """
        # Use shared cache for metadata and HTTP headers across all Kodi profiles
        if cache_type in ['metadata', 'http_headers']:
            try:
                from resources.lib.shared_cache import SharedCacheManager
                shared_dir = SharedCacheManager.get_shared_cache_dir()
                
                # Ensure directory exists
                if not xbmcvfs.exists(shared_dir):
                    xbmcvfs.mkdirs(shared_dir)
                
                return shared_dir
            except Exception as e:
                xbmc.log(
                    f'[AIOStreams] Failed to get shared cache dir, falling back to profile cache: {e}',
                    xbmc.LOGWARNING
                )
                # Fall through to profile-specific cache on error
        
        # Use profile-specific cache for other data types
        if self._cache_dir is None:
            addon = xbmcaddon.Addon()
            profile_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
            self._cache_dir = os.path.join(profile_path, 'cache')

            if not xbmcvfs.exists(self._cache_dir):
                xbmcvfs.mkdirs(self._cache_dir)

        return self._cache_dir

    def _get_cache_key(self, cache_type, identifier):
        """Generate cache filename from type and identifier."""
        key_string = f"{cache_type}:{identifier}"
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"{cache_type}_{key_hash}.json"

    def _get_memory_key(self, cache_type, identifier):
        """Generate memory cache key."""
        return f"{cache_type}:{identifier}"

    def get(self, cache_type, identifier, ttl_seconds=None):
        """
        Get data from cache, checking tiers in order.

        Args:
            cache_type: Type of cache (manifest, catalog, metadata, etc.)
            identifier: Unique identifier for this cache entry
            ttl_seconds: Optional TTL override (defaults based on cache_type)

        Returns:
            Cached data or None if not found/expired
        """
        if ttl_seconds is None:
            ttl_seconds = self.DEFAULT_TTLS.get(cache_type, 86400)

        memory_key = self._get_memory_key(cache_type, identifier)

        # Tier 1: Memory cache (instant)
        data = self._memory.get(memory_key, ttl_seconds)
        if data is not None:
            xbmc.log(f'[AIOStreams] Cache HIT (memory): {cache_type}:{identifier}', xbmc.LOGDEBUG)
            return data

        # Tier 2: Disk cache
        data = self._get_from_disk(cache_type, identifier, ttl_seconds)
        if data is not None:
            # Promote to memory cache
            self._memory.set(memory_key, data)
            xbmc.log(f'[AIOStreams] Cache HIT (disk): {cache_type}:{identifier}', xbmc.LOGDEBUG)
            return data

        xbmc.log(f'[AIOStreams] Cache MISS: {cache_type}:{identifier}', xbmc.LOGDEBUG)
        return None

    def _get_from_disk(self, cache_type, identifier, ttl_seconds):
        """Get data from disk cache."""
        cache_dir = self._get_cache_dir(cache_type)
        cache_file = os.path.join(cache_dir, self._get_cache_key(cache_type, identifier))

        if not xbmcvfs.exists(cache_file):
            return None

        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)

            timestamp = cache_data.get('timestamp', 0)

            # Check if cache is still valid
            if time.time() - timestamp < ttl_seconds:
                return cache_data.get('data')
            else:
                # Expired, delete file
                xbmcvfs.delete(cache_file)
                xbmc.log(f'[AIOStreams] Cache EXPIRED: {cache_type}:{identifier}', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Cache read error: {e}', xbmc.LOGERROR)

        return None

    def set(self, cache_type, identifier, data, checksum=None):
        """
        Store data in cache (both memory and disk).

        Args:
            cache_type: Type of cache
            identifier: Unique identifier
            data: Data to cache
            checksum: Optional checksum for data validation
        """
        memory_key = self._get_memory_key(cache_type, identifier)
        timestamp = time.time()

        # Store in memory immediately
        self._memory.set(memory_key, data, timestamp)

        # Store on disk
        self._save_to_disk(cache_type, identifier, data, timestamp, checksum)

    def _save_to_disk(self, cache_type, identifier, data, timestamp, checksum=None):
        """Save data to disk cache."""
        cache_dir = self._get_cache_dir(cache_type)
        cache_file = os.path.join(cache_dir, self._get_cache_key(cache_type, identifier))

        try:
            cache_data = {
                'timestamp': timestamp,
                'cache_type': cache_type,
                'identifier': identifier,
                'data': data
            }

            # Add checksum if provided or generate one
            if checksum:
                cache_data['checksum'] = checksum
            else:
                try:
                    cache_data['checksum'] = hashlib.md5(
                        json.dumps(data, sort_keys=True).encode()
                    ).hexdigest()
                except:
                    pass  # Skip checksum on serialization error

            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)

            xbmc.log(f'[AIOStreams] Cache SET: {cache_type}:{identifier}', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Cache write error: {e}', xbmc.LOGERROR)

    def get_age(self, cache_type, identifier):
        """
        Get age of cached data in seconds.

        Args:
            cache_type: Type of cache
            identifier: Unique identifier

        Returns:
            Age in seconds, or None if not cached
        """
        cache_dir = self._get_cache_dir(cache_type)
        cache_file = os.path.join(cache_dir, self._get_cache_key(cache_type, identifier))

        if not xbmcvfs.exists(cache_file):
            return None

        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            timestamp = cache_data.get('timestamp', 0)
            return time.time() - timestamp
        except:
            return None

    def invalidate(self, cache_type, identifier):
        """Invalidate a specific cache entry from all tiers."""
        memory_key = self._get_memory_key(cache_type, identifier)
        self._memory.invalidate(memory_key)

        cache_dir = self._get_cache_dir(cache_type)
        cache_file = os.path.join(cache_dir, self._get_cache_key(cache_type, identifier))
        if xbmcvfs.exists(cache_file):
            xbmcvfs.delete(cache_file)

    def invalidate_type(self, cache_type):
        """Invalidate all entries of a specific type."""
        # Clear from memory
        self._memory.invalidate_prefix(f"{cache_type}:")

        # Clear from disk
        cache_dir = self._get_cache_dir()
        try:
            dirs, files = xbmcvfs.listdir(cache_dir)
            for filename in files:
                if filename.startswith(f"{cache_type}_") and filename.endswith('.json'):
                    xbmcvfs.delete(os.path.join(cache_dir, filename))
        except:
            pass

    def clear_memory(self):
        """Clear memory cache only."""
        self._memory.clear()

    def clear_all(self):
        """Clear all caches (memory and disk)."""
        self._memory.clear()
        self.cleanup_expired(force_all=True)

    def cleanup_expired(self, force_all=False, max_age_days=30):
        """
        Remove expired cache files from disk.

        Args:
            force_all: If True, remove all cache files
            max_age_days: Maximum age in days before cleanup
        """
        cache_dir = self._get_cache_dir()

        if not xbmcvfs.exists(cache_dir):
            return

        try:
            dirs, files = xbmcvfs.listdir(cache_dir)
            expired_count = 0
            cache_types = {}

            max_age_seconds = max_age_days * 86400

            for filename in files:
                if not filename.endswith('.json'):
                    continue

                file_path = os.path.join(cache_dir, filename)

                if force_all:
                    try:
                        try:
                            with open(file_path, 'r') as f:
                                cache_data = json.load(f)
                                cache_type = cache_data.get('cache_type', 'unknown')
                                cache_types[cache_type] = cache_types.get(cache_type, 0) + 1
                        except:
                            cache_types['unknown'] = cache_types.get('unknown', 0) + 1

                        os.remove(file_path)
                        expired_count += 1
                    except:
                        pass
                    continue

                try:
                    with open(file_path, 'r') as f:
                        cache_data = json.load(f)

                    timestamp = cache_data.get('timestamp', 0)

                    if time.time() - timestamp >= max_age_seconds:
                        xbmcvfs.delete(file_path)
                        expired_count += 1
                except:
                    # Delete corrupted cache files
                    xbmcvfs.delete(file_path)

            if expired_count > 0:
                if force_all:
                    type_summary = ', '.join([f'{count} {ctype}' for ctype, count in cache_types.items()])
                    xbmc.log(f'[AIOStreams] Cleared {expired_count} cache files ({type_summary})', xbmc.LOGINFO)
                else:
                    xbmc.log(f'[AIOStreams] Cleaned up {expired_count} expired cache files', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Cache cleanup error: {e}', xbmc.LOGERROR)

    def flush(self):
        """Flush any pending writes (called on shutdown)."""
        pass  # Currently writes are synchronous

    def get_stats(self):
        """Get cache statistics."""
        memory_stats = self._memory.get_stats()
        cache_dir = self._get_cache_dir()

        disk_count = 0
        disk_size = 0

        try:
            dirs, files = xbmcvfs.listdir(cache_dir)
            for filename in files:
                if filename.endswith('.json'):
                    disk_count += 1
                    file_path = os.path.join(cache_dir, filename)
                    try:
                        disk_size += os.path.getsize(file_path)
                    except:
                        pass
        except:
            pass

        return {
            'memory': memory_stats,
            'disk': {
                'entries': disk_count,
                'size_kb': disk_size / 1024
            }
        }


# Global cache instance
_cache = None


def get_cache():
    """Get global TieredCache instance."""
    global _cache
    if _cache is None:
        _cache = TieredCache()
    return _cache


# Decorator for automatic caching
def cached(cache_type, ttl_seconds=None, key_func=None):
    """
    Decorator for automatic function result caching.

    Args:
        cache_type: Type of cache to use
        ttl_seconds: Optional TTL override
        key_func: Optional function to generate cache key from args
                  If None, uses function name + hashed args

    Usage:
        @cached('catalog', ttl_seconds=21600)
        def get_catalog(content_type, catalog_id):
            return api_call(...)
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()

            # Generate cache key
            if key_func:
                identifier = key_func(*args, **kwargs)
            else:
                # Default: function name + arg hash
                arg_str = f"{args}:{sorted(kwargs.items())}"
                arg_hash = hashlib.md5(arg_str.encode()).hexdigest()[:16]
                identifier = f"{func.__name__}:{arg_hash}"

            # Check cache
            ttl = ttl_seconds if ttl_seconds else TieredCache.DEFAULT_TTLS.get(cache_type, 86400)
            cached_data = cache.get(cache_type, identifier, ttl)

            if cached_data is not None:
                return cached_data

            # Execute function
            result = func(*args, **kwargs)

            # Cache result if not None
            if result is not None:
                cache.set(cache_type, identifier, result)

            return result
        return wrapper
    return decorator


# ============================================================================
# Legacy API compatibility (for existing code)
# ============================================================================

def get_cache_dir():
    """Get cache directory path (legacy compatibility)."""
    return get_cache()._get_cache_dir()


def get_cached_data(cache_type, identifier, ttl_seconds=86400*365):
    """Get data from cache (legacy compatibility)."""
    return get_cache().get(cache_type, identifier, ttl_seconds)


def cache_data(cache_type, identifier, data):
    """Store data in cache (legacy compatibility)."""
    get_cache().set(cache_type, identifier, data)


def get_cached_meta(content_type, item_id, ttl_seconds=2592000):
    """Get metadata from cache (legacy compatibility)."""
    return get_cache().get('metadata', f"{content_type}:{item_id}", ttl_seconds)


def cache_meta(content_type, item_id, metadata):
    """Store metadata in cache (legacy compatibility)."""
    get_cache().set('metadata', f"{content_type}:{item_id}", metadata)


def get_cache_age(cache_type, identifier):
    """Get cache age (legacy compatibility)."""
    return get_cache().get_age(cache_type, identifier)


def cleanup_expired_cache(force_all=False):
    """Remove expired cache files (legacy compatibility)."""
    get_cache().cleanup_expired(force_all=force_all)
