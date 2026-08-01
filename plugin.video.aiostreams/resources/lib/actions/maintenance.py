"""Maintenance and configuration actions with explicit dependencies."""
from dataclasses import dataclass
import time

import xbmc
import xbmcgui


@dataclass(frozen=True)
class MaintenanceDependencies:
    has_modules: bool
    get_url: object
    get_base_url: object
    get_manifest: object
    get_stream_manager: object
    get_client: object
    cache: object
    clear_clearlogo_cache: object
    invalidate_trakt_progress_cache: object
    addon: object
    force_trakt_sync: object


def quick_actions(params, dependencies):
    """Show the context-independent quick action picker."""
    from resources.lib import trakt

    content_type = params.get('content_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    title = params.get('title', 'Unknown')
    poster = params.get('poster', '')
    fanart = params.get('fanart', '')
    clearlogo = params.get('clearlogo', '')
    if not imdb_id:
        xbmcgui.Dialog().notification('AIOStreams', 'No content selected', xbmcgui.NOTIFICATION_ERROR)
        return None

    selected = xbmcgui.Dialog().select(f'Quick Actions: {title}', [
        'Add to Watchlist (Q)', 'Mark as Watched (W)', 'Show Info (I)',
        'Similar Content (S)', 'Play (Enter)',
    ])
    if selected == 0 and dependencies.has_modules:
        trakt.add_to_watchlist(content_type, imdb_id)
        xbmc.executebuiltin('Container.Refresh')
    elif selected == 1 and dependencies.has_modules:
        trakt.mark_watched(content_type, imdb_id)
        xbmc.executebuiltin('Container.Refresh')
    elif selected == 2:
        xbmc.executebuiltin('Action(Info)')
    elif selected == 3:
        xbmc.executebuiltin(
            f'Container.Update({dependencies.get_url(action="show_related", content_type=content_type, imdb_id=imdb_id, title=title)})'
        )
    elif selected == 4:
        if content_type == 'movie':
            xbmc.executebuiltin(
                f'RunPlugin({dependencies.get_url(action="show_streams", content_type="movie", media_id=imdb_id, title=title, poster=poster, fanart=fanart, clearlogo=clearlogo)})'
            )
        else:
            xbmc.executebuiltin(
                f'Container.Update({dependencies.get_url(action="show_seasons", meta_id=imdb_id)})'
            )
    return None


def test_connection(params, dependencies):
    """Test the configured AIOStreams endpoint."""
    base_url = dependencies.get_base_url()
    if not base_url:
        xbmcgui.Dialog().ok('AIOStreams', 'Please set AIOStreams Base URL in settings first')
        return None
    try:
        started = time.time()
        manifest = dependencies.get_manifest()
        elapsed = time.time() - started
        if manifest:
            xbmcgui.Dialog().ok(
                'AIOStreams Connection Test',
                f'✓ Connection successful!\n\nServer: {base_url}\nResponse time: {elapsed:.2f}s\nCatalogs available: {len(manifest.get("catalogs", []))}',
            )
        else:
            xbmcgui.Dialog().ok(
                'AIOStreams Connection Test',
                f'✗ Connection failed\n\nServer: {base_url}\nPlease check your settings and try again.',
            )
    except Exception as error:
        xbmc.log(f'[AIOStreams] Connection test failed: {type(error).__name__}', xbmc.LOGERROR)
        xbmcgui.Dialog().ok(
            'AIOStreams Connection Test',
            f'✗ Connection failed\n\nError: {error}\n\nPlease check your settings and try again.',
        )
    return None


def configure_aiostreams(params, dependencies):
    """Open AIOStreams configuration and capture a manifest URL."""
    _run_web_config_action('configure_aiostreams', 'Configuration', 'Configuration completed successfully')


def retrieve_manifest(params, dependencies):
    """Retrieve a manifest URL using UUID/password authentication."""
    _run_web_config_action('retrieve_manifest', 'Retrieve manifest', 'Manifest retrieved successfully')


def clear_stream_stats(params, dependencies):
    """Clear learned stream reliability statistics."""
    if not dependencies.has_modules:
        return None
    try:
        dependencies.get_stream_manager().clear_stats()
        xbmcgui.Dialog().notification('AIOStreams', 'Stream statistics cleared', xbmcgui.NOTIFICATION_INFO)
    except Exception as error:
        xbmc.log(f'[AIOStreams] Failed to clear stream stats: {error}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to clear statistics', xbmcgui.NOTIFICATION_ERROR)
    return None


def clear_preferences(params, dependencies):
    """Clear learned stream preferences."""
    if not dependencies.has_modules:
        return None
    try:
        dependencies.get_stream_manager().clear_preferences()
        xbmcgui.Dialog().notification('AIOStreams', 'Preferences cleared', xbmcgui.NOTIFICATION_INFO)
    except Exception as error:
        xbmc.log(f'[AIOStreams] Failed to clear preferences: {error}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to clear preferences', xbmcgui.NOTIFICATION_ERROR)
    return None


def refresh_manifest_cache(params, dependencies):
    """Invalidate configuration-scoped manifest and catalog caches, then refetch."""
    if not dependencies.has_modules:
        xbmcgui.Dialog().notification('AIOStreams', 'Modules not available', xbmcgui.NOTIFICATION_ERROR)
        return None
    try:
        if not dependencies.get_base_url():
            xbmcgui.Dialog().notification('AIOStreams', 'No manifest URL configured', xbmcgui.NOTIFICATION_ERROR)
            return None
        client = dependencies.get_client()
        cache_key = client.cache_key('manifest')
        cache_instance = dependencies.cache.get_cache()
        xbmc.log(f'[AIOStreams] Invalidating manifest cache for key: {cache_key}', xbmc.LOGINFO)
        cache_instance.invalidate('manifest', cache_key)
        cache_instance.invalidate_type('catalog')
        cache_instance.invalidate_type('search')
        cache_instance.invalidate('http_headers', client.cache_key('http_headers', 'manifest', cache_key))
        cache_instance.cleanup_expired(force_all=False)
        manifest = dependencies.get_manifest(force=True)
        if manifest:
            xbmcgui.Dialog().notification('AIOStreams', 'Manifest cache refreshed successfully', xbmcgui.NOTIFICATION_INFO, 3000)
            xbmc.log(f'[AIOStreams] Manifest refreshed, catalogs: {len(manifest.get("catalogs", []))}', xbmc.LOGINFO)
        else:
            xbmcgui.Dialog().notification('AIOStreams', 'Failed to fetch manifest from server', xbmcgui.NOTIFICATION_ERROR)
    except Exception as error:
        xbmc.log(f'[AIOStreams] Failed to refresh manifest cache: {error}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', f'Failed to refresh: {error}', xbmcgui.NOTIFICATION_ERROR)
    return None


def clear_cache(params, dependencies):
    """Clear in-memory, file, Trakt, artwork, and stream-learning caches."""
    if not dependencies.has_modules:
        return None
    try:
        xbmc.log('[AIOStreams] Starting cache clear operation', xbmc.LOGINFO)
        cache_instance = dependencies.cache.get_cache()
        cache_instance.clear_memory()
        cache_instance.cleanup_expired(force_all=True)
        dependencies.invalidate_trakt_progress_cache()
        dependencies.clear_clearlogo_cache()
        try:
            manager = dependencies.get_stream_manager()
            manager.clear_stats()
            manager.clear_preferences()
        except Exception as error:
            xbmc.log(f'[AIOStreams] Error clearing stream data: {error}', xbmc.LOGWARNING)
        xbmcgui.Dialog().notification('AIOStreams', 'All caches cleared successfully', xbmcgui.NOTIFICATION_INFO)
    except Exception as error:
        xbmc.log(f'[AIOStreams] Failed to clear cache: {error}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to clear cache', xbmcgui.NOTIFICATION_ERROR)
    return None


def clear_trakt_cache(params, dependencies):
    """Clear local Trakt sync data and force a fresh activities sync."""
    if not dependencies.has_modules:
        return None
    if not xbmcgui.Dialog().yesno(
        'Clear Trakt Sync',
        'This will clear all local Trakt data and force a full re-sync.\n'
        'Use this if watched status or "Next Up" is incorrect.\n\nAre you sure?',
    ):
        return None
    try:
        from resources.lib.database.trakt_sync.activities import TraktSyncDatabase

        database = TraktSyncDatabase()
        if database.clear_all_trakt_data():
            xbmcgui.Dialog().notification('Trakt Reset', 'Trakt database cleared. Syncing...', xbmcgui.NOTIFICATION_INFO)
            database.sync_activities(force=True)
        else:
            xbmcgui.Dialog().notification('Trakt Reset', 'Failed to clear Trakt data', xbmcgui.NOTIFICATION_ERROR)
    except Exception as error:
        xbmc.log(f'[AIOStreams] Error in clear_trakt_cache: {error}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('Error', str(error), xbmcgui.NOTIFICATION_ERROR)
    return None


def show_database_info(params, dependencies):
    """Display local Trakt and stream database statistics."""
    if not dependencies.has_modules:
        return None
    try:
        from resources.lib.database.trakt_sync import TraktSyncDatabase
        import datetime
        import os

        database = TraktSyncDatabase()
        if not database.connect():
            xbmcgui.Dialog().notification('AIOStreams', 'Failed to connect to database', xbmcgui.NOTIFICATION_ERROR)
            return None
        try:
            cursor = database.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()] if cursor else []

            def count(table):
                if table not in tables:
                    return 0
                row = database.execute(f'SELECT COUNT(*) as count FROM {table}').fetchone()
                return row['count'] if row else 0

            activities = database.fetchone('SELECT last_activities_call FROM activities WHERE sync_id=1')
            last_sync = activities.get('last_activities_call') if activities else None
            last_sync_text = (
                datetime.datetime.fromtimestamp(last_sync).strftime('%Y-%m-%d %H:%M:%S')
                if last_sync else 'Never'
            )
            size = os.path.getsize(database.db_path) / 1024 if os.path.exists(database.db_path) else 0
            xbmcgui.Dialog().ok('Database Info', (
                'Database Statistics:\n\nTrakt Data:\n'
                f'  Shows: {count("shows")}\n  Episodes: {count("episodes")}\n'
                f'  Movies: {count("movies")}\n  Watchlist: {count("watchlist")}\n'
                f'  Hidden Shows: {count("hidden_shows")}\n\nStream Data:\n'
                f'  Statistics: {count("stream_stats")}\n  Preferences: {count("stream_preferences")}\n\n'
                f'Last Sync: {last_sync_text}\nDatabase Size: {size:.1f} KB'
            ))
        finally:
            database.disconnect()
    except Exception as error:
        xbmc.log(f'[AIOStreams] Failed to get database info: {error}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to get database info', xbmcgui.NOTIFICATION_ERROR)
    return None


def optimize_database(params, dependencies):
    """VACUUM and analyze the local Trakt database."""
    if not dependencies.has_modules:
        return None
    progress = None
    try:
        from resources.lib.database.trakt_sync import TraktSyncDatabase

        progress = xbmcgui.DialogProgress()
        progress.create('Database Optimization', 'Optimizing database...')
        database = TraktSyncDatabase()
        if not database.connect():
            progress.close()
            xbmcgui.Dialog().notification('AIOStreams', 'Failed to connect to database', xbmcgui.NOTIFICATION_ERROR)
            return None
        try:
            progress.update(30, 'Running VACUUM (reclaiming space)...')
            success = database.vacuum()
            progress.update(100, 'Optimization complete!')
            xbmc.sleep(500)
            progress.close()
            if success:
                xbmcgui.Dialog().notification('Database Optimized', 'Database has been optimized for better performance', xbmcgui.NOTIFICATION_INFO, 3000)
            else:
                xbmcgui.Dialog().notification('Optimization Warning', 'Optimization completed with warnings (check log)', xbmcgui.NOTIFICATION_WARNING, 3000)
        finally:
            database.disconnect()
    except Exception as error:
        if progress:
            progress.close()
        xbmc.log(f'[AIOStreams] Failed to optimize database: {error}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to optimize database', xbmcgui.NOTIFICATION_ERROR)
    return None


def clear_trakt_database(params, dependencies):
    """Clear Trakt tables and disposable metadata caches after confirmation."""
    if not dependencies.has_modules:
        return None
    if not xbmcgui.Dialog().yesno(
        'Clear Trakt Database',
        'This will clear all Trakt data from the local database.',
        'Data will be re-synced on next access.',
        'Continue?',
    ):
        return None
    return _clear_trakt_database_data(dependencies, 'All data cleared successfully')


def rebuild_trakt_database(params, dependencies):
    """Clear local Trakt data, then request one full sync."""
    if not dependencies.has_modules:
        return None
    if not xbmcgui.Dialog().yesno(
        'Rebuild Trakt Database',
        'This will clear the database and perform a full sync.',
        'This may take a few moments.',
        'Continue?',
    ):
        return None
    if _clear_trakt_database_data(dependencies, None):
        dependencies.force_trakt_sync({})
    return None


def database_reset(params, dependencies):
    """Perform the explicitly confirmed full Trakt/cache reset."""
    if not dependencies.has_modules:
        return None
    if not xbmcgui.Dialog().yesno(
        'Database Reset',
        'This will:\n• Clear ALL database tables\n• Delete ALL caches\n• Resync Trakt from scratch\n\n'
        'This action CANNOT be undone!\n\nAre you sure?',
    ):
        return None
    if _clear_trakt_database_data(dependencies, 'All database tables and caches cleared'):
        if dependencies.addon.getSettingBool('trakt_sync_auto'):
            dependencies.force_trakt_sync({})
    return None


def vacuum_database(params, dependencies):
    """Run a simple VACUUM action without the progress UI."""
    return optimize_database(params, dependencies)


def _clear_trakt_database_data(dependencies, success_message):
    try:
        from resources.lib.database.trakt_sync import TraktSyncDatabase

        dependencies.invalidate_trakt_progress_cache()
        database = TraktSyncDatabase()
        if not database.connect():
            xbmcgui.Dialog().notification('AIOStreams', 'Failed to connect to database', xbmcgui.NOTIFICATION_ERROR)
            return False
        try:
            for table in ('shows', 'episodes', 'movies', 'watchlist', 'bookmarks', 'hidden', 'activities', 'metas', 'catalogs'):
                database.execute(f'DELETE FROM {table}')
            database.commit()
        finally:
            database.disconnect()
        dependencies.cache.get_cache().cleanup_expired(force_all=True)
        dependencies.clear_clearlogo_cache()
        manager = dependencies.get_stream_manager()
        manager.clear_stats()
        manager.clear_preferences()
        if success_message:
            xbmcgui.Dialog().notification('AIOStreams', success_message, xbmcgui.NOTIFICATION_INFO)
        return True
    except Exception as error:
        xbmc.log(f'[AIOStreams] Failed to clear Trakt database: {error}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to clear database', xbmcgui.NOTIFICATION_ERROR)
        return False


def _run_web_config_action(function_name, label, success_message):
    try:
        from resources.lib import web_config

        if getattr(web_config, function_name)():
            xbmc.log(f'[AIOStreams] {success_message}', xbmc.LOGINFO)
    except ImportError as error:
        xbmc.log(f'[AIOStreams] Failed to import web_config: {error}', xbmc.LOGERROR)
        xbmcgui.Dialog().ok('AIOStreams', 'Web configuration module not available.\n\nPlease update the addon.')
    except Exception as error:
        xbmc.log(f'[AIOStreams] {label} action failed: {error}', xbmc.LOGERROR)
        xbmcgui.Dialog().ok('AIOStreams', f'{label} failed:\n\n{error}')
