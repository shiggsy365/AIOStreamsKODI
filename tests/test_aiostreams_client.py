import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'plugin.video.aiostreams'))

from resources.lib.aiostreams_client import AIOStreamsClient  # noqa: E402


class Response:
    def __init__(self, data):
        self.data = data

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


if __name__ == '__main__':
    unittest.main()
