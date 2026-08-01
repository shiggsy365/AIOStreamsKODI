"""Catalog and menu browsing actions with explicit dependencies."""
from dataclasses import dataclass
import time
from urllib.parse import parse_qsl

import xbmc
import xbmcgui
import xbmcplugin

from ..items import media_action_params
from ..media import MediaRef


@dataclass(frozen=True)
class BrowseDependencies:
    handle: int
    has_modules: bool
    filters: object
    get_url: object
    get_manifest: object
    get_catalog: object
    get_meta: object
    fetch_metadata_parallel: object
    get_cached_clearlogo_path: object
    ensure_clearlogo_cached: object
    format_season_title: object
    format_episode_title: object
    apply_media_identity: object
    create_listitem: object
    origin_fingerprint: object = None


def index(params, dependencies):
    """Render the add-on's compact home menu."""
    xbmcplugin.setPluginCategory(dependencies.handle, 'AIOStreams')
    xbmcplugin.setContent(dependencies.handle, 'videos')
    entries = (
        ('[B]Search (Movies & TV Shows)[/B]', 'search', 'both', 'DefaultAddonsSearch.png'),
        ('[B]Search Movies[/B]', 'search', 'movie', 'DefaultMovies.png'),
        ('[B]Search TV Shows[/B]', 'search', 'series', 'DefaultTVShows.png'),
        ('Movie Lists', 'movie_lists', None, 'DefaultMovies.png'),
        ('Series Lists', 'series_lists', None, 'DefaultTVShows.png'),
    )
    for label, action, content_type, icon in entries:
        route = {'action': action}
        if content_type:
            route['content_type'] = content_type
        list_item = xbmcgui.ListItem(label=label)
        list_item.getVideoInfoTag().setTitle(label)
        list_item.setArt({'icon': icon})
        xbmcplugin.addDirectoryItem(dependencies.handle, dependencies.get_url(**route), list_item, True)
    xbmcplugin.endOfDirectory(dependencies.handle)


def youtube_menu(params, dependencies):
    """Render available third-party music-video entry points."""
    youtube_available = xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)')
    imvdb_available = xbmc.getCondVisibility('System.HasAddon(plugin.video.imvdb)')
    if not youtube_available and not imvdb_available:
        xbmcgui.Dialog().notification('AIOStreams', 'Music Video addons not installed', xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.endOfDirectory(dependencies.handle, succeeded=False)
        return None
    if youtube_available:
        for label, url, icon in (
            ('Search', 'plugin://plugin.video.youtube/search/?path=/root/search', 'DefaultAddonsSearch.png'),
            ('Playlists', 'plugin://plugin.video.youtube/playlists/', 'DefaultPlaylist.png'),
            ('Bookmarks', 'plugin://plugin.video.youtube/special/watch_later/', 'DefaultFolder.png'),
        ):
            list_item = xbmcgui.ListItem(label=label)
            list_item.setArt({'icon': icon, 'thumb': icon})
            list_item.getVideoInfoTag().setTitle(label)
            xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, True)
    xbmcplugin.endOfDirectory(dependencies.handle)
    return None


def movie_lists(params, dependencies):
    """Render the movie-list menu."""
    from resources.lib import trakt
    xbmcplugin.setPluginCategory(dependencies.handle, 'Movie Lists')
    xbmcplugin.setContent(dependencies.handle, 'videos')
    menu_items = [
        ('AIOStreams Catalogs', dependencies.get_url(action='catalogs', content_type='movie'),
         'DefaultMovies.png'),
    ]
    if dependencies.has_modules and trakt.get_access_token():
        menu_items.append(
            ('Watchlist - Trakt', dependencies.get_url(action='trakt_watchlist', media_type='movies'),
             'DefaultMovies.png')
        )
    _add_menu_items(menu_items, dependencies)


def series_lists(params, dependencies):
    """Render the series-list menu."""
    from resources.lib import trakt
    xbmcplugin.setPluginCategory(dependencies.handle, 'Series Lists')
    xbmcplugin.setContent(dependencies.handle, 'videos')
    menu_items = [
        ('AIOStreams Catalogs', dependencies.get_url(action='catalogs', content_type='series'),
         'DefaultTVShows.png'),
    ]
    if dependencies.has_modules and trakt.get_access_token():
        menu_items.extend([
            ('Next Up - Trakt', dependencies.get_url(action='trakt_next_up'), 'DefaultTVShows.png'),
            ('Watchlist - Trakt', dependencies.get_url(action='trakt_watchlist', media_type='shows'),
             'DefaultTVShows.png'),
        ])
    _add_menu_items(menu_items, dependencies)


def _add_menu_items(menu_items, dependencies):
    for label, url, icon in menu_items:
        list_item = xbmcgui.ListItem(label=label)
        list_item.getVideoInfoTag().setTitle(label)
        list_item.setArt({'icon': icon})
        xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, True)
    xbmcplugin.endOfDirectory(dependencies.handle)


def list_catalogs(params, dependencies):
    """List configured manifest catalogs for the requested content type."""
    filter_type = params.get('content_type')
    is_widget = params.get('widget') == 'true'
    manifest = dependencies.get_manifest()
    if not manifest or 'catalogs' not in manifest:
        xbmcgui.Dialog().notification('AIOStreams', 'No catalogs available', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return None

    category_name = {
        'movie': 'Movie Catalogs', 'series': 'Series Catalogs',
    }.get(filter_type, 'All Catalogs')
    xbmcplugin.setPluginCategory(dependencies.handle, category_name)
    xbmcplugin.setContent(dependencies.handle, 'videos')
    for catalog in manifest['catalogs']:
        catalog_name = catalog.get('name', 'Unknown Catalog')
        catalog_id = catalog.get('id')
        content_type = catalog.get('type', 'movie')
        if filter_type and content_type != filter_type:
            continue
        if 'search' in catalog_name.lower() or 'search' in str(catalog_id or '').lower():
            continue
        genre_extra = next(
            (extra for extra in catalog.get('extra', []) if extra.get('name') == 'genre'), None
        )
        if genre_extra and genre_extra.get('options'):
            action = 'browse_catalog' if is_widget else 'catalog_genres'
            extra = {'genre': 'All'} if is_widget else {}
            url = dependencies.get_url(
                action=action, catalog_id=catalog_id, content_type=content_type,
                catalog_name=catalog_name, **extra
            )
        else:
            url = dependencies.get_url(
                action='browse_catalog', catalog_id=catalog_id, content_type=content_type,
                catalog_name=catalog_name
            )
        list_item = xbmcgui.ListItem(label=catalog_name)
        list_item.getVideoInfoTag().setTitle(catalog_name)
        list_item.setArt({'icon': 'DefaultMovies.png' if content_type == 'movie' else 'DefaultTVShows.png'})
        xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, True)
    xbmcplugin.endOfDirectory(dependencies.handle)
    return None


