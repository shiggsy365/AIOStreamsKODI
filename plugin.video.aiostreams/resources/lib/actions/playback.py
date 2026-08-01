"""Stream selection and Kodi playback actions."""
from dataclasses import dataclass
import json
import threading

import xbmc
import xbmcgui
import xbmcplugin

from ..media import MediaRef
from ..stream_utils import matching_episode_id


@dataclass(frozen=True)
class PlaybackDependencies:
    """Collaborators owned by the plugin entry point."""

    handle: int
    has_modules: bool
    get_setting: object
    get_meta: object
    get_streams: object
    get_subtitles: object
    filter_subtitles: object
    download_subtitle: object
    show_no_playable_streams: object
    get_player: object
    get_stream_manager: object
    get_max_streams: object
    show_source_dialog: object
    origin_fingerprint: object = None


def _media_params(params):
    """Read new explicit routes and the historical overloaded route shape.

    Older URLs put the playback ID in ``imdb_id``.  New URLs keep it in
    ``media_id`` and reserve ``imdb_id`` for Trakt/scrobbling.
    """
    content_type = params.get('content_type', 'movie')
    imdb_id = params.get('imdb_id', '')
    meta_id = params.get('meta_id', '')
    season = params.get('season') if content_type != 'movie' else None
    episode = params.get('episode') if content_type != 'movie' else None
    media_id = params.get('media_id', '')
    if not media_id:
        # Compatibility with legacy URLs.  Prefer the old imdb_id value even
        # when it is an opaque stream identifier, then retain the old episode
        # derivation as a final fallback.
        if content_type != 'movie' and season is not None and episode is not None:
            media_id = f'{imdb_id or meta_id}:{season}:{episode}'
        else:
            media_id = imdb_id or meta_id
    return content_type, meta_id, imdb_id, media_id, season, episode


def _add_subtitles(list_item, content_type, media_id, dependencies):
    subtitle_data = dependencies.get_subtitles(content_type, media_id)
    if not subtitle_data or not subtitle_data.get('subtitles'):
        return
    paths = []
    for subtitle in dependencies.filter_subtitles(subtitle_data['subtitles']):
        url = subtitle.get('url')
        if url:
            paths.append(dependencies.download_subtitle(
                url, subtitle.get('lang', 'unknown'), media_id, subtitle.get('id')
            ))
    if paths:
        list_item.setSubtitles(paths)


def _episode_scrobble_id(imdb_id, season, episode):
    if not season or not episode:
        return imdb_id
    try:
        from resources.lib.database.trakt_sync import TraktSyncDatabase
        database = TraktSyncDatabase()
        show = database.fetchone('SELECT trakt_id FROM shows WHERE imdb_id=?', (imdb_id,))
        if show:
            item = database.fetchone(
                'SELECT imdb_id FROM episodes WHERE show_trakt_id=? AND season=? AND episode=?',
                (show['trakt_id'], int(season), int(episode)),
            )
            if item and item['imdb_id']:
                return item['imdb_id']
    except Exception as error:
        xbmc.log(f'[AIOStreams] Unable to resolve episode IMDb ID: {error}', xbmc.LOGWARNING)
    return imdb_id


def _set_media_info(content_type, imdb_id, season, episode, dependencies):
    if not dependencies.has_modules:
        return
    player = dependencies.get_player()
    if player:
        player.set_media_info(
            'movie' if content_type == 'movie' else 'episode',
            imdb_id if content_type == 'movie' else _episode_scrobble_id(imdb_id, season, episode),
            season,
            episode,
        )


def _play_item(stream_url, content_type, media_id, imdb_id, season, episode, dependencies, direct=False):
    list_item = xbmcgui.ListItem(path=stream_url)
    list_item.setProperty('IsPlayable', 'true')
    _add_subtitles(list_item, content_type, media_id, dependencies)
    _set_media_info(content_type, imdb_id, season, episode, dependencies)
    if direct:
        xbmc.Player().play(stream_url, list_item)
        return True
    xbmcplugin.setResolvedUrl(dependencies.handle, True, list_item)
    return True


def _filtered_streams(stream_data, dependencies):
    if not dependencies.has_modules:
        return stream_data.get('streams', [])
    manager = dependencies.get_stream_manager()
    return manager.sort_streams(manager.filter_by_quality(stream_data.get('streams', [])))[:dependencies.get_max_streams()]


