"""Shared Kodi media presentation and navigation parameter helpers."""
from urllib.parse import urlencode

from .media import MediaRef


def plugin_url(action, **params):
    """Build a callback URL for the add-on, independent of the current script."""
    route = {'action': action}
    route.update(params)
    return 'plugin://plugin.video.aiostreams/?{}'.format(urlencode(route))


def media_action_params(action, media, **extra):
    """Return explicit route parameters for a normalized media reference."""
    media = media if isinstance(media, MediaRef) else MediaRef.from_meta(media)
    params = dict(extra)
    if action in ('show_seasons', 'show_episodes', 'browse_show'):
        params.setdefault('meta_id', media.navigation_id)
    elif action in ('play', 'play_first', 'select_stream', 'show_streams'):
        params.setdefault('content_type', media.content_type)
        params.setdefault('imdb_id', media.playback_id)
    params.setdefault('title', media.title)
    if media.poster:
        params.setdefault('poster', media.poster)
    if media.fanart:
        params.setdefault('fanart', media.fanart)
    return params


def apply_media_identity(list_item, media):
    """Expose a normalized media reference through standard Kodi item properties."""
    media = media if isinstance(media, MediaRef) else MediaRef.from_meta(media)
    list_item.setProperty('id', media.navigation_id)
    list_item.setProperty('meta_id', media.navigation_id)
    list_item.setProperty('imdb_id', media.imdb_id or '')
    list_item.setProperty('tmdb_id', media.tmdb_id or '')
    list_item.setProperty('playable_id', media.playable_id or '')
    list_item.setProperty('content_type', media.content_type)
    return list_item


def create_media_list_item(meta, media):
    """Create the common ListItem shell and expose normalized identity to skins."""
    import xbmcgui

    media = media if isinstance(media, MediaRef) else MediaRef.from_meta(meta)
    list_item = xbmcgui.ListItem(label=media.title)
    info_tag = list_item.getVideoInfoTag()
    info_tag.setTitle(media.title)
    info_tag.setPlot(meta.get('description', ''))
    apply_media_identity(list_item, media)
    return list_item, info_tag
