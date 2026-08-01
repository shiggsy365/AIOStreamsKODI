import sys
import traceback
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

# Import new modules with enhanced architecture
try:
    # Essential imports only
    from resources.lib import ui_helpers, settings_helpers, filters, cache, streams
    from resources.lib import plugin_runtime
    from resources.lib.plugin_args import parse_plugin_params
    from resources.lib.safe_logging import redact_identifier
    from resources.lib.items import (
        PresentationDependencies, apply_media_identity,
        create_listitem_with_context as present_media_list_item,
    )
    from resources.lib.globals import g
    from resources.lib.routing import dispatch
    from resources.lib.actions import search as search_actions
    from resources.lib.actions import browse as browse_actions
    from resources.lib.actions import maintenance as maintenance_actions
    from resources.lib.actions import playback as playback_actions
    from resources.lib.actions import trakt as trakt_actions

    from resources.lib.gui import show_source_select_dialog
    from resources.lib.clearlogo import clear_clearlogo_cache, get_cached_clearlogo_path
    HAS_MODULES = True
    HAS_NEW_MODULES = True
except Exception as e:
    HAS_MODULES = False
    HAS_NEW_MODULES = False
    xbmc.log(f'[AIOStreams] Failed to import modules: {e}', xbmc.LOGERROR)

# Initialize globals (new pattern)
if HAS_NEW_MODULES:
    try:
        g.init(sys.argv)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to initialize globals: {e}', xbmc.LOGERROR)

# Initialize addon (legacy compatibility)
ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])

plugin_runtime.configure(ADDON, HANDLE, HAS_MODULES)
get_player = plugin_runtime.get_player
get_setting = plugin_runtime.get_setting
get_base_url = plugin_runtime.get_base_url
get_aiostreams_client = plugin_runtime.get_aiostreams_client
get_all_catalogs_action = plugin_runtime.get_all_catalogs_action
get_folder_browser_catalogs_action = plugin_runtime.get_folder_browser_catalogs_action
get_timeout = plugin_runtime.get_timeout
get_url = plugin_runtime.get_url
get_manifest = plugin_runtime.get_manifest
search_catalog = plugin_runtime.search_catalog
get_streams = plugin_runtime.get_streams
show_no_playable_streams = plugin_runtime.show_no_playable_streams
get_catalog = plugin_runtime.get_catalog
get_subtitles = plugin_runtime.get_subtitles
filter_subtitles_by_language = plugin_runtime.filter_subtitles_by_language
download_subtitle_with_language = plugin_runtime.download_subtitle_with_language
format_date_with_ordinal = plugin_runtime.format_date_with_ordinal
get_meta = plugin_runtime.get_meta
_ensure_clearlogo_cached = plugin_runtime._ensure_clearlogo_cached
fetch_metadata_parallel = plugin_runtime.fetch_metadata_parallel

# Run initialize logic once per addon execution
# Run initialize logic once per addon execution - MOVED TO SERVICE.PY (Background)
# def initialize():
#     pass


_aiostreams_client = None
_aiostreams_client_config = None


# Clearlogo Helpers moved to resources/lib/clearlogo.py


def _presentation_dependencies():
    return PresentationDependencies(
        has_modules=HAS_MODULES,
        get_url=get_url,
        format_date=format_date_with_ordinal,
        get_cached_clearlogo_path=get_cached_clearlogo_path,
        ensure_clearlogo_cached=_ensure_clearlogo_cached,
        redact_identifier=redact_identifier,
    )


def create_listitem_with_context(meta, content_type, action_url):
    """Present one media item through the shared presenter."""
    return present_media_list_item(meta, content_type, action_url, _presentation_dependencies())


def _search_dependencies():
    """Build the small explicit dependency set used by search actions."""
    return search_actions.SearchDependencies(
        handle=HANDLE,
        has_modules=HAS_MODULES,
        filters=filters,
        search_catalog=search_catalog,
        get_url=get_url,
        create_listitem=create_listitem_with_context,
    )