def list_catalog_genres(params, dependencies):
    """Render the genre choices for one manifest catalog."""
    catalog_id = params['catalog_id']
    content_type = params['content_type']
    catalog_name = params.get('catalog_name', 'Catalog')
    manifest = dependencies.get_manifest()
    catalog = next(
        (catalog for catalog in (manifest or {}).get('catalogs', [])
         if catalog.get('id') == catalog_id and catalog.get('type') == content_type),
        None,
    )
    if not catalog:
        xbmcplugin.endOfDirectory(dependencies.handle)
        return None
    xbmcplugin.setPluginCategory(dependencies.handle, catalog_name)
    xbmcplugin.setContent(dependencies.handle, 'videos')
    _add_genre('All', catalog_id, content_type, catalog_name, dependencies)
    genre_extra = next(
        (extra for extra in catalog.get('extra', []) if extra.get('name') == 'genre'), None
    )
    for genre in (genre_extra or {}).get('options', []):
        _add_genre(genre, catalog_id, content_type, catalog_name, dependencies)
    xbmcplugin.endOfDirectory(dependencies.handle)
    return None


def _add_genre(genre, catalog_id, content_type, catalog_name, dependencies):
    list_item = xbmcgui.ListItem(label=genre)
    list_item.getVideoInfoTag().setTitle(genre)
    url = dependencies.get_url(
        action='browse_catalog', catalog_id=catalog_id, content_type=content_type,
        catalog_name=catalog_name, genre=genre
    )
    xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, True)


def browse_catalog(params, dependencies):
    """Render one catalog page, treating the UI's All choice as no genre filter."""
    from resources.lib import trakt
    xbmcgui.Window(10000).clearProperty('AIOStreams_ShowLogo')
    catalog_id = params['catalog_id']
    content_type = params['content_type']
    catalog_name = params.get('catalog_name', 'Catalog')
    genre = params.get('genre')
    skip = int(params.get('skip', 0))
    if dependencies.has_modules:
        try:
            trakt.prime_database_cache(content_type)
        except Exception as error:
            xbmc.log(f'[AIOStreams] browse_catalog: Failed to prime cache: {error}', xbmc.LOGERROR)
    catalog_data = dependencies.get_catalog(
        content_type, catalog_id, None if genre == 'All' else genre, skip
    )
    if not catalog_data or 'metas' not in catalog_data:
        xbmcgui.Dialog().notification('AIOStreams', 'No items found', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return None
    items = catalog_data['metas']
    if dependencies.has_modules and dependencies.filters:
        items = dependencies.filters.filter_items(items)
    category_title = f'{catalog_name} > {genre}' if genre and genre != 'All' else catalog_name
    xbmcplugin.setPluginCategory(dependencies.handle, category_title)
    xbmcplugin.setContent(dependencies.handle, 'movies' if content_type == 'movie' else 'tvshows')
    for meta in items:
        media = MediaRef.from_meta(meta, meta.get('type', content_type), dependencies.origin_fingerprint)
        if media.content_type == 'series':
            url = dependencies.get_url(
                action='show_seasons', **media_action_params('show_seasons', media)
            )
            is_folder = True
        else:
            url = dependencies.get_url(
                action='play', **media_action_params('play', media, clearlogo=meta.get('logo', ''))
            )
            is_folder = False
        list_item = dependencies.create_listitem(meta, media.content_type, url)
        if not is_folder:
            list_item.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, is_folder)
    if len(items) >= 20:
        list_item = xbmcgui.ListItem(label='More Results')
        list_item.setArt({'thumb': 'special://skin/media/more.png', 'poster': 'special://skin/media/more.png'})
        url = dependencies.get_url(
            action='browse_catalog', catalog_id=catalog_id, content_type=content_type,
            catalog_name=catalog_name, genre=genre or '', skip=skip + 20
        )
        xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, True)
    if params.get('page') and params.get('index'):
        xbmcgui.Window(10000).setProperty(
            f"AIOStreams.{params['page']}.{params['index']}.NumItems", str(len(items))
        )
    xbmcplugin.endOfDirectory(dependencies.handle)
    return None


