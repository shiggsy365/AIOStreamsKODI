# -*- coding: utf-8 -*-
"""
AIOStreams provider implementation.
Handles all API communication with the AIOStreams backend.
"""
import time
import hashlib
import requests
import xbmc
import xbmcgui

from .base import BaseProvider
from ..cache import get_cache, cached


class AIOStreamsProvider(BaseProvider):
    """
    AIOStreams API provider.
    Primary provider for streaming content via Stremio-compatible API.
    """

    name = "aiostreams"
    display_name = "AIOStreams"
    enabled = True
    priority = 100  # Primary provider

    def __init__(self, base_url=None, timeout=10):
        """
        Initialize AIOStreams provider.

        Args:
            base_url: AIOStreams API base URL (optional, reads from settings)
            timeout: Request timeout in seconds
        """
        super().__init__()
        self._base_url = base_url
        self._timeout = timeout
        self._manifest = None

    def initialize(self):
        """Initialize provider and validate connection."""
        if not self.base_url:
            self.log('No base URL configured', xbmc.LOGWARNING)
            return False

        # Try to fetch manifest to validate connection
        manifest = self.get_manifest()
        if manifest:
            self._initialized = True
            self.log(f'Initialized with {len(manifest.get("catalogs", []))} catalogs', xbmc.LOGINFO)
            return True

        return False

    @property
    def base_url(self):
        """Get base URL, reading from settings if not set."""
        if self._base_url:
            return self._base_url

        try:
            from ..globals import g
            url = g.get_setting('base_url', '')
        except:
            import xbmcaddon
            addon = xbmcaddon.Addon()
            url = addon.getSetting('base_url') or ''

        # Strip /manifest.json if present
        if url.endswith('/manifest.json'):
            url = url[:-14]

        return url

    @property
    def timeout(self):
        """Get request timeout."""
        if self._timeout:
            return self._timeout

        try:
            from ..globals import g
            return g.get_int_setting('timeout', 10)
        except:
            return 10

    def _make_request(self, url, error_message='Request failed', cache_key=None):
        """
        Make HTTP request with conditional caching support.

        Args:
            url: URL to fetch
            error_message: Error message to display on failure
            cache_key: Optional cache key for conditional requests

        Returns:
            JSON response data, or None on error
        """
        headers = {}
        cache = get_cache()

        # Check for cached ETag/Last-Modified for conditional requests
        if cache_key:
            cached_headers = cache.get('http_headers', cache_key, 86400*365)
            if cached_headers:
                if 'etag' in cached_headers:
                    headers['If-None-Match'] = cached_headers['etag']
                if 'last-modified' in cached_headers:
                    headers['If-Modified-Since'] = cached_headers['last-modified']

        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)

            # 304 Not Modified - use cached data
            if response.status_code == 304:
                self.log(f'HTTP 304 Not Modified: {cache_key}', xbmc.LOGDEBUG)
                if cache_key:
                    parts = cache_key.split(':', 1)
                    if len(parts) == 2:
                        cached_data = cache.get(parts[0], parts[1], 86400*365)
                        if cached_data:
                            return cached_data
                return None

            response.raise_for_status()
            data = response.json()

            # Cache response headers for future conditional requests
            if cache_key:
                cache_headers = {}
                if 'etag' in response.headers:
                    cache_headers['etag'] = response.headers['etag']
                if 'last-modified' in response.headers:
                    cache_headers['last-modified'] = response.headers['last-modified']
                if cache_headers:
                    cache.set('http_headers', cache_key, cache_headers)

            return data

        except requests.Timeout:
            xbmcgui.Dialog().notification('AIOStreams', 'Request timed out', xbmcgui.NOTIFICATION_ERROR)
            return None
        except requests.RequestException as e:
            xbmcgui.Dialog().notification('AIOStreams', f'{error_message}', xbmcgui.NOTIFICATION_ERROR)
            self.log(f'Request error: {e}', xbmc.LOGERROR)
            return None
        except ValueError:
            xbmcgui.Dialog().notification('AIOStreams', 'Invalid JSON response', xbmcgui.NOTIFICATION_ERROR)
            return None

    def get_manifest(self):
        """
        Fetch the manifest with stale-while-revalidate caching.

        Returns:
            Manifest dict or None
        """
        base_url = self.base_url
        if not base_url:
            return None

        cache = get_cache()

        # Use base_url as cache key to support multiple profiles
        cache_key = hashlib.md5(base_url.encode()).hexdigest()[:16]
        full_cache_key = f'manifest:{cache_key}'

        # Check cache first
        cached = cache.get('manifest', cache_key, 86400*365)
        cache_age = cache.get_age('manifest', cache_key)

        if cached:
            # Fresh cache (< 24 hours) - serve immediately
            if cache_age is not None and cache_age < 86400:
                self.log(f'Serving fresh manifest from cache (age: {int(cache_age)}s)', xbmc.LOGDEBUG)
                return cached

            # Stale cache - check server with conditional request
            self.log(f'Cache stale (age: {int(cache_age)}s), checking server', xbmc.LOGDEBUG)
            manifest = self._make_request(
                f"{base_url}/manifest.json",
                'Error fetching manifest',
                cache_key=full_cache_key
            )

            if manifest:
                cache.set('manifest', cache_key, manifest)
                self.log('Manifest updated from server', xbmc.LOGINFO)
                return manifest
            else:
                # Return stale cache as fallback
                self.log('Using stale manifest as fallback', xbmc.LOGDEBUG)
                return cached

        # No cache - fetch fresh
        self.log('No cached manifest, fetching fresh', xbmc.LOGDEBUG)
        manifest = self._make_request(
            f"{base_url}/manifest.json",
            'Error fetching manifest',
            cache_key=full_cache_key
        )

        if manifest:
            cache.set('manifest', cache_key, manifest)

        self._manifest = manifest
        return manifest

    def get_streams(self, content_type, media_id):
        """
        Fetch streams for a given media ID.

        Args:
            content_type: Type of content ('movie' or 'series')
            media_id: IMDB ID or other identifier

        Returns:
            dict with 'streams' key or None
        """
        base_url = self.base_url
        if not base_url:
            return None

        url = f"{base_url}/stream/{content_type}/{media_id}.json"
        self.log(f'Requesting streams: {url}', xbmc.LOGINFO)

        result = self._make_request(url, 'Stream error')

        if result:
            stream_count = len(result.get('streams', []))
            self.log(f'Received {stream_count} streams for {media_id}', xbmc.LOGINFO)

        return result

    def search(self, query, content_type='movie', skip=0):
        """
        Search the catalog.

        Args:
            query: Search query string
            content_type: 'movie' or 'series'
            skip: Pagination offset

        Returns:
            dict with 'metas' key or None
        """
        base_url = self.base_url
        if not base_url:
            return None

        catalog_id = '39fe3b0.search'
        url = f"{base_url}/catalog/{content_type}/{catalog_id}/search={query}"

        if skip > 0:
            url += f"&skip={skip}"

        url += ".json"

        return self._make_request(url, 'Search error')

    def get_catalogs(self):
        """
        Get available catalogs from manifest.

        Returns:
            List of catalog dicts
        """
        manifest = self.get_manifest()
        if not manifest:
            return []

        return manifest.get('catalogs', [])

    def get_catalog(self, content_type, catalog_id, genre=None, skip=0):
        """
        Fetch a catalog with caching.

        Args:
            content_type: 'movie' or 'series'
            catalog_id: Catalog identifier
            genre: Optional genre filter
            skip: Pagination offset

        Returns:
            dict with 'metas' key or None
        """
        base_url = self.base_url
        if not base_url:
            return None

        cache = get_cache()

        # Build cache identifier
        cache_id = f"{content_type}:{catalog_id}:{genre or 'none'}:{skip}"

        # Check cache (6 hours)
        cached = cache.get('catalog', cache_id, 21600)
        if cached:
            return cached

        # Build URL
        url_parts = [f"{base_url}/catalog/{content_type}/{catalog_id}"]

        extras = []
        if genre:
            extras.append(f"genre={genre}")
        if skip > 0:
            extras.append(f"skip={skip}")

        if extras:
            url = f"{url_parts[0]}/{'&'.join(extras)}.json"
        else:
            url = f"{url_parts[0]}.json"

        self.log(f'Requesting catalog: {url}', xbmc.LOGINFO)
        catalog = self._make_request(url, 'Catalog error')

        if catalog:
            cache.set('catalog', cache_id, catalog)

        return catalog

    def get_meta(self, content_type, meta_id):
        """
        Fetch metadata with adaptive TTL caching.

        Args:
            content_type: 'movie' or 'series'
            meta_id: Metadata identifier

        Returns:
            dict with 'meta' key or None
        """
        base_url = self.base_url
        if not base_url:
            return None

        cache = get_cache()
        cache_key = f"{content_type}:{meta_id}"

        # Check with long TTL first
        cached = cache.get('metadata', cache_key, 86400*365)
        if cached:
            # Calculate appropriate TTL based on content age
            ttl = self._get_metadata_ttl(cached)

            # Re-check with calculated TTL
            cached = cache.get('metadata', cache_key, ttl)
            if cached:
                self.log(f'Metadata cache hit for {meta_id} (TTL: {ttl//86400} days)', xbmc.LOGDEBUG)
                return cached

        # Fetch from API
        url = f"{base_url}/meta/{content_type}/{meta_id}.json"
        self.log(f'Requesting meta: {url}', xbmc.LOGINFO)
        result = self._make_request(url, 'Meta error')

        if result:
            cache.set('metadata', cache_key, result)

        return result

    def _get_metadata_ttl(self, meta_data):
        """
        Determine appropriate cache TTL based on content age.

        Args:
            meta_data: Metadata dict

        Returns:
            TTL in seconds
        """
        from datetime import datetime

        try:
            meta = meta_data.get('meta', {})
            year = meta.get('year')

            if year:
                current_year = datetime.now().year

                # Recent/current year - may get updates
                if year >= current_year:
                    return 86400 * 7  # 7 days

                # Last year - moderate refresh
                if year >= current_year - 1:
                    return 86400 * 30  # 30 days

            # Older content is stable
            return 86400 * 90  # 90 days

        except:
            return 86400 * 30  # Default 30 days

    def get_subtitles(self, content_type, media_id):
        """
        Fetch subtitles for a media item.

        Args:
            content_type: Content type
            media_id: Media identifier

        Returns:
            dict with 'subtitles' key or None
        """
        base_url = self.base_url
        if not base_url:
            return None

        url = f"{base_url}/subtitles/{content_type}/{media_id}.json"
        self.log(f'Requesting subtitles: {url}', xbmc.LOGINFO)
        return self._make_request(url, 'Subtitle error')

    def test_connection(self):
        """
        Test connection to AIOStreams server.

        Returns:
            tuple (success, message)
        """
        base_url = self.base_url

        if not base_url:
            return False, "No base URL configured"

        try:
            start_time = time.time()
            manifest = self.get_manifest()
            elapsed = time.time() - start_time

            if manifest:
                catalog_count = len(manifest.get('catalogs', []))
                return True, f"Connected! {catalog_count} catalogs available. Response time: {elapsed:.2f}s"
            else:
                return False, "Failed to fetch manifest"

        except Exception as e:
            return False, f"Connection error: {str(e)}"