def _playback_dependencies():
    """Build the explicit collaborator set used by playback actions."""
    return playback_actions.PlaybackDependencies(
        handle=HANDLE,
        has_modules=HAS_MODULES,
        get_setting=get_setting,
        get_meta=get_meta,
        get_streams=get_streams,
        get_subtitles=get_subtitles,
        filter_subtitles=filter_subtitles_by_language,
        download_subtitle=download_subtitle_with_language,
        show_no_playable_streams=show_no_playable_streams,
        get_player=get_player,
        get_stream_manager=streams.get_stream_manager,
        get_max_streams=settings_helpers.get_max_streams,
        show_source_dialog=show_source_select_dialog,
    )


def _browse_dependencies():
    """Build the explicit dependency set for catalog and menu actions."""
    return browse_actions.BrowseDependencies(
        handle=HANDLE,
        has_modules=HAS_MODULES,
        filters=filters,
        get_url=get_url,
        get_manifest=get_manifest,
        get_catalog=get_catalog,
        get_meta=get_meta,
        fetch_metadata_parallel=fetch_metadata_parallel,
        get_cached_clearlogo_path=get_cached_clearlogo_path,
        ensure_clearlogo_cached=_ensure_clearlogo_cached,
        format_season_title=ui_helpers.format_season_title,
        format_episode_title=ui_helpers.format_episode_title,
        apply_media_identity=apply_media_identity,
        create_listitem=create_listitem_with_context,
    )


def _invalidate_trakt_progress_cache():
    from resources.lib import trakt
    trakt.invalidate_progress_cache()


def _maintenance_dependencies():
    return maintenance_actions.MaintenanceDependencies(
        has_modules=HAS_MODULES,
        get_url=get_url,
        get_base_url=get_base_url,
        get_manifest=get_manifest,
        get_stream_manager=streams.get_stream_manager,
        get_client=get_aiostreams_client,
        cache=cache,
        clear_clearlogo_cache=clear_clearlogo_cache,
        invalidate_trakt_progress_cache=_invalidate_trakt_progress_cache,
        addon=ADDON,
        force_trakt_sync=_bind_action(trakt_actions.force_trakt_sync, _trakt_dependencies),
    )


def _trakt_dependencies():
    """Build the explicit collaborator set used by Trakt actions."""
    return trakt_actions.TraktDependencies(
        handle=HANDLE,
        has_modules=HAS_MODULES,
        get_setting=get_setting,
        get_url=get_url,
        get_streams=get_streams,
        fetch_metadata_parallel=fetch_metadata_parallel,
        create_listitem=create_listitem_with_context,
        format_date=format_date_with_ordinal,
        clear_trakt_widget_cache=browse_actions.clear_trakt_widget_cache,
    )


def _dispatch_registered_action(action, params):
    """Reuse the main route map for widget-originated actions."""
    handler = ACTION_REGISTRY.get(action)
    if handler is None:
        _log_unknown_action(action)
        return _default_action(params)
    return handler(params)


def _default_action(params):
    return browse_actions.index(params, _browse_dependencies())


def _bind_action(handler, dependency_factory):
    """Delay dependency construction until Kodi invokes an action."""
    def bound(params):
        return handler(params, dependency_factory())
    return bound


def _widget_dependencies():
    return browse_actions.WidgetDependencies(
        handle=HANDLE,
        has_modules=HAS_MODULES,
        get_url=get_url,
        get_catalog=get_catalog,
        get_meta=get_meta,
        create_listitem=create_listitem_with_context,
        dispatch_action=_dispatch_registered_action,
    )


def _info_dependencies():
    return browse_actions.InfoDependencies(
        get_meta=get_meta,
        get_url=get_url,
        create_listitem=create_listitem_with_context,
        clear_window_properties=ui_helpers.clear_window_properties,
    )


# Trakt functions


# Helper functions for Trakt actions


# Maintenance Tools


