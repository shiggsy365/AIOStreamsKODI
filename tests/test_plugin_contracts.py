import ast
import os
import sys
import unittest
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

from kodi_stubs import install


ROOT = os.path.dirname(os.path.dirname(__file__))
ADDON_ROOT = os.path.join(ROOT, 'plugin.video.aiostreams')
sys.path.insert(0, ADDON_ROOT)

from resources.lib.plugin_args import parse_plugin_params, parse_search_query  # noqa: E402


def action_registry_keys():
    source_path = os.path.join(ADDON_ROOT, 'addon.py')
    tree = ast.parse(Path(source_path).read_text(encoding='utf-8'), filename=source_path)
    assignment = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'ACTION_REGISTRY'
                for target in node.targets)
    )
    return [key.value for key in assignment.value.keys if isinstance(key, ast.Constant)]


def function_names():
    source_path = os.path.join(ADDON_ROOT, 'addon.py')
    tree = ast.parse(Path(source_path).read_text(encoding='utf-8'), filename=source_path)
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}


def registered_handler_names():
    source_path = os.path.join(ADDON_ROOT, 'addon.py')
    tree = ast.parse(Path(source_path).read_text(encoding='utf-8'), filename=source_path)
    assignment = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'ACTION_REGISTRY'
                for target in node.targets)
    )
    return {
        value.body.func.id
        for value in assignment.value.values
        if isinstance(value, ast.Lambda)
        and isinstance(value.body, ast.Call)
        and isinstance(value.body.func, ast.Name)
    }


class PluginParameterTests(unittest.TestCase):
    def test_query_string_parameters_are_decoded(self):
        self.assertEqual(
            {'action': 'search', 'query': 'The Last of Us'},
            parse_plugin_params('?action=search&query=The+Last+of+Us'),
        )

    def test_clean_path_parameters_are_mapped(self):
        self.assertEqual(
            {'action': 'show_episodes', 'meta_id': 'tt0944947', 'season': '1'},
            parse_plugin_params('/show_episodes/tt0944947/1'),
        )
        self.assertEqual(
            {'action': 'play', 'meta_id': 'tt1375666'},
            parse_plugin_params('/play/tt1375666'),
        )

    def test_empty_or_non_navigation_arguments_are_empty(self):
        self.assertEqual({}, parse_plugin_params(''))
        self.assertEqual({}, parse_plugin_params('not-a-plugin-route'))

    def test_global_search_query_arguments_support_query_variants_and_positional_terms(self):
        self.assertEqual('The Last of Us', parse_search_query(['?query=The+Last+of+Us']))
        self.assertEqual('The Last of Us', parse_search_query(['?search=The+Last+of+Us']))
        self.assertEqual('The Last of Us', parse_search_query(['The+Last+of+Us']))
        self.assertEqual('', parse_search_query(['?action=search']))


class PluginRouteTests(unittest.TestCase):
    def test_current_route_names_are_characterized(self):
        keys = action_registry_keys()
        self.assertTrue({
            'search', 'browse_catalog', 'show_seasons', 'show_episodes',
            'play', 'play_first', 'select_stream', 'show_streams',
            'trakt_watchlist', 'trakt_next_up', 'refresh_manifest_cache',
        }.issubset(keys))
        self.assertEqual(1, Counter(keys)['info'])
        self.assertNotIn('trakt_collection', keys)
        self.assertNotIn('trakt_recommendations', keys)

    def test_metadata_uses_only_the_configured_backend(self):
        source = Path(os.path.join(ADDON_ROOT, 'addon.py')).read_text(encoding='utf-8')
        get_meta_source = source[source.index('def get_meta('):source.index('def _ensure_clearlogo_cached(')]

        self.assertNotIn('master_token', get_meta_source)
        self.assertNotIn('aiostreams.shiggsy.co.uk', get_meta_source)

    def test_next_source_route_has_an_implementation(self):
        self.assertIn('play_next_source', function_names())

    def test_registered_handlers_are_defined(self):
        self.assertTrue(registered_handler_names().issubset(function_names()))


class SettingsContractTests(unittest.TestCase):
    def test_settings_are_unique_and_include_all_genre_filter_controls(self):
        settings_path = os.path.join(ADDON_ROOT, 'resources', 'settings.xml')
        settings = [node.attrib['id'] for node in ET.parse(settings_path).iter('setting')]

        self.assertEqual(len(settings), len(set(settings)))
        self.assertIn('filter_genres_enabled', settings)
        for genre in (
            'action', 'adventure', 'animation', 'anime', 'comedy', 'crime',
            'documentary', 'drama', 'family', 'fantasy', 'history', 'horror',
            'music', 'mystery', 'romance', 'science_fiction', 'thriller', 'war', 'western',
        ):
            self.assertIn(f'filter_genre_{genre}', settings)

    def test_action_registry_dispatches_with_kodi_stubs(self):
        install()
        from resources.lib.router import ActionRegistry

        seen = []
        registry = ActionRegistry()
        registry.register('test', lambda params: seen.append(params) or 'ok')

        self.assertEqual('ok', registry.dispatch({'action': 'test'}))
        self.assertEqual([{'action': 'test'}], seen)


if __name__ == '__main__':
    unittest.main()
