"""Configured HTTP client for the AIOStreams/Stremio-compatible API."""
import hashlib
from urllib.parse import quote

import requests

from .stream_utils import client_user_agent


class AIOStreamsClientError(Exception):
    """A request failed before a usable AIOStreams response was available."""


class AIOStreamsClient:
    """Own URL construction, request headers, and configuration cache identity."""

    def __init__(self, base_url, timeout=10, addon_version='unknown', session=None):
        self.base_url = (base_url or '').rstrip('/')
        if self.base_url.endswith('/manifest.json'):
            self.base_url = self.base_url[:-14]
        self.timeout = timeout
        self.addon_version = addon_version
        self.session = session or requests.Session()

    @property
    def fingerprint(self):
        return hashlib.sha256(self.base_url.encode('utf-8')).hexdigest()[:16]

    def cache_key(self, namespace, *parts):
        encoded_parts = ':'.join(str(part) for part in parts)
        return f'{self.fingerprint}:{namespace}:{encoded_parts}'

    def _url(self, *path_parts):
        if not self.base_url:
            raise AIOStreamsClientError('AIOStreams is not configured')
        path = '/'.join(quote(str(part), safe=':=&') for part in path_parts)
        return f'{self.base_url}/{path}'

    def _get(self, operation, *path_parts, headers=None):
        request_headers = {'User-Agent': client_user_agent(self.addon_version)}
        request_headers.update(headers or {})
        try:
            response = self.session.get(
                self._url(*path_parts), headers=request_headers, timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as error:
            raise AIOStreamsClientError(f'{operation} request failed') from error
        except ValueError as error:
            raise AIOStreamsClientError(f'{operation} returned invalid JSON') from error

    def get_manifest(self):
        return self._get('manifest', 'manifest.json')

    def get_catalog(self, content_type, catalog_id, genre=None, skip=0):
        extra = []
        if genre:
            extra.append(f'genre={genre}')
        if skip:
            extra.append(f'skip={skip}')
        suffix = f"{'&'.join(extra)}.json" if extra else '.json'
        return self._get('catalog', 'catalog', content_type, catalog_id, suffix)

    def search(self, query, content_type, catalog_id, skip=0):
        extra = f'search={query}'
        if skip:
            extra = f'{extra}&skip={skip}'
        return self._get('search', 'catalog', content_type, catalog_id, f'{extra}.json')

    def get_meta(self, content_type, meta_id):
        return self._get('metadata', 'meta', content_type, f'{meta_id}.json')

    def get_streams(self, content_type, playable_id):
        return self._get('streams', 'stream', content_type, f'{playable_id}.json')

    def get_subtitles(self, content_type, playable_id):
        return self._get('subtitles', 'subtitles', content_type, f'{playable_id}.json')
