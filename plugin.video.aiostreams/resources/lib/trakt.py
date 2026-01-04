# -*- coding: utf-8 -*-
"""Trakt.tv integration for AIOStreams"""
import xbmc
import xbmcgui
import xbmcaddon
import requests
import time
import json

ADDON = xbmcaddon.Addon()
API_ENDPOINT = 'https://api.trakt.tv'
API_VERSION = '2'


def get_client_id():
    """Get Trakt client ID from settings."""
    return ADDON.getSetting('trakt_client_id')


def get_client_secret():
    """Get Trakt client secret from settings."""
    return ADDON.getSetting('trakt_client_secret')


def get_access_token():
    """Get stored access token."""
    return ADDON.getSetting('trakt_token')


def get_refresh_token():
    """Get stored refresh token."""
    return ADDON.getSetting('trakt_refresh')


def get_token_expires():
    """Get token expiration timestamp."""
    try:
        return float(ADDON.getSetting('trakt_expires'))
    except:
        return 0.0


def save_token_data(token_data):
    """Save token data to settings."""
    ADDON.setSetting('trakt_token', token_data.get('access_token', ''))
    ADDON.setSetting('trakt_refresh', token_data.get('refresh_token', ''))
    expires_at = time.time() + token_data.get('expires_in', 7200)
    ADDON.setSetting('trakt_expires', str(expires_at))


def clear_token_data():
    """Clear all token data."""
    ADDON.setSetting('trakt_token', '')
    ADDON.setSetting('trakt_refresh', '')
    ADDON.setSetting('trakt_expires', '0')


def call_trakt(path, method='GET', data=None, params=None, with_auth=True):
    """Make authenticated request to Trakt API."""
    client_id = get_client_id()
    if not client_id:
        xbmcgui.Dialog().notification('AIOStreams', 'Trakt Client ID not set', xbmcgui.NOTIFICATION_WARNING)
        return None
    
    headers = {
        'Content-Type': 'application/json',
        'trakt-api-version': API_VERSION,
        'trakt-api-key': client_id
    }
    
    # Add authorization if needed
    if with_auth:
        # Check if token needs refresh
        if time.time() > get_token_expires():
            refresh_access_token()
        
        token = get_access_token()
        if token:
            headers['Authorization'] = f'Bearer {token}'
        elif path not in ['oauth/device/code', 'oauth/device/token']:
            xbmcgui.Dialog().notification('AIOStreams', 'Not authorized with Trakt', xbmcgui.NOTIFICATION_WARNING)
            return None
    
    url = f'{API_ENDPOINT}/{path}'
    
    try:
        if method == 'GET':
            response = requests.get(url, headers=headers, params=params, timeout=10)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data, timeout=10)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers, timeout=10)
        else:
            return None
        
        response.raise_for_status()
        
        if response.text:
            return response.json()
        return True
    
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401 and with_auth:
            # Token expired, try refresh
            refresh_access_token()
            return call_trakt(path, method, data, params, with_auth)
        xbmc.log(f'[AIOStreams] Trakt API error: {e}', xbmc.LOGERROR)
        return None
    except Exception as e:
        xbmc.log(f'[AIOStreams] Trakt request failed: {e}', xbmc.LOGERROR)
        return None


def authorize():
    """Start device authorization flow."""
    client_id = get_client_id()
    if not client_id:
        xbmcgui.Dialog().ok('AIOStreams', 'Please set Trakt Client ID in settings first')
        return False
    
    # Get device code
    device_data = call_trakt('oauth/device/code', method='POST', 
                             data={'client_id': client_id}, with_auth=False)
    
    if not device_data:
        xbmcgui.Dialog().ok('AIOStreams', 'Failed to get device code from Trakt')
        return False
    
    user_code = device_data['user_code']
    device_code = device_data['device_code']
    verification_url = device_data['verification_url']
    expires_in = device_data['expires_in']
    interval = device_data['interval']
    
    # Show code to user
    line1 = f'Go to: [B]{verification_url}[/B]'
    line2 = f'Enter code: [B]{user_code}[/B]'
    
    progress = xbmcgui.DialogProgress()
    # Kodi 21 only takes heading and message (2 args)
    progress.create('Authorize Trakt', f'{line1}\n{line2}\nWaiting for authorization...')
    
    # Poll for token
    start_time = time.time()
    while (time.time() - start_time) < expires_in:
        if progress.iscanceled():
            progress.close()
            return False
        
        # Update progress
        percent = int(((time.time() - start_time) / expires_in) * 100)
        progress.update(percent, f'{line1}\n{line2}\nWaiting for authorization...')
        
        # Check for token
        client_secret = get_client_secret()
        if not client_secret:
            progress.close()
            xbmcgui.Dialog().ok('AIOStreams', 'Please set Trakt Client Secret in settings')
            return False
        
        token_data = call_trakt('oauth/device/token', method='POST',
                                data={
                                    'code': device_code,
                                    'client_id': client_id,
                                    'client_secret': client_secret
                                }, with_auth=False)
        
        if token_data and 'access_token' in token_data:
            save_token_data(token_data)
            progress.close()
            xbmcgui.Dialog().notification('AIOStreams', 'Authorized with Trakt!', xbmcgui.NOTIFICATION_INFO)
            return True
        
        xbmc.sleep(interval * 1000)
    
    progress.close()
    xbmcgui.Dialog().ok('AIOStreams', 'Authorization timeout')
    return False