# Widget cache: {cache_key: {'data': catalog_data, 'timestamp': time.time()}}
_widget_cache = {}
_widget_cache_ttl = 3600  # 1 hour in seconds (increased from 15 minutes)


def open_youtube_folder(params):
    """Close search dialog and open YouTube folder in video window."""
    url = params.get('url', '')
    if url:
        xbmc.log('[AIOStreams] Opening YouTube folder', xbmc.LOGINFO)

        # Robustly close the custom search window (ID 1112)
        # We try multiple methods to ensure it's gone
        xbmc.executebuiltin('Dialog.Close(1112, true)')
        xbmc.executebuiltin('Window.Close(1112, true)')

        # Even more aggressive closure for window 1112
        xbmc.executebuiltin('Action(CloseDialog, 1112)')

        # Larger delay to let skin settle before switching windows
        xbmc.sleep(600)

        # Open the YouTube folder in the video window (without 'return' to see if it helps)
        xbmc.executebuiltin(f'ActivateWindow(Videos, "{url}")')


# ============================================================================
# Action Registry - Cleaner routing using dictionary pattern
# ============================================================================

# Action handler registry - maps action names to handler functions


ACTION_REGISTRY = {
    # Index/Home
    'index': _default_action,
    'search': _bind_action(search_actions.search, _search_dependencies),
    'search_tab': _bind_action(search_actions.search, _search_dependencies),
    'info': _bind_action(browse_actions.action_info, _info_dependencies),
    'clear_cache': _bind_action(maintenance_actions.clear_cache, _maintenance_dependencies),

    # Browse actions
    'movie_lists': _bind_action(browse_actions.movie_lists, _browse_dependencies),
    'series_lists': _bind_action(browse_actions.series_lists, _browse_dependencies),
    'catalogs': _bind_action(browse_actions.list_catalogs, _browse_dependencies),
    'smart_widget': _bind_action(browse_actions.smart_widget, _widget_dependencies),
    'configured_widget': _bind_action(browse_actions.configured_widget, _widget_dependencies),
    'catalog_genres': _bind_action(browse_actions.list_catalog_genres, _browse_dependencies),
    'browse_catalog': _bind_action(browse_actions.browse_catalog, _browse_dependencies),

    # TV Show navigation
    'show_seasons': _bind_action(browse_actions.show_seasons, _browse_dependencies),
    'browse_show': _bind_action(browse_actions.browse_show, _browse_dependencies),
    'show_episodes': _bind_action(browse_actions.show_episodes, _browse_dependencies),
    'show_related': _bind_action(browse_actions.show_related, _browse_dependencies),
    'update_container': _bind_action(browse_actions.update_container, _browse_dependencies),

    # Trakt menu actions
    'trakt_menu': _bind_action(trakt_actions.trakt_menu, _trakt_dependencies),
    'trakt_watchlist': _bind_action(trakt_actions.trakt_watchlist, _trakt_dependencies),
    'trakt_next_up': _bind_action(trakt_actions.trakt_next_up, _trakt_dependencies),

    # Trakt authentication
    'trakt_auth': _bind_action(trakt_actions.trakt_auth, _trakt_dependencies),
    'trakt_revoke': _bind_action(trakt_actions.trakt_revoke, _trakt_dependencies),

    # Trakt item actions
    'trakt_add_watchlist': _bind_action(trakt_actions.trakt_add_watchlist, _trakt_dependencies),
    'trakt_remove_watchlist': _bind_action(trakt_actions.trakt_remove_watchlist, _trakt_dependencies),
    'trakt_mark_watched': _bind_action(trakt_actions.trakt_mark_watched, _trakt_dependencies),
    'trakt_mark_unwatched': _bind_action(trakt_actions.trakt_mark_unwatched, _trakt_dependencies),
    'trakt_remove_playback': _bind_action(trakt_actions.trakt_remove_playback, _trakt_dependencies),
    'trakt_hide_show': _bind_action(trakt_actions.trakt_hide_show, _trakt_dependencies),
    'trakt_hide_from_progress': _bind_action(trakt_actions.trakt_hide_from_progress, _trakt_dependencies),
    'trakt_unhide_from_progress': _bind_action(trakt_actions.trakt_unhide_from_progress, _trakt_dependencies),

    # Settings/maintenance actions
    'clear_stream_stats': _bind_action(maintenance_actions.clear_stream_stats, _maintenance_dependencies),
    'clear_preferences': _bind_action(maintenance_actions.clear_preferences, _maintenance_dependencies),
    'database_reset': _bind_action(maintenance_actions.database_reset, _maintenance_dependencies),
    'clear_trakt_cache': _bind_action(maintenance_actions.clear_trakt_cache, _maintenance_dependencies),
    'show_database_info': _bind_action(maintenance_actions.show_database_info, _maintenance_dependencies),
    'optimize_database': _bind_action(maintenance_actions.optimize_database, _maintenance_dependencies),
    'test_connection': _bind_action(maintenance_actions.test_connection, _maintenance_dependencies),
    'quick_actions': _bind_action(maintenance_actions.quick_actions, _maintenance_dependencies),
    'configure_aiostreams': _bind_action(maintenance_actions.configure_aiostreams, _maintenance_dependencies),
    'retrieve_manifest': _bind_action(maintenance_actions.retrieve_manifest, _maintenance_dependencies),
    'refresh_manifest_cache': _bind_action(maintenance_actions.refresh_manifest_cache, _maintenance_dependencies),
    'get_all_catalogs': get_all_catalogs_action,
    'get_folder_browser_catalogs': get_folder_browser_catalogs_action,
    'open_youtube_folder': open_youtube_folder,
    'youtube_menu': _bind_action(browse_actions.youtube_menu, _browse_dependencies),

    # Playback actions
    'play': _bind_action(playback_actions.play, _playback_dependencies),
    'play_next': _bind_action(playback_actions.play_next, _playback_dependencies),
    'play_next_source': _bind_action(playback_actions.play_next_source, _playback_dependencies),
    'play_first': _bind_action(playback_actions.play_first, _playback_dependencies),
    'select_stream': _bind_action(playback_actions.select_stream, _playback_dependencies),
    'show_streams': _bind_action(playback_actions.show_streams, _playback_dependencies),
}