def browse_show(params, dependencies):
    """Set up the skin's custom TV-show browse window."""
    meta_id = params.get('meta_id')
    if not meta_id:
        xbmc.log('[AIOStreams] browse_show: meta_id parameter is missing or empty', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Invalid show ID', xbmcgui.NOTIFICATION_ERROR)
        return None

    meta_data = dependencies.get_meta('series', meta_id)
    if not meta_data or 'meta' not in meta_data:
        xbmcgui.Dialog().notification('AIOStreams', 'Series info not found', xbmcgui.NOTIFICATION_ERROR)
        return None

    meta = meta_data['meta']
    seasons = {}
    for video in meta.get('videos', []):
        season = video.get('season')
        if season is not None:
            seasons.setdefault(season, []).append(video)
    if not seasons:
        xbmcgui.Dialog().notification('AIOStreams', 'No seasons found', xbmcgui.NOTIFICATION_INFO)
        return None

    window = xbmcgui.Window(10000)
    window.setProperty('BrowseShow.Title', meta.get('name', 'Unknown Series'))
    window.setProperty('BrowseShow.MetaID', meta_id)
    if meta.get('poster'):
        window.setProperty('BrowseShow.Poster', meta['poster'])
    if meta.get('background'):
        window.setProperty('BrowseShow.Fanart', meta['background'])
    if meta.get('plot'):
        window.setProperty('BrowseShow.Plot', meta['plot'])
    window.setProperty('BrowseShow.SeasonCount', str(len(seasons)))
    xbmc.executebuiltin('ActivateWindow(1114)')
    return None


def show_seasons(params, dependencies):
    """Render a show's seasons with artwork and Trakt watch state."""
    from resources.lib import trakt

    meta_id = params.get('meta_id')
    if not meta_id:
        xbmc.log('[AIOStreams] show_seasons: meta_id parameter is missing or empty', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Invalid show ID', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return None

    meta_data = _get_series_meta(meta_id, dependencies)
    if not meta_data or 'meta' not in meta_data:
        xbmcgui.Dialog().notification('AIOStreams', 'Series info not found', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return None

    meta = meta_data['meta']
    show_ref = MediaRef.from_meta(meta, 'series', dependencies.origin_fingerprint)
    series_name = meta.get('name', 'Unknown Series')
    xbmcplugin.setPluginCategory(dependencies.handle, series_name)
    xbmcplugin.setContent(dependencies.handle, 'seasons')
    _set_series_logo(meta, meta_id, dependencies)

    seasons = {}
    for video in meta.get('videos', []):
        season = video.get('season')
        if season is not None:
            seasons.setdefault(season, []).append(video)
    if not seasons:
        xbmcgui.Dialog().notification('AIOStreams', 'No seasons found', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return None

    show_progress = None
    if dependencies.has_modules and trakt.get_access_token():
        show_progress = trakt.get_show_progress(show_ref.imdb_id or meta_id)

    for season_num in sorted(seasons):
        episode_count = len(seasons[season_num])
        aired, completed = 0, 0
        if show_progress:
            for season_data in show_progress.get('seasons', []):
                if season_data.get('number') == season_num:
                    aired = season_data.get('aired', 0)
                    completed = season_data.get('completed', 0)
                    break
        is_season_watched = aired > 0 and aired == completed
        if dependencies.has_modules:
            season_label = dependencies.format_season_title(
                season_num, episode_count, aired, completed
            )
        else:
            season_label = f'Season {season_num} ({episode_count} episodes)'

        list_item = xbmcgui.ListItem(label=season_label)
        info_tag = list_item.getVideoInfoTag()
        info_tag.setTitle(season_label)
        info_tag.setSeason(season_num)
        info_tag.setTvShowTitle(series_name)
        info_tag.setMediaType('season')
        plot = meta.get('plot') or meta.get('overview') or meta.get('description', '')
        xbmc.log(f'[AIOStreams] Season {season_num}: Plot="{plot}"', xbmc.LOGINFO)
        if not plot:
            xbmc.log(f'[AIOStreams] Meta Keys Available: {list(meta.keys())}', xbmc.LOGINFO)
            plot = 'DEBUG: Plot missing from metadata'
        info_tag.setPlot(plot)
        list_item.setProperty('Plot', plot)
        list_item.setProperty('TVShowPlot', plot)
        list_item.setProperty('Overview', plot)
        list_item.setProperty('DEBUG_PLOT', 'DEBUG_MODE_ON')
        list_item.setProperty('meta_id', str(meta_id))
        list_item.setProperty('season_num', str(season_num))
        if is_season_watched:
            info_tag.setPlaycount(1)
            list_item.setProperty('WatchedOverlay', 'OverlayWatched.png')
        _set_season_art(list_item, meta, meta_id, dependencies)

        context_menu = []
        if dependencies.has_modules and trakt.get_access_token() and show_ref.imdb_id:
            action = 'trakt_mark_unwatched' if is_season_watched else 'trakt_mark_watched'
            label = 'Mark Season As Unwatched' if is_season_watched else 'Mark Season As Watched'
            context_menu.append((
                f'[COLOR lightcoral]{label}[/COLOR]',
                f'RunPlugin({dependencies.get_url(action=action, media_type="show", imdb_id=show_ref.imdb_id, season=season_num)})',
            ))
        list_item.addContextMenuItems(context_menu)
        url = dependencies.get_url(
            action='show_episodes',
            **media_action_params('show_episodes', show_ref, season=season_num),
        )
        xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, True)

    xbmcplugin.endOfDirectory(dependencies.handle)
    return None


def _get_series_meta(meta_id, dependencies):
    """Prefer the local Trakt SyncDB before requesting series metadata."""
    try:
        from resources.lib.database.trakt_sync import TraktSyncDatabase

        db = TraktSyncDatabase()
        if isinstance(meta_id, int) or (isinstance(meta_id, str) and meta_id.isdigit()):
            trakt_id = int(meta_id)
        elif isinstance(meta_id, str) and meta_id.startswith('tt'):
            trakt_id = db.get_trakt_id_for_item(meta_id, 'show')
        else:
            trakt_id = None
        if trakt_id:
            show_row = db.get_show(trakt_id)
            if show_row and show_row.get('metadata'):
                show_meta = show_row['metadata']
                episode_rows = db.get_episodes_for_show(trakt_id)
                if episode_rows:
                    videos = []
                    for row in episode_rows:
                        episode = row.get('metadata', {}) or {}
                        episode.setdefault('season', row['season'])
                        episode.setdefault('episode', row['episode'])
                        videos.append(episode)
                    show_meta['videos'] = videos
                    xbmc.log(f'[AIOStreams] Loaded {len(videos)} episodes from local SyncDB', xbmc.LOGINFO)
                    return {'meta': show_meta}
    except Exception as error:
        xbmc.log(f'[AIOStreams] SyncDB optimization error: {error}', xbmc.LOGERROR)
    return dependencies.get_meta('series', meta_id)


def _set_series_logo(meta, meta_id, dependencies):
    logo_url = meta.get('logo')
    window = xbmcgui.Window(10000)
    if logo_url:
        cached_logo = dependencies.get_cached_clearlogo_path('series', meta_id)
        window.setProperty('AIOStreams_ShowLogo', cached_logo or logo_url)
        window.setProperty('AIOStreams_HasLogo', 'true')
        if not cached_logo:
            dependencies.ensure_clearlogo_cached(meta, 'series', meta_id)
    else:
        window.setProperty('AIOStreams_HasLogo', 'false')


def _set_season_art(list_item, meta, meta_id, dependencies):
    logo_url = meta.get('logo')
    if logo_url:
        cached_logo = dependencies.get_cached_clearlogo_path('series', meta_id)
        logo = cached_logo or logo_url
        list_item.setArt({
            'poster': meta.get('poster', ''), 'thumb': meta.get('poster', ''),
            'fanart': meta.get('background', ''), 'clearlogo': logo, 'logo': logo,
            'tvshow.clearlogo': logo,
        })
    elif meta.get('poster'):
        list_item.setArt({'poster': meta['poster'], 'thumb': meta['poster']})
    if meta.get('background') and not logo_url:
        list_item.setArt({'fanart': meta['background']})


def show_episodes(params, dependencies):
    """Render a season's episodes with exact episode playback identities."""
    from resources.lib import trakt

    meta_id = params.get('meta_id')
    season_param = params.get('season')
    if not meta_id or not season_param:
        xbmc.log('[AIOStreams] show_episodes: meta_id or season parameter is missing', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Invalid episode parameters', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return None
    try:
        season = int(season_param)
    except (ValueError, TypeError):
        xbmc.log(f'[AIOStreams] show_episodes: Invalid season number: {season_param}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Invalid season number', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return None

    meta_data = _get_series_meta(meta_id, dependencies)
    if not meta_data or 'meta' not in meta_data:
        xbmcgui.Dialog().notification('AIOStreams', 'Series info not found', xbmcgui.NOTIFICATION_ERROR)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return None
    meta = meta_data['meta']
    show_ref = MediaRef.from_meta(meta, 'series', dependencies.origin_fingerprint)
    series_name = meta.get('name', 'Unknown Series')
    _set_series_logo(meta, meta_id, dependencies)
    xbmcplugin.setPluginCategory(dependencies.handle, f'{series_name} - Season {season}')
    xbmcplugin.setContent(dependencies.handle, 'episodes')

    videos = meta.get('videos', [])
    xbmc.log(
        f'[AIOStreams] show_episodes: Searching for Season {season} in {len(videos)} videos',
        xbmc.LOGINFO,
    )
    episodes = [video for video in videos if video.get('season') == season]
    xbmc.log(f'[AIOStreams] show_episodes: Found {len(episodes)} matching episodes', xbmc.LOGINFO)
    if not episodes:
        xbmcgui.Dialog().notification('AIOStreams', 'No episodes found', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return None
    episodes.sort(key=lambda episode: episode.get('episode', 0))

    watched_episodes = set()
    if dependencies.has_modules and trakt.get_access_token():
        show_progress = trakt.get_show_progress(show_ref.imdb_id or meta_id)
        if show_progress:
            for season_data in show_progress.get('seasons', []):
                if season_data.get('number') == season:
                    watched_episodes = {
                        episode.get('number') for episode in season_data.get('episodes', [])
                        if episode.get('completed', False)
                    }
                    break
        trakt.is_in_watchlist('series', show_ref.imdb_id or meta_id)

    for episode in episodes:
        _add_episode(episode, season, meta_id, meta, show_ref, series_name, watched_episodes, dependencies)
    xbmcplugin.endOfDirectory(dependencies.handle)
    return None


def _add_episode(episode, season, meta_id, meta, show_ref, series_name, watched_episodes, dependencies):
    episode_num = episode.get('episode', 0)
    raw_title = episode.get('title', f'Episode {episode_num}')
    is_watched = episode_num in watched_episodes
    if dependencies.has_modules:
        label = dependencies.format_episode_title(episode_num, raw_title, is_watched, 100 if is_watched else 0)
    else:
        label = f'{episode_num}. {raw_title}'
    episode_ref = MediaRef.episode(show_ref, episode, season, episode_num, dependencies.origin_fingerprint)
    list_item = xbmcgui.ListItem(label=label)
    dependencies.apply_media_identity(list_item, episode_ref)
    info_tag = list_item.getVideoInfoTag()
    info_tag.setTitle(raw_title)
    info_tag.setEpisode(episode_num)
    info_tag.setSeason(season)
    info_tag.setTvShowTitle(series_name)
    info_tag.setPlot(episode.get('overview', ''))
    info_tag.setMediaType('episode')
    _set_episode_runtime(info_tag, episode.get('runtime', ''))
    _set_episode_premiered(info_tag, episode.get('released', ''))
    _set_episode_art(list_item, episode, meta, meta_id, dependencies)
    if is_watched:
        info_tag.setPlaycount(1)
        list_item.setProperty('WatchedOverlay', 'OverlayWatched.png')

    episode_title = f'{series_name} - S{season:02d}E{episode_num:02d}'
    episode_media_id = episode_ref.playback_id
    episode_poster = meta.get('poster', '')
    episode_fanart = meta.get('background', '')
    episode_clearlogo = meta.get('logo', '')
    context_menu = [
        (
            '[COLOR lightcoral]Browse Show[/COLOR]',
            f'ActivateWindow(Videos,{dependencies.get_url(action="show_seasons", **media_action_params("show_seasons", show_ref))},return)',
        ),
    ]
    _add_episode_watch_menu(
        context_menu, is_watched, show_ref, season, episode_num, dependencies
    )
    list_item.addContextMenuItems(context_menu)
    url = dependencies.get_url(
        action='play',
        **media_action_params(
            'play', show_ref, media_id=episode_media_id, season=season, episode=episode_num,
            title=episode_title, poster=episode_poster, fanart=episode_fanart,
            clearlogo=episode_clearlogo,
        ),
    )
    list_item.setProperty('IsPlayable', 'true')
    xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, False)


def _set_episode_runtime(info_tag, runtime):
    if not runtime:
        return
    try:
        runtime_text = str(runtime).lower()
        if 'h' in runtime_text:
            hours_text, minutes_text = runtime_text.split('h', 1)
            total_minutes = int(hours_text.strip()) * 60
            minutes_text = minutes_text.replace('min', '').replace('minutes', '').strip()
            if minutes_text:
                total_minutes += int(minutes_text)
        else:
            total_minutes = int(runtime_text.replace('min', '').replace('minutes', '').strip())
        if total_minutes > 0:
            info_tag.setDuration(total_minutes * 60)
    except Exception:
        pass


def _set_episode_premiered(info_tag, released):
    if not released:
        return
    try:
        info_tag.setPremiered(released.split('T')[0])
    except Exception:
        pass


def _set_episode_art(list_item, episode, meta, meta_id, dependencies):
    if episode.get('thumbnail'):
        list_item.setArt({'thumb': episode['thumbnail']})
    elif meta.get('poster'):
        list_item.setArt({'thumb': meta['poster']})
    if meta.get('background'):
        list_item.setArt({'fanart': meta['background']})
    logo_url = meta.get('logo')
    if logo_url:
        cached_logo = dependencies.get_cached_clearlogo_path('series', meta_id)
        logo = cached_logo or logo_url
        list_item.setArt({'clearlogo': logo, 'logo': logo, 'tvshow.clearlogo': logo})
        if not cached_logo:
            dependencies.ensure_clearlogo_cached(meta, 'series', meta_id)


def _add_episode_watch_menu(context_menu, is_watched, show_ref, season, episode_num, dependencies):
    from resources.lib import trakt

    if not (dependencies.has_modules and trakt.get_access_token() and show_ref.imdb_id):
        return
    action = 'trakt_mark_unwatched' if is_watched else 'trakt_mark_watched'
    label = 'Mark Episode As Unwatched' if is_watched else 'Mark Episode As Watched'
    context_menu.append((
        f'[COLOR lightcoral]{label}[/COLOR]',
        f'RunPlugin({dependencies.get_url(action=action, media_type="show", imdb_id=show_ref.imdb_id, season=season, episode=episode_num)})',
    ))


def show_related(params, dependencies):
    """Show related titles, fetching metadata in parallel where possible."""
    if not dependencies.has_modules:
        xbmcgui.Dialog().ok('AIOStreams', 'Trakt module not available')
        return None

    from resources.lib import trakt

    content_type = params.get('content_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    title = params.get('title', 'Unknown')
    if not imdb_id:
        xbmcplugin.endOfDirectory(dependencies.handle, succeeded=False)
        return None

    xbmcplugin.setPluginCategory(dependencies.handle, f'Similar to {title}')
    xbmcplugin.setContent(dependencies.handle, 'movies' if content_type == 'movie' else 'tvshows')
    items = trakt.get_related(content_type, imdb_id, page=1, limit=20)
    if not items:
        xbmcgui.Dialog().notification('AIOStreams', 'No related content found', xbmcgui.NOTIFICATION_INFO)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return None

    movie_items, show_items = [], []
    for item in items:
        item_type = 'movie' if 'movie' in item else 'show'
        item_data = item.get('movie') or item.get('show', {})
        item_id = item_data.get('ids', {}).get('imdb', '')
        if item_id:
            target = movie_items if item_type == 'movie' else show_items
            target.append({'ids': {'imdb': item_id}})

    metadata_map = {}
    if movie_items:
        xbmc.log(f'[AIOStreams] Related: Fetching {len(movie_items)} movies in parallel...', xbmc.LOGINFO)
        metadata_map.update(dependencies.fetch_metadata_parallel(movie_items, 'movie'))
    if show_items:
        xbmc.log(f'[AIOStreams] Related: Fetching {len(show_items)} shows in parallel...', xbmc.LOGINFO)
        metadata_map.update(dependencies.fetch_metadata_parallel(show_items, 'series'))

    for item in items:
        item_type = 'movie' if 'movie' in item else 'show'
        item_data = item.get('movie') or item.get('show', {})
        item_id = item_data.get('ids', {}).get('imdb', '')
        if not item_id:
            continue
        item_content_type = 'movie' if item_type == 'movie' else 'series'
        meta = metadata_map.get(item_id)
        if not meta:
            meta_data = dependencies.get_meta(item_content_type, item_id)
            if meta_data and 'meta' in meta_data:
                meta = meta_data['meta']
        if not meta:
            meta = {
                'id': item_id, 'name': item_data.get('title', 'Unknown'),
                'description': item_data.get('overview', ''), 'year': item_data.get('year', 0),
                'genres': [],
            }

        media = MediaRef.from_meta(meta, item_content_type, dependencies.origin_fingerprint)
        if media.content_type == 'series':
            url = dependencies.get_url(action='show_seasons', **media_action_params('show_seasons', media))
            is_folder = True
        else:
            url = dependencies.get_url(
                action='play', **media_action_params('play', media, clearlogo=meta.get('logo', ''))
            )
            is_folder = False
        list_item = dependencies.create_listitem(meta, media.content_type, url)
        if not is_folder:
            list_item.setProperty('IsPlayable', 'true')
        xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, is_folder)

    xbmcplugin.endOfDirectory(dependencies.handle)
    return None


def update_container(params, dependencies):
    """Handle the skin-driven episode container update request."""
    target_id = params.get('target_id')
    meta_id = params.get('meta_id')
    season = params.get('season')
    xbmc.log(
        f'[AIOStreams] update_container triggered: target={target_id}, meta={meta_id}, season={season}',
        xbmc.LOGINFO,
    )
    if target_id and meta_id and season:
        url = dependencies.get_url(action='show_episodes', meta_id=meta_id, season=season)
        window = xbmcgui.Window(xbmcgui.getCurrentWindowId())
        window.setProperty('AIOStreams_EpisodeUpdate_URL', url)
        xbmc.log('[AIOStreams] Setting episode update property', xbmc.LOGINFO)
        xbmc.executebuiltin(
            f"Container({target_id}).Update('$INFO[Window.Property(AIOStreams_EpisodeUpdate_URL)]')"
        )
    return None


@dataclass(frozen=True)
class WidgetDependencies:
    handle: int
    has_modules: bool
    get_url: object
    get_catalog: object
    get_meta: object
    create_listitem: object
    dispatch_action: object
    origin_fingerprint: object = None


_widget_cache = {}
_widget_cache_ttl = 3600


def _get_cached_widget(cache_key):
    """Get cached widget data if still valid."""
    import time
    if cache_key in _widget_cache:
        cache_entry = _widget_cache[cache_key]
        age = time.time() - cache_entry['timestamp']
        if age < _widget_cache_ttl:
            xbmc.log(f'[AIOStreams] Widget cache hit: {cache_key} (age: {int(age)}s)', xbmc.LOGDEBUG)
            return cache_entry['data']
        else:
            # Expired, remove it
            del _widget_cache[cache_key]
            xbmc.log(f'[AIOStreams] Widget cache expired: {cache_key}', xbmc.LOGDEBUG)
    return None


def _cache_widget(cache_key, data):
    """Cache widget data."""
    import time
    _widget_cache[cache_key] = {'data': data, 'timestamp': time.time()}
    xbmc.log(f'[AIOStreams] Widget cached: {cache_key}', xbmc.LOGDEBUG)


def clear_trakt_widget_cache():
    """
    Clear widget cache for Trakt-related widgets only.
    Called after Trakt actions (mark watched, add/remove watchlist).

    Clears cache for:
    - Trakt Next Up (home widget)
    - Trakt Watchlist Movies (home widget)
    - Trakt Watchlist Series (home widget)
    - Any catalog-based Trakt widgets (trending, popular, recommendations)
    """
    global _widget_cache

    # Clear catalog-based Trakt widgets (those with 'trakt' in the catalog ID)
    trakt_keys = [k for k in _widget_cache.keys() if 'trakt' in k.lower()]

    for key in trakt_keys:
        del _widget_cache[key]
        xbmc.log(f'[AIOStreams] Cleared Trakt widget cache: {key}', xbmc.LOGDEBUG)

    if trakt_keys:
        xbmc.log(f'[AIOStreams] Cleared {len(trakt_keys)} Trakt widget cache entries', xbmc.LOGINFO)


def smart_widget(params, dependencies):
    """
    Dynamic widget content generator using widget_config.json.

    URL Parameters:
        index: Widget index (0, 1, 2, ...)
        content_type: 'series', 'movie', or 'home'

    Returns:
        Content from configured widget at specified index
    """
    from resources.lib import trakt
    # Suppression guard (Global or Internal)
    win_home = xbmcgui.Window(10000)
    if win_home.getProperty('AIOStreams.SearchActive') == 'true' or \
       win_home.getProperty('AIOStreams.InternalSearchActive') == 'true':
        xbmc.log('[AIOStreams] Suppression: smart_widget skipped (Search Active)', xbmc.LOGINFO)
        # Return TRUE but empty to prevent Kodi from showing "Plugin Error" dialog
        xbmcplugin.endOfDirectory(dependencies.handle, succeeded=True)
        return

    index = int(params.get('index', 0))
    # content_type param from URL (usually 'home', 'movie', 'series')
    url_content_type = params.get('content_type', 'movie')

    xbmc.log(f'[AIOStreams] smart_widget: index={index}, source_page={url_content_type}', xbmc.LOGINFO)

    # Use widget_config_loader to get configured widget
    try:
        from resources.lib.widget_config_loader import get_widget_at_index

        # Map content_type to page name
        page_map = {'home': 'home', 'series': 'tvshows', 'movie': 'movies'}
        page = page_map.get(url_content_type, url_content_type)

        # Get widget from config
        widget = get_widget_at_index(page, index)

        if not widget:
            xbmc.log(f'[AIOStreams] smart_widget: No widget configured at index {index} for {page}', xbmc.LOGINFO)
            xbmcplugin.endOfDirectory(dependencies.handle)
            return

        # Extract widget details
        path = widget.get('path', '')
        label = widget.get('label', 'Unknown')
        # CRITICAL: Use the widget's internal type (movie/series) for the API call
        content_type = widget.get('type', 'movie')

        xbmc.log(f'[AIOStreams] smart_widget: Loading "{label}" (Index: {index}, Page: {page}, Type: {content_type})', xbmc.LOGINFO)

        # Define property name for the header
        prop_name = None
        if page == 'home':
            prop_name = f'WidgetLabel_Home_{index}'
        elif page == 'movies':
            prop_name = f'movie_catalog_{index}_name'
        elif page == 'tvshows':
            prop_name = f'series_catalog_{index}_name'

        if prop_name:
            xbmcgui.Window(10000).setProperty(prop_name, label)
            # Set generic property too
            xbmcgui.Window(10000).setProperty(f'{page}_widget_{index}_name', label)

        # Parse the widget path
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(path)
        widget_params = parse_qs(parsed.query)

        # Extract action
        action = widget_params.get('action', [None])[0]

        if not action:
            xbmc.log(f'[AIOStreams] smart_widget: No action in widget path', xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(dependencies.handle)
            return

        # Handle different actions
        # Handle different actions
        if action == 'trakt_next_up':
            xbmc.log(f'[AIOStreams] smart_widget: Executing trakt_next_up', xbmc.LOGDEBUG)
            return dependencies.dispatch_action('trakt_next_up',
                dict(widget_params, page=page, index=index)
            )

        elif action == 'trakt_watchlist':
            media_type = widget_params.get('media_type', ['movies'])[0]
            xbmc.log(f'[AIOStreams] smart_widget: Executing trakt_watchlist ({media_type})', xbmc.LOGDEBUG)
            return dependencies.dispatch_action('trakt_watchlist',
                dict(widget_params, media_type=media_type, page=page, index=index)
            )

        elif action == 'catalog' or action == 'browse_catalog':
            catalog_id = widget_params.get('catalog_id', [None])[0]

            # LOCAL OVERRIDE: Redirect Trakt recommendations to local API - REMOVED PER REQUEST
            # if catalog_id and 'trakt.recommendations' in catalog_id:
            #     xbmc.log(f'[AIOStreams] smart_widget: Overriding {catalog_id} with local Trakt recommendations', xbmc.LOGDEBUG)
            #     media_type = 'movies' if 'movies' in catalog_id else 'shows'
            #     return trakt_recommendations({'media_type': media_type, 'page': 'home', 'index': str(index)})
            catalog_id = widget_params.get('catalog_id', [None])[0]

            if not catalog_id:
                xbmc.log(f'[AIOStreams] smart_widget: missing catalog_id for {action}', xbmc.LOGERROR)
                xbmcplugin.endOfDirectory(dependencies.handle)
                return

            xbmc.log(f'[AIOStreams] smart_widget: Executing catalog/browse_catalog {catalog_id} (Type: {content_type})', xbmc.LOGINFO)
            xbmcplugin.setPluginCategory(dependencies.handle, label)
            xbmcplugin.setContent(dependencies.handle, 'tvshows' if content_type == 'series' else 'movies')

            if dependencies.has_modules:
                trakt.prime_database_cache(content_type)

            cache_key = f'widget_{content_type}_{catalog_id}_all'
            catalog_data = _get_cached_widget(cache_key)

            if catalog_data is None:
                start_time = time.time()
                catalog_data = dependencies.get_catalog(content_type, catalog_id, genre=None, skip=0)
                duration = time.time() - start_time
                xbmc.log(f'[AIOStreams] smart_widget: get_catalog took {duration:.2f} seconds for {catalog_id}', xbmc.LOGINFO)

                if catalog_data and 'metas' in catalog_data:
                    _cache_widget(cache_key, catalog_data)

            if not catalog_data or 'metas' not in catalog_data:
                xbmc.log(f'[AIOStreams] smart_widget: No data found for catalog {catalog_id}', xbmc.LOGWARNING)
                xbmcplugin.endOfDirectory(dependencies.handle)
                return

            # Pre-fetch full metadata in parallel to get clearlogos
            items_to_fetch = []
            for meta in catalog_data['metas']:
                item_id = meta.get('id')
                if item_id:
                    # Detect type from ID format or catalog data
                    item_type = 'series' if item_id.startswith('tt') and ':' in item_id else 'movie'
                    if not ':' in item_id and content_type == 'series':
                        item_type = 'series'

                    items_to_fetch.append({'ids': {'imdb': item_id}, 'type': item_type})

            # Fetch metadata with logos in parallel
            metadata_map = {}
            if items_to_fetch:
                xbmc.log(f'[AIOStreams] smart_widget: Fetching {len(items_to_fetch)} items metadata in parallel...', xbmc.LOGDEBUG)

                # Custom parallel fetch to handle mixed types
                def fetch_single_smart(item):
                    try:
                        ids = item.get('ids', {})
                        i_id = ids.get('imdb')
                        i_type = item.get('type', 'movie')
                        res = dependencies.get_meta(i_type, i_id)
                        if res and 'meta' in res:
                            return (i_id, res['meta'])
                    except: pass
                    return None

                from concurrent.futures import ThreadPoolExecutor, as_completed
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(fetch_single_smart, item) for item in items_to_fetch]
                    for future in as_completed(futures):
                        res = future.result()
                        if res: metadata_map[res[0]] = res[1]

            for meta in catalog_data['metas']:
                try:
                    item_id = meta.get('id')
                    if not item_id:
                        continue

                    # Merge with full metadata if available (for logos, cast, etc.)
                    full_meta = metadata_map.get(item_id, {})
                    if full_meta:
                        # Smart merge: full_meta overwrites catalog data, but preserve non-empty rating fields
                        merged_meta = {**meta, **full_meta}

                        # Preserve catalog values if API result is missing them (or empty)
                        for field in ['imdbRating', 'rating', 'Rating', 'stremio_rating', 'trakt_rating']:
                            val = meta.get(field)
                            if not merged_meta.get(field) and val:
                                # Filter likely dummy values from catalogs (like 7 or 0)
                                try:
                                    f_val = float(val)
                                    if f_val == 0: continue
                                    # If it's a new item (likely from Cinemate), ignore the '7' placeholder
                                    if f_val == 7.0 and not meta.get('released'): continue
                                except: pass

                                merged_meta[field] = val
                                xbmc.log(f'[AIOStreams] Preserved catalog {field}={val} for {item_id}', xbmc.LOGDEBUG)
                    else:
                        merged_meta = meta

                    media = MediaRef.from_meta(merged_meta, content_type, dependencies.origin_fingerprint)
                    if media.content_type == 'series':
                        url = dependencies.get_url(action='show_seasons', **media_action_params('show_seasons', media))
                        is_folder = True
                    else:
                        url = dependencies.get_url(
                            action='play',
                            **media_action_params(
                                'play', media, media_id=media.playback_id,
                                clearlogo=merged_meta.get('logo', ''),
                            )
                        )
                        is_folder = False

                    list_item = dependencies.create_listitem(merged_meta, media.content_type, url)
                    xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, is_folder)


                except Exception as e:
                    import traceback
                    xbmc.log(f'[AIOStreams] smart_widget: Failed to add item: {e}', xbmc.LOGDEBUG)
                    continue
            # Set NumItems property for the skin
            count_prop = f"AIOStreams.{page}.{index}.NumItems"
            item_count = len(catalog_data["metas"])
            xbmcgui.Window(10000).setProperty(count_prop, str(item_count))
            xbmc.log(f"[AIOStreams] smart_widget: Set {count_prop} = {item_count}", xbmc.LOGDEBUG)


            xbmcplugin.endOfDirectory(dependencies.handle)
            return

        else:
            xbmc.log(f'[AIOStreams] smart_widget: Unknown action "{action}"', xbmc.LOGWARNING)
            xbmcplugin.endOfDirectory(dependencies.handle)
            return

    except Exception as e:
        xbmc.log(f'[AIOStreams] smart_widget: Error: {e}', xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(dependencies.handle)


def configured_widget(params, dependencies):
    """
    Dynamic widget content from widget_config.json

    URL Parameters:
        index: Widget index (0, 1, 2, ...)
        page: 'home', 'tvshows', or 'movies'

    Returns:
        Widget content based on configuration
    """
    from resources.lib.widget_config_loader import get_widget_at_index

    index = int(params.get('index', 0))
    page = params.get('page', 'home')

    # Optimization: If Search Dialog (1112) or Info Dialog (12003) OR ANY MODAL is open, skip background widget loading
    if xbmc.getCondVisibility('Window.IsVisible(1112)') or xbmc.getCondVisibility('Window.IsVisible(12003)') or xbmc.getCondVisibility('System.HasModalDialog'):
        xbmc.log(f'[AIOStreams] configured_widget: Skipping background load (Dialog Open) - index={index}', xbmc.LOGDEBUG)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return

    xbmc.log(f'[AIOStreams] configured_widget: index={index}, page={page}', xbmc.LOGINFO)

    # Get the configured widget
    widget = get_widget_at_index(page, index)

    if not widget:
        xbmc.log(f'[AIOStreams] configured_widget: No widget configured at index {index} for {page}', xbmc.LOGDEBUG)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return

    # Extract widget details
    label = widget.get('label', 'Unknown')
    path = widget.get('path', '')
    widget_type = widget.get('type', 'unknown')
    is_trakt = widget.get('is_trakt', False)

    xbmc.log(f'[AIOStreams] configured_widget: Loading "{label}" (type: {widget_type}, is_trakt: {is_trakt})', xbmc.LOGINFO)

    # Parse the widget path to extract action and parameters
    try:
        if '?' in path:
            path_parts = path.split('?')
            query_string = path_parts[1] if len(path_parts) > 1 else ''
            widget_params = dict(parse_qsl(query_string))
            action = widget_params.get('action', '')

            xbmc.log(f'[AIOStreams] configured_widget: Redirecting to action "{action}"', xbmc.LOGDEBUG)

            # Route to the appropriate action
            if action == 'trakt_next_up':
                return dependencies.dispatch_action('trakt_next_up',
                    dict(widget_params, page=page, index=index)
                )
            elif action == 'trakt_watchlist':
                media_type = widget_params.get('media_type', 'movies')
                return dependencies.dispatch_action('trakt_watchlist',
                    dict(widget_params, media_type=media_type, page=page, index=index)
                )
            elif action == 'browse_catalog':
                # Browse a specific catalog
                catalog_id = widget_params.get('catalog_id', '')
                content_type = widget_params.get('content_type', 'movie')
                catalog_name = widget_params.get('catalog_name', label)

                # Set the window property for the header
                try:
                    xbmcgui.Window(10000).setProperty(f'{page}_widget_{index}_name', catalog_name)
                except:
                    pass

                # Fetch catalog content
                catalog_data = dependencies.get_catalog(content_type, catalog_id, genre=None, skip=0)

                if not catalog_data or 'metas' not in catalog_data:
                    xbmc.log(f'[AIOStreams] configured_widget: No content in catalog {catalog_id}', xbmc.LOGWARNING)
                    xbmcplugin.endOfDirectory(dependencies.handle)
                    return

                # Set plugin metadata
                xbmcplugin.setPluginCategory(dependencies.handle, catalog_name)
                xbmcplugin.setContent(dependencies.handle, 'tvshows' if content_type == 'series' else 'movies')

                # Add items
                for meta in catalog_data['metas']:
                    media = MediaRef.from_meta(meta, content_type, dependencies.origin_fingerprint)
                    if not media.navigation_id:
                        continue

                    # For series: navigate to show
                    if media.content_type == 'series':
                        url = dependencies.get_url(action='show_seasons', **media_action_params('show_seasons', media))
                        is_folder = True
                    else:
                        url = dependencies.get_url(
                            action='play',
                            **media_action_params(
                                'play', media, media_id=media.playback_id,
                                clearlogo=meta.get('logo', ''),
                            )
                        )
                        is_folder = False

                    list_item = dependencies.create_listitem(meta, media.content_type, url)
                    xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, is_folder)

                xbmcplugin.endOfDirectory(dependencies.handle)
                return
            else:
                xbmc.log(f'[AIOStreams] configured_widget: Unknown action "{action}"', xbmc.LOGWARNING)
                xbmcplugin.endOfDirectory(dependencies.handle)
                return
        else:
            xbmc.log(f'[AIOStreams] configured_widget: Invalid widget path "{path}"', xbmc.LOGERROR)
            xbmcplugin.endOfDirectory(dependencies.handle)
            return
    except Exception as e:
        xbmc.log(f'[AIOStreams] configured_widget: Error processing widget: {e}', xbmc.LOGERROR)
        import traceback
        xbmc.log(traceback.format_exc(), xbmc.LOGERROR)
        xbmcplugin.endOfDirectory(dependencies.handle)
        return


@dataclass(frozen=True)
class InfoDependencies:
    get_meta: object
    get_url: object
    create_listitem: object
    clear_window_properties: object
    origin_fingerprint: object = None


def action_info(params, dependencies):
    """Handle info action."""
    meta_id = params.get('id') or params.get('imdb_id')
    content_type = params.get('content_type', 'movie')

    if not meta_id:
        xbmc.log('[AIOStreams] action_info: No ID provided', xbmc.LOGERROR)
        return

    xbmc.log(f'[AIOStreams] Fetching info for {content_type}/{meta_id}', xbmc.LOGINFO)

    # Clear stale properties first to avoid flash of old content
    dependencies.clear_window_properties(['InfoWindow.Title', 'InfoWindow.Plot', 'InfoWindow.Director',
                           'InfoWindow.Writer', 'InfoWindow.Cast', 'InfoWindow.Duration',
                           'InfoWindow.Year', 'InfoWindow.Genre', 'InfoWindow.Rating',
                           'InfoWindow.Votes', 'InfoWindow.Trailer', 'InfoWindow.IsCustom'])

    # Show busy dialog while fetching
    xbmc.executebuiltin('ActivateWindow(busydialog)')

    try:
        # Fetch metadata
        result = dependencies.get_meta(content_type, meta_id)

        if not result or 'meta' not in result:
            xbmc.executebuiltin('Dialog.Close(busydialog)')
            xbmcgui.Dialog().notification('AIOStreams', 'Metadata not found', xbmcgui.NOTIFICATION_ERROR)
            return

        meta = result['meta']

        # Create list item with full context
        # We need a dummy URL since we aren't playing it immediately, but it might be used for Play button in dialog
        media = MediaRef.from_meta(meta, content_type, dependencies.origin_fingerprint)
        play_url = dependencies.get_url(action='play', **media_action_params('play', media))
        list_item = dependencies.create_listitem(meta, media.content_type, play_url)

        # Close busy dialog
        xbmc.executebuiltin('Dialog.Close(busydialog)')

        # Open Info Dialog
        # Note: We can't easily "push" a List Item to the standard DialogVideoInfo.
        # However, we can use the 'open_info_dialog' helper pattern if available, or extended script.
        # But a trick is to open a hidden directory containing this item and trigger Info? No.

        # Now open the dialog.
        # Set properties BEFORE opening window to ensure they are available on load
        window = xbmcgui.Window(10000)
        window.setProperty('InfoWindow.IsCustom', 'true')
        window.setProperty('InfoWindow.IMDB', meta_id)
        window.setProperty('InfoWindow.Title', meta.get('name', ''))
        window.setProperty('InfoWindow.Plot', meta.get('description', ''))
        window.setProperty('InfoWindow.Year', str(meta.get('year', '')))
        window.setProperty('InfoWindow.Director', meta.get('director', ''))
        window.setProperty('InfoWindow.Premiered', meta.get('released', '').split('T')[0] if meta.get('released') else "")
        window.setProperty('InfoWindow.DBType', content_type)
        window.setProperty('InfoWindow.Poster', meta.get('poster', ''))
        window.setProperty('InfoWindow.Fanart', meta.get('background', ''))

        # Add Rating to InfoWindow (matches the property we set for list items)
        imdb_rating = meta.get('imdbRating') or meta.get('rating') or meta.get('Rating') or ''
        try:
            val = float(imdb_rating)
            window.setProperty('InfoWindow.Rating', f"{val:.1f}")
        except:
            window.setProperty('InfoWindow.Rating', "")

        # Add Genre to InfoWindow
        genres_data = meta.get('genres', [])
        if isinstance(genres_data, list):
            genre_str = ' | '.join([str(g.get('name') if isinstance(g, dict) else g) for g in genres_data])
        else:
            genre_str = str(genres_data)
        window.setProperty('InfoWindow.Genre', genre_str)

        # Add cast members (up to 12) for the skin chips
        info_tag = list_item.getVideoInfoTag()
        actors = info_tag.getCast() or []
        for i in range(1, 13):
            if i <= len(actors):
                actor = actors[i-1]
                window.setProperty(f'InfoWindow.Cast.{i}.Name', actor.name if hasattr(actor, 'name') else str(actor))
                window.setProperty(f'InfoWindow.Cast.{i}.Role', actor.role if hasattr(actor, 'role') else "")
                window.setProperty(f'InfoWindow.Cast.{i}.Thumb', actor.thumbnail if hasattr(actor, 'thumbnail') else "")
            else:
                window.clearProperty(f'InfoWindow.Cast.{i}.Name')
                window.clearProperty(f'InfoWindow.Cast.{i}.Role')
                window.clearProperty(f'InfoWindow.Cast.{i}.Thumb')

        # Duration handling
        try:
            runtime = meta.get('runtime', 0)
            if isinstance(runtime, int):
                window.setProperty('InfoWindow.Duration', str(runtime))
            else:
                 window.setProperty('InfoWindow.Duration', str(runtime).replace('min', '').strip())
        except:
            pass

        # Now open the dialog.
        xbmc.sleep(100)
        xbmc.executebuiltin('ActivateWindow(12003)') # DialogVideoInfo

    except Exception as e:
        xbmc.executebuiltin('Dialog.Close(busydialog)')
        xbmc.log(f'[AIOStreams] action_info error: {e}', xbmc.LOGERROR)
