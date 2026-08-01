"""Trakt-facing Kodi actions with explicit dependencies."""
from dataclasses import dataclass

import xbmc
import xbmcgui
import xbmcplugin

from ..items import media_action_params
from ..media import MediaRef


@dataclass(frozen=True)
class TraktDependencies:
    handle: int
    has_modules: bool
    get_setting: object
    get_url: object
    get_streams: object
    fetch_metadata_parallel: object
    create_listitem: object
    format_date: object
    clear_trakt_widget_cache: object
    origin_fingerprint: object = None


def trakt_menu(params, dependencies):
    """Trakt catalogs submenu."""
    from resources.lib import trakt
    if not dependencies.has_modules:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return

    xbmcplugin.setPluginCategory(dependencies.handle, 'Trakt Catalogs')
    xbmcplugin.setContent(dependencies.handle, 'videos')

    menu_items = [
        {'label': 'Next Up', 'url': dependencies.get_url(action='trakt_next_up'), 'icon': 'DefaultTVShows.png'},
        {'label': 'Watchlist - Movies', 'url': dependencies.get_url(action='trakt_watchlist', media_type='movies'), 'icon': 'DefaultMovies.png'},
        {'label': 'Watchlist - Shows', 'url': dependencies.get_url(action='trakt_watchlist', media_type='shows'), 'icon': 'DefaultTVShows.png'},
        # Trakt Collections and Recommendations removed per user request
    ]

    for item in menu_items:
        list_item = xbmcgui.ListItem(label=item['label'])
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(item['label'])
        list_item.setArt({'icon': item['icon']})
        xbmcplugin.addDirectoryItem(dependencies.handle, item['url'], list_item, True)

    xbmcplugin.endOfDirectory(dependencies.handle)


def force_trakt_sync(params, dependencies):
    """Force immediate Trakt sync with progress dialog."""
    from resources.lib import trakt
    if not dependencies.has_modules:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return

    from resources.lib.database.trakt_sync.activities import TraktSyncDatabase

    db = TraktSyncDatabase()
    result = db.sync_activities(silent=False)  # Show progress dialog

    if result is None:
        xbmcgui.Dialog().notification(
            'AIOStreams',
            'Sync throttled (wait 5 minutes)',
            xbmcgui.NOTIFICATION_INFO
        )
    elif result:
        xbmc.log('[AIOStreams] Force sync completed successfully', xbmc.LOGINFO)
    else:
        xbmc.log('[AIOStreams] Force sync completed with errors', xbmc.LOGWARNING)


