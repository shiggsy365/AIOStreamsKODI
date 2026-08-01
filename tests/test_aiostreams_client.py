import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'plugin.video.aiostreams'))

from resources.lib.aiostreams_client import AIOStreamsClient  # noqa: E402


class Response:
    def __init__(self, data, status_code=200, headers=None):
        self.data = data
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


class Session:
    def __init__(self):
        self.calls = []

    def get(self, url, headers, timeout):
        self.calls.append((url, headers, timeout))
        return Response({'ok': True})


class FixedResponseSession(Session):
    def __init__(self, response):
        super().__init__()
        self.response = response

    def get(self, url, headers, timeout):
        self.calls.append((url, headers, timeout))
        return self.response


class Cache:
    def __init__(self):
        self.values = {}

    def get(self, cache_type, identifier, ttl):
        return self.values.get((cache_type, identifier))

    def set(self, cache_type, identifier, value):
        self.values[(cache_type, identifier)] = value

    def get_age(self, cache_type, identifier):
        return self.age

    age = 0


class SqlCache:
    def __init__(self):
        self.catalog_reads = []
        self.catalog_writes = []
        self.meta_reads = []
        self.meta_writes = []

    def get_catalog(self, *args):
        self.catalog_reads.append(args)
        return None

    def set_catalog(self, *args):
        self.catalog_writes.append(args)

    def get_meta(self, *args):
        self.meta_reads.append(args)
        return None

    def set_meta(self, *args):
        self.meta_writes.append(args)


class AIOStreamsClientTests(unittest.TestCase):
    def test_manifest_url_and_identity_are_configuration_scoped(self):
        session = Session()
        client = AIOStreamsClient(
            'https://example.invalid/stremio/secret/manifest.json',
            timeout=12, addon_version='1.2.3', session=session,
        )

        self.assertEqual({'ok': True}, client.get_manifest())
        self.assertEqual(
            'https://example.invalid/stremio/secret/manifest.json', session.calls[0][0]
        )
        self.assertEqual('AIOStreams/Kodi-1.2.3', session.calls[0][1]['User-Agent'])
        self.assertEqual(12, session.calls[0][2])
        self.assertNotEqual(
            client.cache_key('catalog', 'movie', 'popular'),
            AIOStreamsClient('https://another.invalid', session=Session()).cache_key(
                'catalog', 'movie', 'popular'
            ),
        )

    def test_dynamic_catalog_values_are_url_encoded(self):
        session = Session()
        client = AIOStreamsClient('https://example.invalid', session=session)

        client.search('The Last of Us / test', 'movie', 'search id', skip=20)

        self.assertEqual(
            'https://example.invalid/catalog/movie/search%20id/search=The%20Last%20of%20Us%20%2F%20test&skip=20.json',
            session.calls[0][0],
        )

    def test_catalog_and_metadata_caches_include_configuration_fingerprint(self):
        session = Session()
        cache = Cache()
        sql_cache = SqlCache()
        client = AIOStreamsClient(
            'https://example.invalid/config-a', session=session, cache=cache, sql_cache=sql_cache,
        )

        client.get_catalog('movie', 'popular', genre='Sci-Fi', skip=20)
        client.get_meta('movie', 'tt1234567')

        self.assertEqual(client.fingerprint, sql_cache.catalog_reads[0][0])
        self.assertEqual(client.fingerprint, sql_cache.catalog_writes[0][0])
        self.assertEqual(client.fingerprint, sql_cache.meta_reads[0][0])
        self.assertEqual(client.fingerprint, sql_cache.meta_writes[0][0])
        self.assertIn(
            ('catalog', client.cache_key('catalog', 'movie', 'popular', 'Sci-Fi', 20)),
            cache.values,
        )
        self.assertIn(
            ('metadata', client.cache_key('metadata', 'movie', 'tt1234567')),
            cache.values,
        )

    def test_manifest_revalidation_uses_only_the_matching_configuration_cache(self):
        cache = Cache()
        cache.age = 600
        session = FixedResponseSession(Response({}, status_code=304))
        client = AIOStreamsClient('https://example.invalid/config-a', session=session, cache=cache)
        manifest_key = client.cache_key('manifest')
        header_key = client.cache_key('http_headers', 'manifest', manifest_key)
        cache.values[('manifest', manifest_key)] = {'id': 'configured-manifest'}
        cache.values[('http_headers', header_key)] = {'etag': 'manifest-etag'}

        self.assertEqual({'id': 'configured-manifest'}, client.get_manifest(force=True))
        self.assertEqual('manifest-etag', session.calls[0][1]['If-None-Match'])


if __name__ == '__main__':
    unittest.main()
