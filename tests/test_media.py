import os
import sys
import unittest


ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'plugin.video.aiostreams'))

from resources.lib.items import media_action_params, plugin_url  # noqa: E402
from resources.lib.media import MediaRef, normalize_content_type  # noqa: E402
from kodi_stubs import install  # noqa: E402


class MediaRefTests(unittest.TestCase):
    def test_normalizes_movie_ids_without_conflating_opaque_metadata_id_with_imdb(self):
        media = MediaRef.from_meta({
            'id': 'aiometadata:movie:42', 'imdb_id': 'tt1375666', 'tmdb_id': '27205',
            'name': 'Inception', 'year': '2010-07-16', 'poster': 'poster', 'background': 'fanart',
        }, 'movies', 'backend-a')

        self.assertEqual('movie', media.content_type)
        self.assertEqual('aiometadata:movie:42', media.navigation_id)
        self.assertEqual('tt1375666', media.imdb_id)
        self.assertEqual('27205', media.tmdb_id)
        self.assertEqual('tt1375666', media.playback_id)
        self.assertEqual(2010, media.year)
        self.assertEqual('backend-a', media.origin_fingerprint)

    def test_catalog_only_reference_uses_its_metadata_id_only_as_a_last_playback_fallback(self):
        media = MediaRef.from_meta({'id': 'catalog:opaque:42', 'type': 'series', 'name': 'Example'})

        self.assertEqual('series', media.content_type)
        self.assertIsNone(media.imdb_id)
        self.assertIsNone(media.tmdb_id)
        self.assertEqual('catalog:opaque:42', media.playback_id)

    def test_nested_ids_and_explicit_playable_id_are_preserved(self):
        media = MediaRef.from_meta({
            'id': 'meta:7', 'ids': {'imdb': 'tt7654321', 'tmdb': 99}, 'stream_id': 'stream:7',
        }, 'tvshows')

        self.assertEqual('series', media.content_type)
        self.assertEqual('tt7654321', media.imdb_id)
        self.assertEqual('99', media.tmdb_id)
        self.assertEqual('stream:7', media.playback_id)

    def test_episode_reference_preserves_exact_video_id(self):
        show = MediaRef.from_meta({'id': 'tt0944947', 'name': 'Game of Thrones'}, 'series')
        episode = MediaRef.episode(show, {'id': 'tt0944947:1:1', 'title': 'Winter Is Coming'}, 1, 1)

        self.assertEqual('episode', episode.content_type)
        self.assertEqual('tt0944947:1:1', episode.metadata_id)
        self.assertEqual('tt0944947:1:1', episode.playback_id)
        self.assertIsNone(episode.imdb_id)
        self.assertEqual('Winter Is Coming', episode.title)

    def test_action_parameters_use_navigation_and_playback_fields_explicitly(self):
        media = MediaRef.from_meta({'id': 'meta:1', 'imdb_id': 'tt1', 'name': 'Title'}, 'movie')

        self.assertEqual({'meta_id': 'meta:1', 'title': 'Title'}, media_action_params('show_seasons', media))
        self.assertEqual(
            {'content_type': 'movie', 'imdb_id': 'tt1', 'title': 'Title'},
            media_action_params('play', media),
        )

    def test_content_type_aliases(self):
        self.assertEqual('movie', normalize_content_type('movies'))
        self.assertEqual('series', normalize_content_type('tvshow'))
        self.assertEqual('episode', normalize_content_type('episode'))

    def test_plugin_url_does_not_depend_on_the_global_search_script_path(self):
        self.assertEqual(
            'plugin://plugin.video.aiostreams/?action=play&imdb_id=tt1375666',
            plugin_url('play', imdb_id='tt1375666'),
        )

    def test_presenter_exposes_normalized_identity_to_kodi_skins(self):
        install()
        from resources.lib.items import create_media_list_item

        meta = {'id': 'opaque:9', 'imdb_id': 'tt9', 'tmdb_id': '19', 'name': 'Example'}
        list_item, info_tag = create_media_list_item(meta, MediaRef.from_meta(meta, 'movie'))

        self.assertEqual('Example', list_item.label)
        self.assertEqual('opaque:9', list_item.properties['meta_id'])
        self.assertEqual('tt9', list_item.properties['imdb_id'])
        self.assertEqual('19', list_item.properties['tmdb_id'])
        self.assertEqual('Example', info_tag.values['Title'])


if __name__ == '__main__':
    unittest.main()