def refresh_access_token():
    """Refresh the access token."""
    refresh_token = get_refresh_token()
    if not refresh_token:
        return False
    
    client_id = get_client_id()
    client_secret = get_client_secret()
    
    if not client_id or not client_secret:
        return False
    
    token_data = call_trakt('oauth/token', method='POST',
                            data={
                                'refresh_token': refresh_token,
                                'client_id': client_id,
                                'client_secret': client_secret,
                                'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
                                'grant_type': 'refresh_token'
                            }, with_auth=False)
    
    if token_data and 'access_token' in token_data:
        save_token_data(token_data)
        return True
    
    return False


def revoke_authorization():
    """Revoke Trakt authorization."""
    token = get_access_token()
    client_id = get_client_id()
    client_secret = get_client_secret()
    
    if token and client_id and client_secret:
        call_trakt('oauth/revoke', method='POST',
                   data={
                       'token': token,
                       'client_id': client_id,
                       'client_secret': client_secret
                   }, with_auth=False)
    
    clear_token_data()
    xbmcgui.Dialog().notification('AIOStreams', 'Trakt authorization revoked', xbmcgui.NOTIFICATION_INFO)


def get_watchlist(list_type='movies', page=1, limit=20):
    """Get user's watchlist."""
    return call_trakt(f'sync/watchlist/{list_type}', params={'page': page, 'limit': limit})


def get_collection(list_type='movies', page=1, limit=20):
    """Get user's collection."""
    return call_trakt(f'sync/collection/{list_type}', params={'page': page, 'limit': limit})


def get_watched(list_type='movies', page=1, limit=20):
    """Get user's watched history."""
    return call_trakt(f'sync/watched/{list_type}', params={'page': page, 'limit': limit})


def get_trending(media_type='movies', page=1, limit=20):
    """Get trending items."""
    return call_trakt(f'{media_type}/trending', params={'page': page, 'limit': limit}, with_auth=False)


def get_popular(media_type='movies', page=1, limit=20):
    """Get popular items."""
    return call_trakt(f'{media_type}/popular', params={'page': page, 'limit': limit}, with_auth=False)


def get_show_progress(show_id):
    """Get progress for a specific show (includes next episode)."""
    return call_trakt(f'shows/{show_id}/progress/watched')


def get_hidden_shows():
    """Get list of shows user has hidden from progress."""
    result = call_trakt('users/hidden/progress_watched')
    if result:
        return [item.get('show', {}).get('ids', {}).get('trakt') for item in result]
    return []


def get_progress_watching(type='shows', page=1, limit=20):
    """Get shows/movies currently watching (continue watching)."""
    return call_trakt(f'sync/playback/{type}', params={'page': page, 'limit': limit})


def get_recommended(media_type='movies', page=1, limit=20):
    """Get personalized recommendations."""
    return call_trakt(f'recommendations/{media_type}', params={'page': page, 'limit': limit})


def get_related(media_type, item_id, page=1, limit=20):
    """Get related items (similar shows/movies)."""
    # media_type should be 'movies' or 'shows'
    api_type = 'movies' if media_type == 'movie' else 'shows'
    return call_trakt(f'{api_type}/{item_id}/related', params={'page': page, 'limit': limit}, with_auth=False)


# Cache for cast information
_cast_cache = {}

def get_cast(media_type, item_id):
    """
    Get cast and crew information from Trakt.

    Args:
        media_type: 'movie' or 'series'
        item_id: IMDB ID

    Returns:
        List of xbmc.Actor objects
    """
    # Check cache first
    cache_key = f"{media_type}:{item_id}"
    if cache_key in _cast_cache:
        return _cast_cache[cache_key]

    # media_type should be 'movies' or 'shows'
    api_type = 'movies' if media_type == 'movie' else 'shows'

    result = call_trakt(f'{api_type}/{item_id}/people', with_auth=False)

    if not result:
        return []

    # Format cast for Kodi - expects list of xbmc.Actor objects
    cast_list = []

    # Get actors from cast
    cast_data = result.get('cast', [])
    for person in cast_data:
        person_info = person.get('person', {})
        character = person.get('character', '')
        name = person_info.get('name', '')

        # Get thumbnail if available
        thumbnail = ''
        images = person_info.get('images', {})
        if images and isinstance(images, dict):
            headshot = images.get('headshot', {})
            # headshot can be a dict or list, only process if it's a dict
            if headshot and isinstance(headshot, dict):
                thumbnail = headshot.get('full') or headshot.get('medium') or headshot.get('thumb') or ''

        # Create xbmc.Actor object
        actor = xbmc.Actor(name, character, len(cast_list), thumbnail)
        cast_list.append(actor)

        # Limit to top 20 cast members for performance
        if len(cast_list) >= 20:
            break

    # Cache the result
    _cast_cache[cache_key] = cast_list

    return cast_list


