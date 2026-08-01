"""Search actions with explicit, parsed parameters and dependencies."""
from dataclasses import dataclass

import xbmc
import xbmcgui
import xbmcplugin

from ..items import media_action_params
from ..media import MediaRef


@dataclass(frozen=True)
class SearchDependencies:
    """The narrow add-on services required to render search results."""

    handle: int
    has_modules: bool
    filters: object
    search_catalog: object
    get_url: object
    create_listitem: object
    origin_fingerprint: object = None


def _set_background_suppression(active):
    """Pause background work while a foreground search is loading."""
    try:
        window = xbmcgui.Window(10000)
        if active:
            window.setProperty('AIOStreams.InternalSearchActive', 'true')
            xbmc.executebuiltin('Skin.ClearString(WidgetReloadToken)')
            from service import get_task_queue
            get_task_queue().clear()
            xbmc.log('[AIOStreams] Internal Search started', xbmc.LOGINFO)
        else:
            window.clearProperty('AIOStreams.InternalSearchActive')
            xbmc.executebuiltin('Skin.ClearString(WidgetReloadToken)')
            xbmc.log('[AIOStreams] Internal Search finished', xbmc.LOGDEBUG)
    except Exception as error:
        xbmc.log(f'[AIOStreams] Error managing background tasks: {error}', xbmc.LOGDEBUG)


def _filter_items(items, dependencies):
    if dependencies.has_modules and dependencies.filters:
        return dependencies.filters.filter_items(items)
    return items


def search(params, dependencies):
    """Render one movie, show, video, or combined result set."""
    _set_background_suppression(True)
    try:
        return _search(params, dependencies)
    finally:
        _set_background_suppression(False)


def _search(params, dependencies):
    content_type = params.get('content_type', 'both')
    query = params.get('query', '').strip()
    skip = int(params.get('skip', 0))
    window = xbmcgui.Window(10000)

    if not query:
        query = xbmcgui.Dialog().input('Search', type=xbmcgui.INPUT_ALPHANUM)
        if not query:
            xbmcplugin.endOfDirectory(dependencies.handle, succeeded=False)
            return None
        query = query.strip()

    if content_type == 'both' and skip == 0:
        return search_all_results(query, dependencies)

    xbmcplugin.setPluginCategory(dependencies.handle, f'Search {content_type.title()}: {query}')
    xbmcplugin.setContent(
        dependencies.handle, 'movies' if content_type == 'movie' else 'tvshows'
    )
    progress = xbmcgui.DialogProgress()
    content_label = 'TV shows' if content_type == 'series' else f'{content_type}s'
    progress.create('AIOStreams', f'Searching {content_label}...')
    results = dependencies.search_catalog(query, content_type, skip=skip)
    progress.close()

    if not results or not results.get('metas'):
        _set_result_count(window, content_type, 0)
        xbmc.log(f'[AIOStreams] Search returned no results for "{query}"', xbmc.LOGINFO)
        xbmcplugin.endOfDirectory(dependencies.handle, succeeded=True)
        return None

    _set_result_count(window, content_type, len(results['metas']))
    items = _filter_items(results['metas'], dependencies)
    for meta in items:
        _add_result(meta, content_type, dependencies)

    if len(results['metas']) >= 20:
        next_skip = skip + 20
        list_item = xbmcgui.ListItem(label='[COLOR yellow]» Load More...[/COLOR]')
        url = dependencies.get_url(
            action='search', content_type=content_type, query=query, skip=next_skip
        )
        xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, True)
    xbmcplugin.endOfDirectory(dependencies.handle)
    return None


def _set_result_count(window, content_type, count):
    if content_type == 'movie':
        window.setProperty('GlobalSearch.MoviesCount', str(count))
    elif content_type in ('tvshows', 'series'):
        window.setProperty('GlobalSearch.SeriesCount', str(count))
    elif content_type in ('video', 'youtube') or 'youtube' in str(content_type):
        window.setProperty('GlobalSearch.YoutubeCount', str(count))


def _add_result(meta, content_type, dependencies):
    item_type = 'video' if content_type in ('video', 'youtube') else meta.get('type', content_type)
    media = MediaRef.from_meta(meta, item_type, dependencies.origin_fingerprint)
    item_type = media.content_type
    if item_type == 'series':
        url = dependencies.get_url(
            action='show_seasons', **media_action_params('show_seasons', media)
        )
        is_folder = True
    elif content_type in ('video', 'youtube') or 'youtube' in str(item_type):
        item_url = meta.get('url', '')
        item_name = meta.get('name', '')
        is_youtube_folder = (
            '/channel/' in item_url or '/playlist/' in item_url or
            'Channels' in item_name or 'Playlists' in item_name or
            meta.get('mediatype') in ('channel', 'playlist')
        )
        if is_youtube_folder:
            if not xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)'):
                return
            url = dependencies.get_url(action='open_youtube_folder', url=item_url or meta.get('id', ''))
            is_folder = False
        else:
            url = dependencies.get_url(
                action='play', **media_action_params('play', media, clearlogo=meta.get('logo', ''))
            )
            is_folder = False
    else:
        url = dependencies.get_url(
            action='play', **media_action_params('play', media, clearlogo=meta.get('logo', ''))
        )
        is_folder = False

    list_item = dependencies.create_listitem(meta, item_type, url)
    if not is_folder:
        list_item.setProperty('IsPlayable', 'true')
    xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, is_folder)


def search_all_results(query, dependencies):
    """Render combined movie and show results in a single directory."""
    xbmcplugin.setPluginCategory(dependencies.handle, f'Search: {query}')
    xbmcplugin.setContent(dependencies.handle, 'videos')
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams', 'Searching movies and TV shows...')
    progress.update(25, 'Searching movies...')
    movie_results = dependencies.search_catalog(query, 'movie', skip=0)
    progress.update(50, 'Searching TV shows...')
    series_results = dependencies.search_catalog(query, 'series', skip=0)
    progress.close()

    movies = _filter_items((movie_results or {}).get('metas', []), dependencies)
    for meta in movies[:10]:
        _add_result(meta, 'movie', dependencies)
    if len(movies) > 10:
        list_item = xbmcgui.ListItem(
            label=f'[COLOR yellow]   » View All Movies ({len(movies)} results)[/COLOR]'
        )
        url = dependencies.get_url(action='search', content_type='movie', query=query)
        xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, True)

    shows = _filter_items((series_results or {}).get('metas', []), dependencies)
    for meta in shows[:10]:
        _add_result(meta, 'series', dependencies)
    if len(shows) > 10:
        list_item = xbmcgui.ListItem(
            label=f'[COLOR yellow]   » View All TV Shows ({len(shows)} results)[/COLOR]'
        )
        url = dependencies.get_url(action='search_tab', content_type='series', query=query)
        xbmcplugin.addDirectoryItem(dependencies.handle, url, list_item, True)

    if not movies and not shows:
        list_item = xbmcgui.ListItem(label=f'[COLOR red]No results found for "{query}"[/COLOR]')
        xbmcplugin.addDirectoryItem(dependencies.handle, '', list_item, False)
    xbmcplugin.endOfDirectory(dependencies.handle)
    return None
