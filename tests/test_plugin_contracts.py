import ast
import os
import sys
import unittest
from collections import Counter
from pathlib import Path

from kodi_stubs import install


ROOT = os.path.dirname(os.path.dirname(__file__))
ADDON_ROOT = os.path.join(ROOT, 'plugin.video.aiostreams')
sys.path.insert(0, ADDON_ROOT)

from resources.lib.plugin_args import parse_plugin_params  # noqa: E402


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


class PluginRouteTests(unittest.TestCase):
    def test_current_route_names_are_characterized(self):
        keys = action_registry_keys()
        self.assertTrue({
            'search', 'browse_catalog', 'show_seasons', 'show_episodes',
            'play', 'play_first', 'select_stream', 'show_streams',
            'trakt_watchlist', 'trakt_next_up', 'refresh_manifest_cache',
        }.issubset(keys))
        self.assertEqual(2, Counter(keys)['info'])

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