def hide_show_from_progress(show_id):
    """Hide a show from progress/recommendations."""
    data = {
        'shows': [{'ids': {'trakt': show_id}}]
    }
    result = call_trakt('users/hidden/progress_watched', method='POST', data=data)
    if result:
        xbmcgui.Dialog().notification('AIOStreams', 'Show hidden from progress', xbmcgui.NOTIFICATION_INFO)
        return True
    return False


def scrobble(action, media_type, imdb_id, progress=0, season=None, episode=None):
    """
    Scrobble playback to Trakt.
    
    action: 'start', 'pause', 'stop'
    media_type: 'movie' or 'episode'
    imdb_id: IMDB ID
    progress: Playback progress percentage (0-100)
    season: Season number (for episodes)
    episode: Episode number (for episodes)
    """
    if not get_access_token():
        return False
    
    data = {'progress': progress}
    
    if media_type == 'movie':
        data['movie'] = {'ids': {'imdb': imdb_id}}
    else:
        data['episode'] = {'ids': {'imdb': imdb_id}}
        if season is not None and episode is not None:
            data['show'] = {'ids': {'imdb': imdb_id.split(':')[0]}}
            data['episode'] = {
                'season': int(season),
                'number': int(episode)
            }
    
    result = call_trakt(f'scrobble/{action}', method='POST', data=data)
    
    if result:
        xbmc.log(f'[AIOStreams] Scrobble {action}: {media_type} {imdb_id} at {progress}%', xbmc.LOGINFO)
        return True
    
    return False


def add_to_watchlist(media_type, imdb_id, season=None, episode=None):
    """Add item to watchlist."""
    # For episodes/shows, we use 'shows' in the API
    api_type = 'shows' if media_type in ['episode', 'show'] or season is not None else media_type + 's'

    data = {api_type: []}

    item = {'ids': {'imdb': imdb_id}}
    if season is not None:
        item['seasons'] = [{'number': season}]
        if episode is not None:
            item['seasons'][0]['episodes'] = [{'number': episode}]

    data[api_type].append(item)

    result = call_trakt('sync/watchlist', method='POST', data=data)

    if result:
        # Clear watchlist cache
        cache_key = f"{media_type}:{imdb_id}"
        if cache_key in _watchlist_cache:
            del _watchlist_cache[cache_key]

        xbmcgui.Dialog().notification('AIOStreams', 'Added to Trakt watchlist', xbmcgui.NOTIFICATION_INFO)
        return True

    return False


def remove_from_watchlist(media_type, imdb_id, season=None, episode=None):
    """Remove item from watchlist."""
    # For episodes/shows, we use 'shows' in the API
    api_type = 'shows' if media_type in ['episode', 'show'] or season is not None else media_type + 's'

    data = {api_type: []}

    item = {'ids': {'imdb': imdb_id}}
    if season is not None:
        item['seasons'] = [{'number': season}]
        if episode is not None:
            item['seasons'][0]['episodes'] = [{'number': episode}]

    data[api_type].append(item)

    result = call_trakt('sync/watchlist/remove', method='POST', data=data)

    if result:
        # Clear watchlist cache
        cache_key = f"{media_type}:{imdb_id}"
        if cache_key in _watchlist_cache:
            del _watchlist_cache[cache_key]

        xbmcgui.Dialog().notification('AIOStreams', 'Removed from Trakt watchlist', xbmcgui.NOTIFICATION_INFO)
        return True

    return False