def trakt_watchlist(params, dependencies):
    """Display Trakt watchlist with auto-sync."""
    from resources.lib import trakt
    # Suppression guard
    # Suppression guard (Global or Internal)
    win_home = xbmcgui.Window(10000)
    if win_home.getProperty('AIOStreams.SearchActive') == 'true' or \
       win_home.getProperty('AIOStreams.InternalSearchActive') == 'true':
        xbmc.log('[AIOStreams] Suppression: trakt_watchlist skipped (Search Active)', xbmc.LOGDEBUG)
        xbmcplugin.endOfDirectory(dependencies.handle, succeeded=True)
        return

    if not dependencies.has_modules:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return

    media_type = params.get('media_type', 'movies')
    items = []

    # Auto-sync if enabled (throttled to 5 minutes)
    auto_sync_enabled = dependencies.get_setting('trakt_sync_auto', 'true') == 'true'
    if auto_sync_enabled:
        try:
            from resources.lib.database.trakt_sync.activities import TraktSyncDatabase
            db = TraktSyncDatabase()
            db.sync_activities(silent=True)  # Silent auto-sync
        except Exception as e:
            xbmc.log(f'[AIOStreams] Auto-sync failed: {e}', xbmc.LOGWARNING)

    # Try fetching from database first (instant)
    try:
        from resources.lib.database.trakt_sync.activities import TraktSyncDatabase
        db = TraktSyncDatabase()

        # Query watchlist from database using helper which unpickles metadata
        mediatype_filter = 'movie' if media_type == 'movies' else 'show'
        items_raw = db.get_watchlist_items(mediatype_filter)

        if items_raw:
            # Convert database format to Trakt API format for compatibility
            content_key = media_type[:-1] if media_type.endswith('s') else media_type
            for row in items_raw:
                try:
                    # Use metadata if available (contains extended info)
                    # sqlite3.Row uses dictionary-style access, not .get()
                    metadata = row['metadata'] if 'metadata' in row.keys() else None
                    if metadata:
                        item_data = metadata
                    else:
                        item_data = {
                            'ids': {
                                'trakt': row['trakt_id'] if 'trakt_id' in row.keys() else None,
                                'imdb': row['imdb_id'] if 'imdb_id' in row.keys() else None
                            }
                        }

                    item_wrapper = {
                        'listed_at': row['listed_at'] if 'listed_at' in row.keys() else None,
                        content_key: item_data
                    }
                    items.append(item_wrapper)
                except Exception as e:
                    xbmc.log(f'[AIOStreams] Error unpacking watchlist row: {e}', xbmc.LOGWARNING)
                    continue
            xbmc.log(f'[AIOStreams] Watchlist: Loaded {len(items)} items from database', xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error accessing watchlist database: {e}', xbmc.LOGWARNING)

    # Fallback to old Trakt API method if database is empty or failed
    if not items:
        xbmc.log('[AIOStreams] Watchlist database empty/failed, using Trakt API', xbmc.LOGDEBUG)
        items = trakt.get_watchlist(media_type)

    if not items:
        xbmcgui.Dialog().notification('AIOStreams', 'Watchlist is empty', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return

    xbmcplugin.setPluginCategory(dependencies.handle, f'Trakt Watchlist - {media_type.capitalize()}')
    xbmcplugin.setContent(dependencies.handle, 'movies' if media_type == 'movies' else 'tvshows')

    # Prepare items for parallel fetching
    items_to_fetch = []
    for item in items:
        item_data = item.get('movie' if media_type == 'movies' else 'show', {})
        item_id = item_data.get('ids', {}).get('imdb', '')
        if item_id:
            items_to_fetch.append({'ids': {'imdb': item_id}})

    # Parallel fetch all metadata

    content_type_fetch = 'movie' if media_type == 'movies' else 'series'
    metadata_map = dependencies.fetch_metadata_parallel(items_to_fetch, content_type=content_type_fetch)

    for item in items:
        item_data = item.get('movie' if media_type == 'movies' else 'show', {})
        item_id = item_data.get('ids', {}).get('imdb', '')

        if not item_id:
            continue

        content_type = 'movie' if media_type == 'movies' else 'series'

        # Build metadata from Trakt data (no API call needed for text fields)
        meta = {
            'id': item_id,
            'name': item_data.get('title', 'Unknown'),
            'description': item_data.get('overview', ''),
            'year': item_data.get('year', 0),
            'genres': item_data.get('genres', []),
            'imdbRating': str(item_data.get('rating', '')) if item_data.get('rating') else '',
            'rating': item_data.get('rating', ''),
            'trakt_rating': item_data.get('rating', '')
        }

        # Use fetched metadata (parallel results)
        if item_id in metadata_map:
            cached_data = metadata_map[item_id]

            # Enhance with cached artwork and other metadata
            meta['poster'] = cached_data.get('poster', '')
            meta['background'] = cached_data.get('background', '')
            meta['logo'] = cached_data.get('logo', '')

            # CRITICAL FIX: If Trakt title is missing or "Unknown", use AIOStreams Title
            cached_title = cached_data.get('title') or cached_data.get('name', '')
            if (not meta.get('name') or meta['name'] == 'Unknown') and cached_title:
                meta['name'] = cached_title

            # Use cached description if Trakt description is empty
            if not meta.get('description') and cached_data.get('description'):
                meta['description'] = cached_data['description']

            # Get cast from cached AIOStreams data (includes photos)
            if 'cast' in cached_data:
                meta['cast'] = cached_data['cast']

            # MERGE CHIP METADATA: genres, rating, mpaa
            if cached_data.get('genres'):
                meta['genres'] = cached_data['genres']
            if cached_data.get('rating'):
                meta['imdbRating'] = str(cached_data['rating'])
            if cached_data.get('mpaa') or cached_data.get('certification'):
                meta['mpaa'] = cached_data.get('mpaa') or cached_data.get('certification')
            if cached_data.get('runtime'):
                meta['runtime'] = str(cached_data['runtime'])
            if cached_data.get('released'):
                meta['released'] = cached_data['released']

        media = MediaRef.from_meta(meta, content_type, dependencies.origin_fingerprint)
        # Set URL and folder status based on content type
        if media.content_type == 'series':
            url = dependencies.get_url(action='show_seasons', **media_action_params('show_seasons', media))
            is_folder = True
        else:
            url = dependencies.get_url(
                action='play', **media_action_params('play', media, clearlogo=meta.get('logo', ''))
            )
            is_folder = False

        list_item = dependencies.create_listitem(meta, media.content_type, url)
        xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, is_folder)

    # Set NumItems property if called from smart_widget
    if params.get('page') and params.get('index'):
        count_prop = f"AIOStreams.{params['page']}.{params['index']}.NumItems"
        xbmcgui.Window(10000).setProperty(count_prop, str(len(items)))
        xbmc.log(f'[AIOStreams] Set {count_prop} = {len(items)}', xbmc.LOGDEBUG)

    xbmcplugin.endOfDirectory(dependencies.handle)


def trakt_next_up(params, dependencies):
    """Display next episodes to watch using pure SQL - ZERO API calls!

    Uses Seren's approach: calculates next episode from local database.
    All episodes are stored during sync, so we can find the next unwatched
    episode purely from SQL without calling the API.
    """
    from resources.lib import trakt
    # Suppression guard
    # Suppression guard (Global or Internal)
    win_home = xbmcgui.Window(10000)
    if win_home.getProperty('AIOStreams.SearchActive') == 'true' or \
       win_home.getProperty('AIOStreams.InternalSearchActive') == 'true':
        xbmc.log('[AIOStreams] Suppression: trakt_next_up skipped (Search Active)', xbmc.LOGDEBUG)
        xbmcplugin.endOfDirectory(dependencies.handle, succeeded=True)
        return

    if not dependencies.has_modules:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return

    xbmcplugin.setPluginCategory(dependencies.handle, 'Next Up')
    xbmcplugin.setContent(dependencies.handle, 'episodes')

    # Prime database cache (batch fetch watched status)
    try:
        from resources.lib import trakt
        trakt.prime_database_cache()
    except:
        pass

    # Get next episodes from database - ONE SQL query, ZERO API calls!
    try:
        from resources.lib.database.trakt_sync import TraktSyncDatabase
        db = TraktSyncDatabase()
        next_episodes = db.get_next_up_episodes()
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error getting next up from database: {e}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Error loading Next Up', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return

    if not next_episodes:
        xbmc.log('[AIOStreams] DEBUG: trakt_next_up - No shows in progress (next_episodes list is empty)', xbmc.LOGWARNING)
        xbmcgui.Dialog().notification('AIOStreams', 'No shows in progress', xbmcgui.NOTIFICATION_INFO)

        # Fallback item for visual confirmation
        li = xbmcgui.ListItem(label='[No Next Up Episodes Found]')
        li.getVideoInfoTag().setPlot('Trakt returned no next up episodes.\nCheck your Trakt history or scrobbling status.')
        url = dependencies.get_url(action='noop')
        xbmcplugin.addDirectoryItem(dependencies.handle, url, li, False)

        xbmcplugin.endOfDirectory(dependencies.handle)
        return



    # Prepare item list for parallel fetching
    items_to_fetch = []
    for ep in next_episodes:
        show_imdb = ep.get('show_imdb_id')
        if show_imdb:
            items_to_fetch.append({'ids': {'imdb': show_imdb}})

    # Fetch all metadata in parallel

    metadata_map = dependencies.fetch_metadata_parallel(items_to_fetch, content_type='series')

    # Set NumItems property if called from smart_widget
    if params.get('page') and params.get('index'):
        count_prop = f"AIOStreams.{params['page']}.{params['index']}.NumItems"
        xbmcgui.Window(10000).setProperty(count_prop, str(len(next_episodes)))
        xbmc.log(f'[AIOStreams] Set {count_prop} = {len(next_episodes)}', xbmc.LOGDEBUG)

    def process_ep(ep_data):
        try:
            show_imdb = ep_data.get('show_imdb_id', '')
            show_title = ep_data.get('show_title', 'Unknown')
            season = ep_data.get('season', 0)
            episode = ep_data.get('episode', 0)
            episode_imdb = ep_data.get('episode_imdb_id', '')

            # Get artwork and basic metadata placeholders
            poster = ''
            fanart = ''
            logo = ''
            episode_thumb = ''
            episode_title = f'Episode {episode}'
            episode_overview = ''
            episode_air_date = ep_data.get('air_date', '')

            # 1. Try to get episode-specific metadata from database
            episode_meta = ep_data.get('episode_metadata')
            if episode_meta:
                episode_title = episode_meta.get('title', episode_title)
                episode_overview = episode_meta.get('overview', '')
                if not episode_air_date:
                    episode_air_date = episode_meta.get('first_aired', '') or episode_meta.get('aired', '')

            # 2. Get show metadata from our parallel fetch results
            meta_data = None
            if show_imdb and show_imdb in metadata_map:
                meta_data = metadata_map[show_imdb]

            # If not in map, try local DB
            if not meta_data and show_imdb:
                 meta_data = ep_data.get('show_metadata')

            # Extract artwork from show metadata
            matched_video = None
            if meta_data:
                show_title = meta_data.get('name', show_title)
                poster = meta_data.get('poster', '')
                fanart = meta_data.get('background', '')
                logo = meta_data.get('logo', '')

                # Try to get episode thumbnail from show metadata videos
                if not episode_thumb:
                    videos = meta_data.get('videos', [])
                    for video in videos:
                        if video.get('season') == season and video.get('episode') == episode:
                            matched_video = video
                            episode_thumb = video.get('thumbnail', '')
                            if not episode_meta:
                                episode_title = video.get('title', episode_title)
                                episode_overview = video.get('description', '')
                            break

            label = f'{show_title} S{season:02d}E{episode:02d}'
            show_ref = MediaRef.from_meta(
                meta_data or {'id': show_imdb, 'imdb_id': show_imdb, 'name': show_title},
                'series', dependencies.origin_fingerprint,
            )
            episode_ref = MediaRef.episode(
                show_ref, matched_video or episode_meta or {'id': episode_imdb}, season, episode,
                dependencies.origin_fingerprint,
            )
            url = dependencies.get_url(
                action='play',
                **media_action_params(
                    'play', show_ref, media_id=episode_ref.playback_id, season=season,
                    episode=episode, title=label, poster=poster, fanart=fanart, clearlogo=logo,
                )
            )

            # Prepare metadata for creation (merging show-level info for chips)
            meta = {
                'id': episode_ref.metadata_id,
                'imdb_id': episode_ref.imdb_id,
                'name': label,
                'description': episode_overview,
                'released': episode_air_date,
                'poster': poster,
                'background': fanart,
                'logo': logo
            }

            # Merge show-level metadata (genres, mpaa, rating) for chips
            if meta_data:
                meta['genres'] = meta_data.get('genres', [])
                meta['mpaa'] = meta_data.get('mpaa', '') or meta_data.get('certification', '')
                rating_val = meta_data.get('rating', '')
                meta['imdbRating'] = str(rating_val) if rating_val else ''
                meta['rating'] = rating_val
                meta['trakt_rating'] = rating_val
                if meta_data.get('runtime'):
                    meta['runtime'] = str(meta_data['runtime'])

            list_item = dependencies.create_listitem(meta, 'episode', url)

            # Mark this as a Next Up episode for special handling in the info panel
            list_item.setProperty('IsNextUpEpisode', 'true')
            list_item.setProperty('NextUpShowIMDb', show_imdb)
            list_item.setProperty('NextUpSeason', str(season))
            list_item.setProperty('NextUpEpisode', str(episode))

            # InfoTag cleanup
            info_tag = list_item.getVideoInfoTag()
            info_tag.setTitle(episode_title)
            info_tag.setTvShowTitle(show_title)
            info_tag.setSeason(season)
            info_tag.setEpisode(episode)

            if episode_air_date:
                air_date_str = episode_air_date.split('T')[0] if 'T' in episode_air_date else episode_air_date
                formatted_date = dependencies.format_date(air_date_str)
                list_item.setProperty('AirDate', formatted_date)
                list_item.setLabel2(formatted_date)

            if episode_thumb:
                list_item.setArt({'thumb': episode_thumb, 'poster': poster, 'fanart': fanart, 'clearlogo': logo})
            elif poster:
                list_item.setArt({'thumb': poster, 'poster': poster, 'fanart': fanart, 'clearlogo': logo})

            # Watched status and bookmarks
            percent = ep_data.get('percent_played', 0)
            if percent and percent > 0:
                list_item.setProperty('PercentPlayed', str(int(percent)))
                info_tag.setPercentPlayed(float(percent))
                resume_time = ep_data.get('resume_time', 0)
                if resume_time > 0:
                    list_item.setProperty('StartOffset', str(resume_time))

            show_trakt_id = ep_data.get('show_trakt_id')
            if show_trakt_id:
                is_watched = db.is_item_watched(show_trakt_id, 'episode', season, episode)
                if is_watched:
                    info_tag.setPlaycount(1)
                    list_item.setProperty('watched', 'true')
                    list_item.setProperty('WatchedOverlay', 'indicator_watched.png')

            # Build context menu (create_listitem_with_context already adds standard ones)
            context_menu = []
            context_menu.append(('[COLOR lightcoral]Browse Show[/COLOR]', f'ActivateWindow(Videos,{dependencies.get_url(action="show_seasons", **media_action_params("show_seasons", show_ref))},return)'))

            # Add Trakt watched toggle for episodes if authorized
            if dependencies.has_modules and trakt.get_access_token() and show_ref.imdb_id:
                show_trakt_id = ep_data.get('show_trakt_id')
                if show_trakt_id:
                    is_watched = db.is_item_watched(show_trakt_id, 'episode', season, episode)
                    if is_watched:
                        context_menu.append(('[COLOR lightcoral]Mark Episode As Unwatched[/COLOR]',
                                            f'RunPlugin({dependencies.get_url(action="trakt_mark_unwatched", media_type="show", imdb_id=show_ref.imdb_id, season=season, episode=episode)})'))
                    else:
                        context_menu.append(('[COLOR lightcoral]Mark Episode As Watched[/COLOR]',
                                            f'RunPlugin({dependencies.get_url(action="trakt_mark_watched", media_type="show", imdb_id=show_ref.imdb_id, season=season, episode=episode)})'))

            list_item.addContextMenuItems(context_menu)
            list_item.setProperty('IsPlayable', 'true')

            return (url, list_item, False)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error processing Next Up episode: {e}', xbmc.LOGERROR)
            return None

    # Execute processing
    for ep in next_episodes:
        result = process_ep(ep)
        if result:
            xbmcplugin.addDirectoryItem(dependencies.handle, result[0], result[1], result[2])

    # Push Next Up data to window properties for instant widget updates
    _push_next_up_to_window(next_episodes, dependencies)

    # Force container refresh to solve widget delay
    xbmc.executebuiltin('Container.Refresh')

    xbmcplugin.endOfDirectory(dependencies.handle)


def trakt_hide_show(params, dependencies):
    """Hide a show from progress."""
    from resources.lib import trakt
    if not dependencies.has_modules:
        return

    show_trakt_id = params.get('show_trakt_id', '')

    if show_trakt_id:
        trakt.hide_show_from_progress(int(show_trakt_id))
        xbmc.executebuiltin('Container.Refresh')


def trakt_auth(params, dependencies):
    """Authorize with Trakt."""
    from resources.lib import trakt
    if not dependencies.has_modules:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return

    trakt.authorize()


def trakt_revoke(params, dependencies):
    """Revoke Trakt authorization."""
    from resources.lib import trakt
    if not dependencies.has_modules:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return

    trakt.revoke_authorization()


def _refresh_ui(dependencies):
    """Refresh container and trigger background widget refresh."""
    # Clear Trakt widget cache so Next Up and Watchlist refresh with new data
    dependencies.clear_trakt_widget_cache()

    # Update WidgetReloadToken skin string to force immediate background refresh
    try:
        current_token = xbmc.getSkinVariableString('WidgetReloadToken')
        new_token = str(int(current_token) + 1) if current_token.isdigit() else "1"
        xbmc.executebuiltin(f'Skin.SetString(WidgetReloadToken,{new_token})')
    except:
        xbmc.executebuiltin('Skin.SetString(WidgetReloadToken,1)')

    xbmc.executebuiltin('Container.Refresh')
    try:
        from resources.lib import utils
        utils.trigger_background_refresh(delay=0.5)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to trigger widget refresh: {e}', xbmc.LOGDEBUG)


def _parse_episode_params(params):
    """Parse and convert episode parameters to integers.

    Args:
        params: Dict of URL parameters

    Returns:
        tuple: (season_int, episode_int) or (None, None)
    """
    season = params.get('season')
    episode = params.get('episode')
    season_int = int(season) if season else None
    episode_int = int(episode) if episode else None
    return season_int, episode_int


def _push_next_up_to_window(next_episodes, dependencies):
    """Push Next Up data to Kodi window properties for instant widget updates.

    This allows skins to access Next Up data without forcing container refresh,
    eliminating the "stutter" effect in widgets.

    Args:
        next_episodes: List of episode dicts from get_next_up_episodes()
    """
    try:
        window = xbmcgui.Window(10000)  # Home window (persistent)

        # Limit to first 20 episodes for performance
        limited_episodes = next_episodes[:20]

        # Push each episode to window properties
        for idx, ep_data in enumerate(limited_episodes):
            show_imdb = ep_data.get('show_imdb_id', '')
            show_title = ep_data.get('show_title', 'Unknown')
            season = ep_data.get('season', 0)
            episode = ep_data.get('episode', 0)
            episode_imdb = ep_data.get('episode_imdb_id', '')
            last_watched = ep_data.get('last_watched_at', '')

            # Set window properties with AIOStreams. prefix
            prefix = f'AIOStreams.NextUp.{idx}'
            window.setProperty(f'{prefix}.ShowTitle', str(show_title))
            window.setProperty(f'{prefix}.ShowIMDB', str(show_imdb))
            window.setProperty(f'{prefix}.Season', str(season))
            window.setProperty(f'{prefix}.Episode', str(episode))
            window.setProperty(f'{prefix}.EpisodeIMDB', str(episode_imdb))
            window.setProperty(f'{prefix}.ClearLogo', str(ep_data.get('Logo', '')))
            window.setProperty(f'{prefix}.Label', f'{show_title} S{season:02d}E{episode:02d}')
            window.setProperty(f'{prefix}.LastWatched', str(last_watched))
            window.setProperty(f'{prefix}.PlayURL', dependencies.get_url(action='play', content_type='series',
                                                            imdb_id=show_imdb, season=season, episode=episode))

        # Set total count
        window.setProperty('AIOStreams.NextUp.Count', str(len(limited_episodes)))

        # Clear unused slots (in case list got smaller)
        for idx in range(len(limited_episodes), 20):
            prefix = f'AIOStreams.NextUp.{idx}'
            window.clearProperty(f'{prefix}.ShowTitle')
            window.clearProperty(f'{prefix}.ShowIMDB')
            window.clearProperty(f'{prefix}.Season')
            window.clearProperty(f'{prefix}.Episode')
            window.clearProperty(f'{prefix}.EpisodeIMDB')
            window.clearProperty(f'{prefix}.Label')
            window.clearProperty(f'{prefix}.LastWatched')
            window.clearProperty(f'{prefix}.PlayURL')

        xbmc.log(f'[AIOStreams] Pushed {len(limited_episodes)} Next Up items to window properties', xbmc.LOGINFO)

    except Exception as e:
        xbmc.log(f'[AIOStreams] Error pushing Next Up to window properties: {e}', xbmc.LOGERROR)


def _prefetch_next_up_streams(next_episodes, dependencies):
    """Trigger background prefetch for top Next Up episodes.

    Args:
        next_episodes: List of episode dicts from get_next_up_episodes()
    """
    try:
        from resources.lib.stream_prefetch import get_prefetch_manager

        def get_streams_wrapper(show_imdb, season, episode):
            """Wrapper to fetch streams for an episode."""
            media_id = f"{show_imdb}:{season}:{episode}"
            return dependencies.get_streams('series', media_id)

        manager = get_prefetch_manager()
        manager.prefetch_streams_async(next_episodes, get_streams_wrapper)

    except Exception as e:
        xbmc.log(f'[AIOStreams] Error triggering stream prefetch: {e}', xbmc.LOGERROR)


def trakt_add_watchlist(params, dependencies):
    """Add item to Trakt watchlist."""
    from resources.lib import trakt
    if not dependencies.has_modules:
        return

    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')

    if imdb_id:
        trakt.add_to_watchlist(media_type, imdb_id)
        _refresh_ui(dependencies)


def trakt_remove_watchlist(params, dependencies):
    """Remove item from Trakt watchlist."""
    from resources.lib import trakt
    if not dependencies.has_modules:
        return

    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    season_int, episode_int = _parse_episode_params(params)

    if imdb_id:
        trakt.remove_from_watchlist(media_type, imdb_id, season_int, episode_int)
        _refresh_ui(dependencies)


def trakt_mark_watched(params, dependencies):
    """Mark item as watched on Trakt."""
    from resources.lib import trakt
    if not dependencies.has_modules:
        return

    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    playback_id = params.get('playback_id', '')
    season_int, episode_int = _parse_episode_params(params)

    if imdb_id:
        playback_id_int = int(playback_id) if playback_id else None
        trakt.mark_watched(media_type, imdb_id, season_int, episode_int, playback_id_int)
        _refresh_ui(dependencies)


def trakt_mark_unwatched(params, dependencies):
    """Mark item as unwatched on Trakt."""
    from resources.lib import trakt
    if not dependencies.has_modules:
        return

    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    season_int, episode_int = _parse_episode_params(params)

    if imdb_id:
        trakt.mark_unwatched(media_type, imdb_id, season_int, episode_int)
        _refresh_ui(dependencies)


def trakt_remove_playback(params, dependencies):
    """Remove item from continue watching without marking as watched."""
    from resources.lib import trakt
    if not dependencies.has_modules:
        return

    playback_id = params.get('playback_id', '')

    if playback_id:
        trakt.remove_from_playback(int(playback_id))


def trakt_hide_from_progress(params, dependencies):
    """Hide item from Trakt progress (Stop Watching/Drop)."""
    from resources.lib import trakt
    if not dependencies.has_modules:
        return

    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')

    if imdb_id:
        success = trakt.hide_from_progress(media_type, imdb_id)
        if success:
            _refresh_ui(dependencies)


def trakt_unhide_from_progress(params, dependencies):
    """Unhide item from Trakt progress (Undrop/Resume Watching)."""
    from resources.lib import trakt
    if not dependencies.has_modules:
        return

    media_type = params.get('media_type', 'movie')
    imdb_id = params.get('imdb_id', '')

    if imdb_id:
        success = trakt.unhide_from_progress(media_type, imdb_id)
        if success:
            _refresh_ui(dependencies)
