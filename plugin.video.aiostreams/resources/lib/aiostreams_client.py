"""Configured HTTP client for the AIOStreams/Stremio-compatible API."""
import hashlib
from urllib.parse import quote

import requests

from .stream_utils import client_user_agent


class AIOStreamsClientError(Exception):
    """A request failed before a usable AIOStreams response was available."""


class AIOStreamsClient:
    """Own configured requests and disposable AIOStreams response caches."""

    def __init__(self, base_url, timeout=10, addon_version='unknown', session=None,
                 cache=None, sql_cache=None):
        self.base_url = (base_url or '').rstrip('/')
        if self.base_url.endswith('/manifest.json'):
            self.base_url = self.base_url[:-14]
        self.timeout = timeout
        self.addon_version = addon_version
        self.session = session or requests.Session()
        self._cache = cache
        self._sql_cache = sql_cache

    @property
    def fingerprint(self):
        return hashlib.sha256(self.base_url.encode('utf-8')).hexdigest()[:16]

    def cache_key(self, namespace, *parts):
        encoded_parts = ':'.join(str(part) for part in parts)
        return ':'.join(part for part in (self.fingerprint, namespace, encoded_parts) if part)

    def _url(self, *path_parts):
        if not self.base_url:
            raise AIOStreamsClientError('AIOStreams is not configured')
        path = '/'.join(quote(str(part), safe='%:=&') for part in path_parts)
        return f'{self.base_url}/{path}'

    @staticmethod
    def _path_value(value):
        """Encode a dynamic path value once before joining Stremio extras."""
        return quote(str(value), safe='')

    def _get_cache(self):
        if self._cache is not None:
            return self._cache
        try:
            from .cache import get_cache
            self._cache = get_cache()
        except Exception:
            self._cache = False
        return self._cache or None

    def _cache_get(self, cache_type, identifier, ttl):
        cache = self._get_cache()
        if not cache:
            return None
        try:
            return cache.get(cache_type, identifier, ttl)
        except Exception:
            return None

    def _cache_set(self, cache_type, identifier, value):
        cache = self._get_cache()
        if cache:
            try:
                cache.set(cache_type, identifier, value)
            except Exception:
                pass

    def _cache_age(self, cache_type, identifier):
        cache = self._get_cache()
        if not cache:
            return None
        try:
            return cache.get_age(cache_type, identifier)
        except Exception:
            return None

    def _get(self, operation, *path_parts, cache_type=None, cache_id=None):
        request_headers = {'User-Agent': client_user_agent(self.addon_version)}
        header_key = self.cache_key('http_headers', cache_type or operation, cache_id or '')
        if cache_type and cache_id:
            cached_headers = self._cache_get('http_headers', header_key, 86400 * 365)
            if cached_headers:
                if cached_headers.get('etag'):
                    request_headers['If-None-Match'] = cached_headers['etag']
                if cached_headers.get('last-modified'):
                    request_headers['If-Modified-Since'] = cached_headers['last-modified']
        try:
            response = self.session.get(
                self._url(*path_parts), headers=request_headers, timeout=self.timeout
            )
            if response.status_code == 304:
                cached = self._cache_get(cache_type, cache_id, 86400 * 365)
                if cached is not None:
                    return cached
                raise AIOStreamsClientError(f'{operation} returned an empty cache response')
            response.raise_for_status()
            data = response.json()
            if cache_type and cache_id:
                response_headers = {}
                if response.headers.get('etag'):
                    response_headers['etag'] = response.headers['etag']
                if response.headers.get('last-modified'):
                    response_headers['last-modified'] = response.headers['last-modified']
                if response_headers:
                    self._cache_set('http_headers', header_key, response_headers)
            return data
        except requests.RequestException as error:
            raise AIOStreamsClientError(f'{operation} request failed') from error
        except ValueError as error:
            raise AIOStreamsClientError(f'{operation} returned invalid JSON') from error

    def get_manifest(self, force=False):
        cache_id = self.cache_key('manifest')
        cached = self._cache_get('manifest', cache_id, 86400 * 365)
        if cached is not None and not force:
            age = self._cache_age('manifest', cache_id)
            if age is not None and age < 300:
                return cached
        try:
            manifest = self._get(
                'manifest', 'manifest.json', cache_type='manifest', cache_id=cache_id
            )
        except AIOStreamsClientError:
            if cached is not None:
                return cached
            raise
        self._cache_set('manifest', cache_id, manifest)
        return manifest

    def get_catalog(self, content_type, catalog_id, genre=None, skip=0):
        cache_id = self.cache_key('catalog', content_type, catalog_id, genre or '', skip)
        cached = self._sql_get_catalog(content_type, catalog_id, genre, skip)
        if cached is not None:
            return cached
        cached = self._cache_get('catalog', cache_id, 21600)
        if cached is not None:
            return cached
        extra = []
        if genre:
            extra.append(f'genre={quote(str(genre), safe="")}')
        if skip:
            extra.append(f'skip={skip}')
        catalog_path = self._path_value(catalog_id)
        if extra:
            catalog = self._get(
                'catalog', 'catalog', self._path_value(content_type), catalog_path,
                f"{'&'.join(extra)}.json",
            )
        else:
            # Stremio catalog URLs put the extension directly on the catalog ID.
            # A separate ".json" path segment becomes ``catalog-id/.json``.
            catalog = self._get(
                'catalog', 'catalog', self._path_value(content_type), f'{catalog_path}.json',
            )
        self._cache_set('catalog', cache_id, catalog)
        self._sql_set_catalog(content_type, catalog_id, genre, skip, catalog, 21600)
        return catalog

    def search(self, query, content_type, catalog_id, skip=0):
        extra = f'search={quote(str(query), safe="")}'
        if skip:
            extra = f'{extra}&skip={skip}'
        return self._get(
            'search', 'catalog', self._path_value(content_type), self._path_value(catalog_id),
            f'{extra}.json',
        )

    def get_meta(self, content_type, meta_id):
        cache_id = self.cache_key('metadata', content_type, meta_id)
        cached = self._sql_get_meta(content_type, meta_id)
        if cached is not None:
            return cached
        cached = self._cache_get('metadata', cache_id, 86400 * 365)
        if cached is not None:
            cached = self._cache_get('metadata', cache_id, self.metadata_ttl(cached))
            if cached is not None:
                return cached
        metadata = self._get(
            'metadata', 'meta', self._path_value(content_type), f'{self._path_value(meta_id)}.json',
        )
        ttl = self.metadata_ttl(metadata)
        self._cache_set('metadata', cache_id, metadata)
        self._sql_set_meta(content_type, meta_id, metadata, ttl)
        return metadata

    def get_streams(self, content_type, playable_id):
        return self._get(
            'streams', 'stream', self._path_value(content_type),
            f'{self._path_value(playable_id)}.json',
        )

    def get_subtitles(self, content_type, playable_id):
        return self._get(
            'subtitles', 'subtitles', self._path_value(content_type),
            f'{self._path_value(playable_id)}.json',
        )

    def test_connection(self):
        """Fetch the manifest as the backend connection health check."""
        return self.get_manifest(force=True)

    @staticmethod
    def metadata_ttl(metadata):
        try:
            from datetime import datetime
            year = (metadata.get('meta') or {}).get('year')
            if year and int(year) >= datetime.now().year:
                return 86400 * 7
            if year and int(year) >= datetime.now().year - 1:
                return 86400 * 30
        except (AttributeError, TypeError, ValueError):
            pass
        return 86400 * 90

    def _sql_get_meta(self, content_type, meta_id):
        if not self._sql_cache:
            return None
        try:
            return self._sql_cache.get_meta(self.fingerprint, content_type, meta_id)
        except Exception:
            return None

    def _sql_set_meta(self, content_type, meta_id, metadata, ttl):
        if self._sql_cache:
            try:
                self._sql_cache.set_meta(self.fingerprint, content_type, meta_id, metadata, ttl)
            except Exception:
                pass

    def _sql_get_catalog(self, content_type, catalog_id, genre, skip):
        if not self._sql_cache:
            return None
        try:
            return self._sql_cache.get_catalog(
                self.fingerprint, content_type, catalog_id, genre, skip
            )
        except Exception:
            return None

    def _sql_set_catalog(self, content_type, catalog_id, genre, skip, catalog, ttl):
        if self._sql_cache:
            try:
                self._sql_cache.set_catalog(
                    self.fingerprint, content_type, catalog_id, genre, skip, catalog, ttl
                )
            except Exception:
                pass