def mark_watched(media_type, imdb_id, season=None, episode=None, playback_id=None):
    """Mark item as watched and clear any in-progress status."""
    # For episodes, we use 'shows' in the API
    api_type = 'shows' if media_type == 'episode' or season is not None else media_type + 's'

    # Add to watch history
    data = {api_type: []}

    item = {'ids': {'imdb': imdb_id}}
    if season is not None:
        item['seasons'] = [{'number': season}]
        if episode is not None:
            item['seasons'][0]['episodes'] = [{'number': episode}]

    data[api_type].append(item)

    result = call_trakt('sync/history', method='POST', data=data)

    if result:
        # Remove from playback progress if we have playback_id
        if playback_id:
            call_trakt(f'sync/playback/{playback_id}', method='DELETE')

        # Clear watched cache
        cache_key = f"{media_type}:{imdb_id}"
        if cache_key in _watched_cache:
            del _watched_cache[cache_key]
        if imdb_id in _show_progress_cache:
            del _show_progress_cache[imdb_id]

        xbmcgui.Dialog().notification('AIOStreams', 'Marked as watched on Trakt', xbmcgui.NOTIFICATION_INFO)
        return True

    return False


def mark_unwatched(media_type, imdb_id, season=None, episode=None):
    """Remove item from watch history."""
    # For episodes, we use 'shows' in the API
    api_type = 'shows' if media_type == 'episode' or season is not None else media_type + 's'

    # Remove from watch history
    data = {api_type: []}

    item = {'ids': {'imdb': imdb_id}}
    if season is not None:
        item['seasons'] = [{'number': season}]
        if episode is not None:
            item['seasons'][0]['episodes'] = [{'number': episode}]

    data[api_type].append(item)

    result = call_trakt('sync/history/remove', method='POST', data=data)

    if result:
        # Clear watched cache
        cache_key = f"{media_type}:{imdb_id}"
        if cache_key in _watched_cache:
            del _watched_cache[cache_key]
        if imdb_id in _show_progress_cache:
            del _show_progress_cache[imdb_id]

        xbmcgui.Dialog().notification('AIOStreams', 'Marked as unwatched on Trakt', xbmcgui.NOTIFICATION_INFO)
        return True

    return False


# Cache for watched status to avoid repeated API calls
_watched_cache = {}
_show_progress_cache = {}
_watchlist_cache = {}


def is_in_watchlist(media_type, imdb_id):
    """Check if item is in Trakt watchlist."""
    # Check cache first
    cache_key = f"{media_type}:{imdb_id}"
    if cache_key in _watchlist_cache:
        return _watchlist_cache[cache_key]

    # Query Trakt watchlist
    api_type = 'movies' if media_type == 'movie' else 'shows'

    # Get watchlist
    result = call_trakt(f'sync/watchlist/{api_type}')

    if not result:
        _watchlist_cache[cache_key] = False
        return False

    # Check if our IMDB ID is in the watchlist
    for item in result:
        item_data = item.get(media_type, {})
        item_imdb = item_data.get('ids', {}).get('imdb', '')
        if item_imdb == imdb_id:
            _watchlist_cache[cache_key] = True
            return True

    _watchlist_cache[cache_key] = False
    return False


def is_watched(media_type, imdb_id):
    """Check if item is watched in Trakt history."""
    # Check cache first
    cache_key = f"{media_type}:{imdb_id}"
    if cache_key in _watched_cache:
        return _watched_cache[cache_key]
    
    # Query Trakt history
    api_type = 'movies' if media_type == 'movie' else 'shows'
    
    # Get watched history (last 1000 items should be enough)
    result = call_trakt(f'sync/history/{api_type}?limit=1000')
    
    if not result:
        _watched_cache[cache_key] = False
        return False
    
    # Check if our IMDB ID is in the history
    for item in result:
        item_data = item.get(media_type, {})
        item_imdb = item_data.get('ids', {}).get('imdb', '')
        if item_imdb == imdb_id:
            _watched_cache[cache_key] = True
            return True
    
    _watched_cache[cache_key] = False
    return False


def get_show_progress(imdb_id):
    """Get show progress from Trakt (which seasons/episodes are watched)."""
    # Check cache first
    if imdb_id in _show_progress_cache:
        return _show_progress_cache[imdb_id]
    
    # Get show progress from Trakt
    result = call_trakt(f'shows/{imdb_id}/progress/watched')
    
    if result:
        _show_progress_cache[imdb_id] = result
        return result
    
    return None


def is_season_watched(imdb_id, season_num):
    """Check if entire season is watched."""
    progress = get_show_progress(imdb_id)
    if not progress:
        return False
    
    seasons = progress.get('seasons', [])
    for season in seasons:
        if season.get('number') == season_num:
            # Check if all episodes are watched
            aired = season.get('aired', 0)
            completed = season.get('completed', 0)
            return aired > 0 and aired == completed
    
    return False


def is_episode_watched(imdb_id, season_num, episode_num):
    """Check if specific episode is watched."""
    progress = get_show_progress(imdb_id)
    if not progress:
        return False
    
    seasons = progress.get('seasons', [])
    for season in seasons:
        if season.get('number') == season_num:
            episodes = season.get('episodes', [])
            for episode in episodes:
                if episode.get('number') == episode_num:
                    return episode.get('completed', False)
    
    return False
