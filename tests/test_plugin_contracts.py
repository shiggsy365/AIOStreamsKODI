import ast
import importlib
import os
import sys
import types
import unittest
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

from kodi_stubs import install

ROOT = os.path.dirname(os.path.dirname(__file__))
ADDON_ROOT = os.path.join(ROOT, 'plugin.video.aiostreams')
sys.path.insert(0, ADDON_ROOT)

from resources.lib.plugin_args import parse_plugin_params, parse_search_query  # noqa: E402
from resources.lib.routing import dispatch, normalize_params  # noqa: E402


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


def action_registry_values():
    source_path = os.path.join(ADDON_ROOT, 'addon.py')
    tree = ast.parse(Path(source_path).read_text(encoding='utf-8'), filename=source_path)
    assignment = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'ACTION_REGISTRY'
                for target in node.targets)
    )
    return assignment.value.values


def addon_function_names():
    source_path = os.path.join(ADDON_ROOT, 'addon.py')
    tree = ast.parse(Path(source_path).read_text(encoding='utf-8'), filename=source_path)
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}


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
            'play', 'play_first', 'select_stream',
            'trakt_watchlist', 'trakt_next_up', 'refresh_manifest_cache',
        }.issubset(keys))
        self.assertEqual(1, Counter(keys)['info'])
        self.assertNotIn('trakt_collection', keys)
        self.assertNotIn('trakt_recommendations', keys)
        self.assertNotIn('show_streams', keys)

    def test_metadata_uses_only_the_configured_backend(self):
        source = Path(os.path.join(ADDON_ROOT, 'resources', 'lib', 'plugin_runtime.py')).read_text(encoding='utf-8')
        get_meta_source = source[source.index('def get_meta('):source.index('def _ensure_clearlogo_cached(')]

        self.assertNotIn('master_token', get_meta_source)
        self.assertNotIn('aiostreams.shiggsy.co.uk', get_meta_source)

    def test_next_source_route_has_an_implementation(self):
        install()
        from resources.lib.actions import playback

        self.assertTrue(callable(playback.play_next_source))

    def test_route_table_has_no_lambdas_and_all_action_modules_import(self):
        install()
        from resources.lib import plugin_runtime
        from resources.lib.actions import browse, maintenance, playback, search, trakt

        modules = {
            'browse_actions': browse,
            'maintenance_actions': maintenance,
            'playback_actions': playback,
            'search_actions': search,
            'trakt_actions': trakt,
        }
        for module in modules.values():
            self.assertTrue(module.__name__.startswith('resources.lib.actions.'))
        self.assertTrue(callable(plugin_runtime.get_manifest))
        self.assertTrue(callable(plugin_runtime.get_meta))
        for value in action_registry_values():
            self.assertNotIsInstance(value, ast.Lambda)
            if isinstance(value, ast.Name):
                source = Path(os.path.join(ADDON_ROOT, 'addon.py')).read_text(encoding='utf-8')
                self.assertTrue(
                    value.id in addon_function_names() or f'{value.id} = plugin_runtime.' in source,
                    value.id,
                )
                continue
            self.assertIsInstance(value, ast.Call)
            self.assertIsInstance(value.func, ast.Name)
            self.assertIn(value.func.id, {'partial', '_bind_action'})
            target = value.args[0]
            self.assertIsInstance(target, ast.Attribute)
            self.assertIsInstance(target.value, ast.Name)
            self.assertTrue(callable(getattr(modules[target.value.id], target.attr)))

    def test_addon_import_constructs_a_callable_route_table(self):
        install()
        xbmcplugin = sys.modules['xbmcplugin']
        xbmcplugin.setPluginCategory = lambda *_args: None
        xbmcplugin.setContent = lambda *_args: None
        directory_items = []
        xbmcplugin.addDirectoryItem = lambda *args: directory_items.append(args)
        xbmcplugin.endOfDirectory = lambda *_args, **_kwargs: None
        original_argv = sys.argv[:]
        overrides = {
            'resources.lib.globals': types.ModuleType('resources.lib.globals'),
            'resources.lib.gui': types.ModuleType('resources.lib.gui'),
            'resources.lib.clearlogo': types.ModuleType('resources.lib.clearlogo'),
        }
        overrides['resources.lib.globals'].g = types.SimpleNamespace(
            init=lambda _args: None, deinit=lambda: None,
        )
        overrides['resources.lib.gui'].show_source_select_dialog = lambda **_kwargs: (-1, None)
        overrides['resources.lib.clearlogo'].clear_clearlogo_cache = lambda: True
        overrides['resources.lib.clearlogo'].get_cached_clearlogo_path = lambda *_args: None
        overrides['resources.lib.clearlogo'].download_and_cache_clearlogo = lambda *_args: None

        previous_modules = {name: sys.modules.get(name) for name in overrides}
        try:
            sys.modules.update(overrides)
            sys.modules.pop('addon', None)
            sys.argv = ['plugin://plugin.video.aiostreams/', '1', '?action=index']
            addon = importlib.import_module('addon')
            self.assertTrue(addon.ACTION_REGISTRY)
            self.assertTrue(all(callable(handler) for handler in addon.ACTION_REGISTRY.values()))
            addon.router({})
            self.assertEqual(5, len(directory_items))
        finally:
            sys.argv = original_argv
            sys.modules.pop('addon', None)
            for name, module in previous_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

    def test_route_table_import_survives_global_initialization_failure(self):
        install()
        original_argv = sys.argv[:]
        globals_module = types.ModuleType('resources.lib.globals')
        globals_module.g = types.SimpleNamespace(
            init=lambda _args: (_ for _ in ()).throw(RuntimeError('stub failure')),
            deinit=lambda: None,
        )
        gui_module = types.ModuleType('resources.lib.gui')
        gui_module.show_source_select_dialog = lambda **_kwargs: (-1, None)
        clearlogo_module = types.ModuleType('resources.lib.clearlogo')
        clearlogo_module.clear_clearlogo_cache = lambda: True
        clearlogo_module.get_cached_clearlogo_path = lambda *_args: None
        clearlogo_module.download_and_cache_clearlogo = lambda *_args: None
        overrides = {
            'resources.lib.globals': globals_module,
            'resources.lib.gui': gui_module,
            'resources.lib.clearlogo': clearlogo_module,
        }
        previous_modules = {name: sys.modules.get(name) for name in overrides}
        try:
            sys.modules.update(overrides)
            sys.modules.pop('addon', None)
            sys.argv = ['plugin://plugin.video.aiostreams/', '1', '?action=index']
            addon = importlib.import_module('addon')
            self.assertTrue(all(callable(handler) for handler in addon.ACTION_REGISTRY.values()))
        finally:
            sys.argv = original_argv
            sys.modules.pop('addon', None)
            for name, module in previous_modules.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

    def test_extracted_action_modules_do_not_reread_kodi_invocation_arguments(self):
        actions_dir = Path(os.path.join(ADDON_ROOT, 'resources', 'lib', 'actions'))
        for source_path in actions_dir.glob('*.py'):
            self.assertNotIn('sys.argv', source_path.read_text(encoding='utf-8'))

    def test_presenter_has_no_direct_trakt_persistence_dependency(self):
        source = Path(os.path.join(ADDON_ROOT, 'resources', 'lib', 'items.py')).read_text(encoding='utf-8')
        self.assertNotIn('from resources.lib import trakt', source)
        self.assertNotIn('get_trakt_db(', source)

    def test_manifest_retrieval_uses_http_basic_authentication(self):
        install()
        from resources.lib.web_config import _api_host_url, _retrieve_user_response

        calls = []
        response = _retrieve_user_response(
            lambda *args, **kwargs: calls.append((args, kwargs)) or 'response',
            'https://example.invalid/', 'user-uuid', 'password', timeout=12,
        )

        self.assertEqual('response', response)
        self.assertEqual(
            (
                ('https://example.invalid/api/v1/user',),
                {'auth': ('user-uuid', 'password'), 'timeout': 12, 'allow_redirects': False},
            ),
            calls[0],
        )
        self.assertEqual('https://example.invalid', _api_host_url('https://example.invalid/stremio/id/token/manifest.json'))
        self.assertEqual('https://example.invalid', _api_host_url('https://example.invalid/stremio/configure'))


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

    def test_dispatch_normalizes_search_aliases_and_calls_routes(self):
        seen = []
        result = dispatch(
            {'q': 'The Last of Us'},
            {'search': lambda params: seen.append(params) or 'ok'},
            lambda params: 'default',
        )

        self.assertEqual('ok', result)
        self.assertEqual([{'q': 'The Last of Us', 'action': 'search', 'query': 'The Last of Us'}], seen)

    def test_dispatch_uses_default_and_reports_unknown_or_failed_actions(self):
        events = []
        self.assertEqual(
            'default',
            dispatch(
                {'action': 'missing'}, {}, lambda params: 'default',
                on_unknown=events.append,
            ),
        )
        self.assertEqual(['missing'], events)

        self.assertIsNone(
            dispatch(
                {'action': 'broken'}, {'broken': lambda params: 1 / 0}, lambda params: 'default',
                on_error=lambda action, error: events.append((action, type(error).__name__)),
            )
        )
        self.assertEqual(('broken', 'ZeroDivisionError'), events[-1])

    def test_normalize_params_does_not_override_an_explicit_action_or_query(self):
        self.assertEqual(
            {'action': 'browse_catalog', 'query': 'Existing', 'q': 'Ignored'},
            normalize_params({'action': 'browse_catalog', 'query': 'Existing', 'q': 'Ignored'}),
        )


if __name__ == '__main__':
    unittest.main()
