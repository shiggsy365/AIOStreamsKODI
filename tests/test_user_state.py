import os
import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor


ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, 'plugin.video.aiostreams'))

from resources.lib.media import MediaRef  # noqa: E402
from resources.lib.user_state import UserState, UserStateError, favorite_key  # noqa: E402


class Clock:
    def __init__(self):
        self.value = 1000

    def __call__(self):
        self.value += 1
        return self.value


class UserStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = os.path.join(self.temporary_directory.name, 'user_state.db')
        self.clock = Clock()
        self.state = UserState(self.database_path, clock=self.clock)

    def tearDown(self):
        self.temporary_directory.cleanup()

    @staticmethod
    def movie(**overrides):
        values = {
            'id': 'catalog:movie:1', 'type': 'movie', 'stream_id': 'stream:movie:1',
            'imdb_id': 'tt1375666', 'tmdb_id': '27205', 'name': 'Inception',
            'year': '2010', 'poster': 'poster-a', 'background': 'fanart-a',
            'origin_fingerprint': 'configuration-a',
        }
        values.update(overrides)
        return MediaRef.from_meta(values, values.get('type'))

    def test_schema_migrates_from_an_unversioned_database(self):
        with sqlite3.connect(self.database_path) as connection:
            connection.execute('CREATE TABLE schema_version (version INTEGER NOT NULL)')
            connection.execute('INSERT INTO schema_version(version) VALUES (0)')

        self.assertTrue(self.state.record_search('Arrival', 'movies'))
        with sqlite3.connect(self.database_path) as connection:
            version = connection.execute('SELECT version FROM schema_version').fetchone()[0]
            tables = {
                row[0] for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }

        self.assertEqual(1, version)
        self.assertTrue({'search_history', 'preferences', 'favorites'}.issubset(tables))

    def test_search_history_persists_deduplicates_orders_and_applies_limit(self):
        self.state.record_search('  The   Last of Us ', 'shows')
        self.state.record_search('Arrival', 'movies')
        self.state.record_search('the last of us', 'shows')

        searches = self.state.list_searches()
        self.assertEqual(2, len(searches))
        self.assertEqual('the last of us', searches[0]['query'])
        self.assertEqual('shows', searches[0]['content_type'])

        limited = UserState(self.database_path, history_limit=2, clock=self.clock)
        limited.record_search('Dune', 'all')
        self.assertEqual(['Dune', 'the last of us'], [row['query'] for row in limited.list_searches()])

        restarted = UserState(self.database_path)
        self.assertEqual(['Dune', 'the last of us'], [row['query'] for row in restarted.list_searches()])
        self.assertTrue(restarted.remove_search('THE LAST OF US', 'shows'))
        self.assertFalse(restarted.remove_search('The Last of Us', 'shows'))
        restarted.clear_searches()
        self.assertEqual([], restarted.list_searches())

    def test_empty_queries_are_ignored_and_scope_is_persisted(self):
        self.assertFalse(self.state.record_search('   ', 'all'))
        self.assertEqual([], self.state.list_searches())
        self.assertEqual('all', self.state.get_last_search_scope())
        self.assertEqual('movies', self.state.set_last_search_scope('movie'))
        self.assertEqual('movies', UserState(self.database_path).get_last_search_scope())

    def test_favorite_key_prioritizes_imdb_then_tmdb_then_origin_and_metadata(self):
        self.assertEqual('movie:imdb:tt1375666', favorite_key(self.movie()))
        self.assertEqual(
            'movie:tmdb:27205',
            favorite_key(self.movie(imdb_id=None, id='meta:2')),
        )
        opaque = self.movie(imdb_id=None, tmdb_id=None, id='opaque:2')
        self.assertEqual('movie:origin:configuration-a:opaque:2', favorite_key(opaque))
        with self.assertRaisesRegex(ValueError, 'origin fingerprint'):
            favorite_key(self.movie(imdb_id=None, tmdb_id=None, origin_fingerprint=None))

    def test_favorites_deduplicate_refresh_and_survive_restart(self):
        original = self.movie()
        key = self.state.add_favorite(original)
        refreshed = self.movie(
            id='catalog:movie:updated', stream_id='stream:updated', name='Inception (Updated)',
            poster='poster-b', background='fanart-b',
        )
        self.assertEqual(key, self.state.add_favorite(refreshed))

        restarted = UserState(self.database_path)
        favorite = restarted.get_favorite(key)
        self.assertEqual('Inception (Updated)', favorite['title'])
        self.assertEqual('catalog:movie:updated', favorite['metadata_id'])
        self.assertEqual('stream:updated', favorite['playable_id'])
        self.assertTrue(restarted.is_favorite(refreshed))
        self.assertEqual([key], [row['favorite_key'] for row in restarted.list_favorites('movies')])
        self.assertTrue(restarted.remove_favorite(refreshed))
        self.assertFalse(restarted.is_favorite(key))

    def test_favorites_are_independent_from_search_history_and_preferences(self):
        key = self.state.add_favorite(self.movie())
        self.state.record_search('Inception', 'movies')
        self.state.set_last_search_scope('shows')

        self.state.clear_searches()
        self.assertIsNotNone(self.state.get_favorite(key))
        self.assertEqual('shows', self.state.get_last_search_scope())
        self.state.clear_favorites()
        self.assertEqual([], self.state.list_favorites())
        self.assertEqual('shows', self.state.get_last_search_scope())

    def test_two_instances_complete_concurrent_writes(self):
        first = UserState(self.database_path)
        second = UserState(self.database_path)

        def write(index):
            state = first if index % 2 else second
            self.assertTrue(state.record_search('Query {}'.format(index), 'all'))

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(write, range(16)))

        self.assertEqual(16, len(UserState(self.database_path).list_searches()))

    def test_corrupt_database_is_reported_without_replacing_it(self):
        with open(self.database_path, 'wb') as database:
            database.write(b'not a sqlite database')

        with self.assertRaisesRegex(UserStateError, 'local user-state database'):
            self.state.list_searches()
        with open(self.database_path, 'rb') as database:
            self.assertEqual(b'not a sqlite database', database.read())


if __name__ == '__main__':
    unittest.main()
