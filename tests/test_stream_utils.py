import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'plugin.video.aiostreams'))

from resources.lib.stream_utils import (  # noqa: E402
    DIRECT_URL, EXTERNAL_URL, SYNTHETIC_ERROR, SYNTHETIC_STATISTIC,
    TORRENT, UNKNOWN, USENET, YOUTUBE, canonical_episode_id,
    canonical_meta_id, classify_stream, client_user_agent, display_label, kodi_headers,
    matching_episode_id, stream_display_fields,
    normalize_streams, playable_url, stream_search_text,
)


class StreamUtilsTests(unittest.TestCase):
    def test_client_identity_is_recognized_by_aiostreams(self):
        self.assertEqual('AIOStreams/Kodi-1.2.3', client_user_agent('1.2.3'))

    def test_synthetic_entries_override_external_url(self):
        self.assertEqual(SYNTHETIC_ERROR, classify_stream({
            'externalUrl': 'https://example.invalid/project',
            'streamData': {'type': 'error'},
        }))
        self.assertEqual(SYNTHETIC_STATISTIC, classify_stream({
            'externalUrl': 'https://example.invalid/project',
            'streamData': {'type': 'statistic'},
        }))

    def test_direct_url_and_external_url_are_distinct(self):
        self.assertEqual(DIRECT_URL, classify_stream({'url': 'https://media.invalid/a.mkv'}))
        self.assertEqual(EXTERNAL_URL, classify_stream({'externalUrl': 'https://example.invalid'}))
        self.assertEqual('', playable_url({'externalUrl': 'https://example.invalid'}))
        self.assertEqual(UNKNOWN, classify_stream({'url': 'magnet:?xt=urn:btih:abc'}))

    def test_unsupported_transports_are_classified(self):
        self.assertEqual(TORRENT, classify_stream({'infoHash': 'abc'}))
        self.assertEqual(YOUTUBE, classify_stream({'ytId': 'abc'}))
        self.assertEqual(USENET, classify_stream({'nzbUrl': 'https://x.invalid/a.nzb'}))
        self.assertEqual(UNKNOWN, classify_stream({'name': 'mystery'}))

    def test_proxy_request_headers_use_kodi_url_syntax(self):
        stream = {'url': 'https://media.invalid/a', 'behaviorHints': {
            'proxyHeaders': {'request': {'User-Agent': 'Kodi Test', 'Referer': 'https://ref.invalid/a b'}}}}
        self.assertEqual('User-Agent=Kodi%20Test&Referer=https%3A%2F%2Fref.invalid%2Fa%20b', kodi_headers(stream))
        self.assertTrue(playable_url(stream).startswith('https://media.invalid/a|User-Agent='))

    def test_normalization_keeps_only_direct_urls_and_messages(self):
        result = normalize_streams([
            {'url': 'https://media.invalid/a'},
            {'name': 'No streams', 'description': 'Provider failed', 'streamData': {'type': 'error'}},
            {'externalUrl': 'https://example.invalid/project'},
        ])
        self.assertEqual(1, len(result['playable']))
        self.assertEqual(['No streams: Provider failed'], result['messages'])
        self.assertEqual(1, result['counts'][EXTERNAL_URL])

    def test_identifier_selection(self):
        self.assertEqual('tt123', canonical_meta_id({'id': 'tmdb:1', 'imdb_id': 'tt123'}))
        self.assertEqual('tt456', canonical_meta_id({'id': 'tmdb:2', 'imdbId': 'tt456'}))
        self.assertEqual('tmdb:1:1:1', canonical_episode_id({'id': 'tmdb:1:1:1'}, 'tt123', 1, 1))
        self.assertEqual('tt123:1:1', canonical_episode_id({}, 'tt123', 1, 1))
        meta = {'videos': [
            {'id': 'ignored', 'season': 1, 'episode': 2},
            {'id': 'canonical-episode-id', 'season': 1, 'episode': 1},
        ]}
        self.assertEqual('canonical-episode-id', matching_episode_id(meta, 'tt123', '1', '1'))
        self.assertEqual('tt123:2:3', matching_episode_id(meta, 'tt123', 2, 3))

    def test_display_and_quality_text_fallbacks(self):
        stream = {'description': 'Real Debrid 2160p', 'behaviorHints': {'filename': 'Movie.4K.mkv'}}
        self.assertEqual('Movie.4K.mkv', display_label(stream))
        self.assertIn('2160p', stream_search_text(stream))
        self.assertIn('Movie.4K.mkv', stream_search_text(stream))

    def test_structured_display_fields(self):
        stream = {
            'name': 'FHD',
            'behaviorHints': {'filename': 'Movie.2026.1080p.mkv'},
            'streamData': {
                'service': {'id': 'debridge', 'cached': True},
                'addon': 'Comet', 'size': 8 * 1024 ** 3, 'proxied': False,
                'library': False, 'indexer': 'ExampleIndexer',
                'parsedFile': {
                    'resolution': '1080p', 'quality': 'BluRay', 'encode': 'HEVC',
                    'visualTags': ['IMAX'], 'audioTags': ['DD'],
                    'audioChannels': ['5.1'], 'languages': ['English'],
                },
            },
        }
        fields = stream_display_fields(stream)
        self.assertEqual('1080p', fields['resolution'])
        self.assertEqual('debridge', fields['service'])
        self.assertEqual('Comet', fields['addon'])
        self.assertEqual('8.00 GB', fields['size'])
        self.assertEqual('YES', fields['cached'])
        self.assertEqual('', fields['duration'])
        self.assertEqual('BluRay | HEVC | IMAX', fields['video'])
        self.assertEqual('DD | 5.1 | English', fields['audio'])
        self.assertEqual('Movie.2026.1080p.mkv', fields['filename'])

    def test_missing_media_details_are_explicit(self):
        fields = stream_display_fields({'name': 'Direct stream', 'streamData': {}})
        self.assertEqual('Unknown', fields['resolution'])
        self.assertEqual('Unknown', fields['video'])
        self.assertEqual('Unknown', fields['audio'])


if __name__ == '__main__':
    unittest.main()