def _select_stream(streams, title, poster, fanart, clearlogo, plot, dependencies):
    if dependencies.has_modules:
        try:
            selected, _stream = dependencies.show_source_dialog(
                streams=streams, title=title or 'Select Stream', fanart=fanart,
                poster=poster, clearlogo=clearlogo, plot=plot,
            )
            return selected
        except Exception as error:
            xbmc.log(f'[AIOStreams] Custom stream dialog failed: {error}', xbmc.LOGERROR)
    return xbmcgui.Dialog().select(
        f'Select Stream ({len(streams)} available)',
        [xbmcgui.ListItem(label=(stream.get('name', 'Unknown Stream') + ' ' + stream.get('description', '')).strip()) for stream in streams],
        useDetails=False,
    )


def _show_dialog(content_type, media_id, stream_data, title, poster, fanart, clearlogo, plot, dependencies,
                 from_playable=False, imdb_id=None, season=None, episode=None):
    streams = _filtered_streams(stream_data, dependencies)
    if not streams:
        xbmcgui.Dialog().notification('AIOStreams', 'No streams match your quality preferences', xbmcgui.NOTIFICATION_ERROR)
        if not from_playable:
            xbmcplugin.endOfDirectory(dependencies.handle, succeeded=False)
        return None
    selected = _select_stream(streams, title, poster, fanart, clearlogo, plot, dependencies)
    if selected < 0:
        if not from_playable:
            xbmcplugin.endOfDirectory(dependencies.handle, succeeded=False)
        return None
    stream_data = dict(stream_data, streams=streams)
    if dependencies.has_modules:
        dependencies.get_stream_manager().record_stream_selection(streams[selected].get('name', ''))
    success = play_stream_by_index(
        content_type, media_id, stream_data, selected, dependencies,
        use_player=not from_playable, imdb_id=imdb_id, season=season, episode=episode,
    )
    if success:
        return success
    for index in range(selected + 1, len(streams)):
        if play_stream_by_index(
            content_type, media_id, stream_data, index, dependencies,
            use_player=not from_playable, imdb_id=imdb_id, season=season, episode=episode,
        ):
            return True
    xbmcgui.Dialog().notification('AIOStreams', 'All streams failed', xbmcgui.NOTIFICATION_ERROR)
    return False


def play(params, dependencies):
    """Respect the configured default stream-selection behavior."""
    xbmc.executebuiltin('Dialog.Close(busydialog)')
    content_type, meta_id, imdb_id, media_id, season, episode = _media_params(params)
    title = params.get('title', 'Unknown' if content_type == 'movie' else f'S{season}E{episode}')
    poster, fanart, clearlogo = (params.get('poster', ''), params.get('fanart', ''), params.get('clearlogo', ''))
    requested_media_id = media_id
    metadata_id = meta_id or imdb_id or media_id
    if not poster or not fanart or not clearlogo or (not params.get('media_id') and not imdb_id.startswith('tt')):
        metadata = dependencies.get_meta(content_type, metadata_id)
        if metadata and metadata.get('meta'):
            meta = metadata['meta']
            media_ref = MediaRef.from_meta(meta, content_type, dependencies.origin_fingerprint)
            canonical_id = media_ref.playback_id or media_id
            media_id = canonical_id if content_type == 'movie' else (params.get('media_id') or matching_episode_id(meta, canonical_id, season, episode))
            imdb_id = imdb_id or media_ref.imdb_id or ''
            poster, fanart, clearlogo = poster or meta.get('poster', ''), fanart or meta.get('background', ''), clearlogo or meta.get('logo', '')
            if media_id != requested_media_id:
                xbmc.log(f'[AIOStreams] Resolved canonical stream ID: type={content_type}, id={media_id}', xbmc.LOGINFO)
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams', 'Scraping streams...')
    progress_closed = False
    try:
        progress.update(25, 'Scraping streams...')
        stream_data = dependencies.get_streams(content_type, media_id)
        if not stream_data or not stream_data.get('streams'):
            dependencies.show_no_playable_streams(stream_data, resolve=True)
            return None
        forced = params.get('force_autoplay') == 'true' or params.get('action') in ('play_next', 'play_next_source', 'play_first')
        if dependencies.get_setting('default_behavior', 'show_streams') == 'show_streams' and not forced:
            # Kodi will refuse the source selector while DialogProgress remains
            # modal. Close it before yielding to the selector window.
            progress.close()
            progress_closed = True
            xbmc.sleep(200)
            xbmc.executebuiltin('Dialog.Close(busydialog)')
            xbmc.sleep(100)
            return _show_dialog(
                content_type, media_id, stream_data, title, poster, fanart, clearlogo,
                params.get('plot', ''), dependencies, from_playable=True, imdb_id=imdb_id,
                season=season, episode=episode,
            )
        stream = stream_data['streams'][0]
        stream_url = stream.get('_playback_url', '')
        if not stream_url:
            xbmcgui.Dialog().notification('AIOStreams', 'No playable URL found', xbmcgui.NOTIFICATION_ERROR)
            return None
        _save_retry_context(stream_data['streams'], content_type, imdb_id, season, episode, title, poster, fanart, clearlogo)
        return _play_item(stream_url, content_type, media_id, imdb_id, season, episode, dependencies, direct=dependencies.handle < 0)
    except Exception as error:
        xbmc.log(f'[AIOStreams] Play error: {error}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', f'Playback error: {error}', xbmcgui.NOTIFICATION_ERROR)
        return None
    finally:
        if not progress_closed:
            progress.close()