def router(params):
    """Dispatch a parsed plugin request through the single route table."""
    return dispatch(
        params,
        ACTION_REGISTRY,
        _default_action,
        on_unknown=_log_unknown_action,
        on_error=_log_action_error,
    )


def _log_unknown_action(action):
    xbmc.log(f'[AIOStreams] Unknown action: {action}', xbmc.LOGWARNING)


def _log_action_error(action, error):
    action_name = action or 'index'
    xbmc.log(
        f'[AIOStreams] Action error ({action_name}): {error}\n{traceback.format_exc()}',
        xbmc.LOGERROR,
    )
    xbmcgui.Dialog().notification(
        'AIOStreams', f'Unable to open {action_name}: {type(error).__name__}',
        xbmcgui.NOTIFICATION_ERROR,
    )
    xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == '__main__':
    xbmc.log(f'[AIOStreams] ===== PLUGIN INVOKED =====', xbmc.LOGDEBUG)

    arg_raw = sys.argv[2]
    params = parse_plugin_params(arg_raw)
    if '/' in arg_raw and not arg_raw.startswith('?'):
        xbmc.log('[AIOStreams] Clean path parsed', xbmc.LOGDEBUG)

    xbmc.log('[AIOStreams] Plugin parameters parsed', xbmc.LOGDEBUG)
    xbmc.log(f'[AIOStreams] Action: {params.get("action", "<none>")}', xbmc.LOGDEBUG)
    router(params)
    xbmc.log(f'[AIOStreams] ===== PLUGIN EXECUTION COMPLETE =====', xbmc.LOGDEBUG)

    # Cleanup on exit if using new modules
    if HAS_NEW_MODULES:
        try:
            g.deinit()
        except:
            pass