def play_first(params, dependencies):
    """Always direct-play the first available stream for TMDBHelper."""
    xbmc.executebuiltin('Dialog.Close(busydialog)')
    if dependencies.handle >= 0:
        xbmcplugin.setResolvedUrl(dependencies.handle, False, xbmcgui.ListItem())
    content_type, _meta_id, imdb_id, media_id, season, episode = _media_params(params)
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams', 'Scraping streams...')
    try:
        stream_data = dependencies.get_streams(content_type, media_id)
        if not stream_data or not stream_data.get('streams'):
            dependencies.show_no_playable_streams(stream_data, resolve=True)
            return None
        url = stream_data['streams'][0].get('_playback_url', '')
        if not url:
            xbmcgui.Dialog().notification('AIOStreams', 'No playable URL found', xbmcgui.NOTIFICATION_ERROR)
            return None
        return _play_item(url, content_type, media_id, imdb_id, season, episode, dependencies, direct=True)
    except Exception as error:
        xbmc.log(f'[AIOStreams] Play first error: {error}', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', f'Playback error: {error}', xbmcgui.NOTIFICATION_ERROR)
        return None
    finally:
        progress.close()


def select_stream(params, dependencies):
    """Always show stream selection for a resolver request."""
    xbmc.executebuiltin('Dialog.Close(busydialog)')
    if dependencies.handle >= 0:
        xbmcplugin.setResolvedUrl(dependencies.handle, False, xbmcgui.ListItem())
    content_type, meta_id, imdb_id, media_id, season, episode = _media_params(params)
    title, poster, fanart, clearlogo = (params.get('title', ''), params.get('poster', ''), params.get('fanart', ''), params.get('clearlogo', ''))
    progress = xbmcgui.DialogProgress()
    progress.create('AIOStreams', 'Fetching metadata...')
    try:
        plot = params.get('plot', '')
        if not poster or not fanart or not clearlogo:
            metadata = dependencies.get_meta(content_type, meta_id or imdb_id or media_id)
            if metadata and metadata.get('meta'):
                meta = metadata['meta']
                title, poster, fanart, clearlogo = title or meta.get('name', ''), poster or meta.get('poster', ''), fanart or meta.get('background', ''), clearlogo or meta.get('logo', '')
                plot = plot or meta.get('description', '')
        stream_data = dependencies.get_streams(content_type, media_id)
    finally:
        progress.close()
    if not stream_data or not stream_data.get('streams'):
        return dependencies.show_no_playable_streams(stream_data)
    return _show_dialog(
        content_type, media_id, stream_data, title, poster, fanart, clearlogo,
        plot or xbmc.getInfoLabel('ListItem.Plot'), dependencies, imdb_id=imdb_id,
        season=season, episode=episode,
    )


def play_stream_by_index(content_type, media_id, stream_data, index, dependencies, use_player=False,
                         imdb_id=None, season=None, episode=None):
    """Play a selected stream and return whether Kodi accepted the handoff."""
    streams = stream_data.get('streams', [])
    if index < 0 or index >= len(streams):
        xbmcgui.Dialog().notification('AIOStreams', 'Invalid stream index', xbmcgui.NOTIFICATION_ERROR)
        return False
    url = streams[index].get('_playback_url', '')
    if not url:
        xbmcgui.Dialog().notification('AIOStreams', 'No playable URL found', xbmcgui.NOTIFICATION_ERROR)
        if not use_player:
            xbmcplugin.setResolvedUrl(dependencies.handle, False, xbmcgui.ListItem())
        return False
    if imdb_id is None:
        imdb_id, season, episode = media_id, None, None
        if content_type == 'series' and ':' in media_id:
            imdb_id, season, episode = (media_id.split(':') + [None, None])[:3]
    if not use_player:
        return _play_item(url, content_type, media_id, imdb_id, season, episode, dependencies)

    _play_item(url, content_type, media_id, imdb_id, season, episode, dependencies, direct=True)
    player = xbmc.Player()
    monitor = xbmc.Monitor()
    started = False
    for _ in range(300):
        if monitor.abortRequested():
            return False
        if player.isPlayingVideo():
            started = True
            break
        monitor.waitForAbort(0.1)
    if dependencies.has_modules:
        dependencies.get_stream_manager().record_stream_result(url, started)
    if not started:
        xbmc.log('[AIOStreams] Stream playback timeout after 30 seconds', xbmc.LOGWARNING)
        return False
    duration = player.getTotalTime()
    if duration and duration < 95:
        player.stop()
        if dependencies.has_modules:
            dependencies.get_stream_manager().record_stream_result(url, False)
        return False
    return True


def play_next(params, dependencies):
    """Use normal playback with the explicit next-episode context."""
    return play(dict(params, force_autoplay='true'), dependencies)


def play_next_source(params, dependencies):
    """Retry sequentially from the stream context saved for the active player."""
    window = xbmcgui.Window(10000)
    try:
        saved = json.loads(window.getProperty('AIOStreams.StreamList'))
        metadata = json.loads(window.getProperty('AIOStreams.StreamMetadata'))
        current = int(window.getProperty('AIOStreams.StreamIndex') or '0')
    except (TypeError, ValueError, json.JSONDecodeError):
        saved, metadata, current = [], {}, 0
    if not isinstance(saved, list) or not isinstance(metadata, dict):
        saved = []
    content_type, imdb_id = metadata.get('content_type', 'movie'), metadata.get('imdb_id', '')
    media_id = imdb_id if content_type == 'movie' else f"{imdb_id}:{metadata.get('season')}:{metadata.get('episode')}"
    streams = [{'_playback_url': item.get('url', '')} for item in saved if isinstance(item, dict) and item.get('url')]
    if not imdb_id or current >= len(streams) - 1:
        xbmcgui.Dialog().notification('AIOStreams', 'No alternate streams are available', xbmcgui.NOTIFICATION_INFO)
        return None
    for index in range(current + 1, len(streams)):
        window.setProperty('AIOStreams.StreamIndex', str(index))
        if play_stream_by_index(content_type, media_id, {'streams': streams}, index, dependencies, use_player=True):
            return True
    xbmcgui.Dialog().notification('AIOStreams', 'All alternate streams failed', xbmcgui.NOTIFICATION_ERROR)
    return None


def _save_retry_context(streams, content_type, imdb_id, season, episode, title, poster, fanart, clearlogo):
    try:
        window = xbmcgui.Window(10000)
        window.setProperty('AIOStreams.StreamList', json.dumps([
            {'url': stream.get('_playback_url', ''), 'title': stream.get('title', ''), 'source': stream.get('source', '')}
            for stream in streams
        ]))
        window.setProperty('AIOStreams.StreamIndex', '0')
        window.setProperty('AIOStreams.StreamMetadata', json.dumps({
            'content_type': content_type, 'imdb_id': imdb_id, 'season': season, 'episode': episode,
            'title': title, 'poster': poster, 'fanart': fanart, 'clearlogo': clearlogo,
        }))
    except Exception as error:
        xbmc.log(f'[AIOStreams] Failed to save stream retry context: {error}', xbmc.LOGWARNING)
