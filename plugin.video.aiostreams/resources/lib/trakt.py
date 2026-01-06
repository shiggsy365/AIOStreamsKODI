# -*- coding: utf-8 -*-
"""Trakt.tv integration for AIOStreams"""
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import requests
import time
import json

# Import cache module
try:
    from resources.lib import cache
    from resources.lib import utils
    HAS_MODULES = True
except:
    HAS_MODULES = False
    cache = None
    utils = None

ADDON = xbmcaddon.Addon()
API_ENDPOINT = 'https://api.trakt.tv'
API_VERSION = '2'

# Database instance (lazy loaded)
_trakt_db = None


def get_trakt_db():
    """Get or create Trakt sync database instance.
    
    Returns:
        TraktSyncDatabase instance or None if database module unavailable
    """
    global _trakt_db
    
    if _trakt_db is None:
        try:
            from resources.lib.database.trakt_sync.activities import TraktSyncDatabase
            _trakt_db = TraktSyncDatabase()
            xbmc.log('[AIOStreams] Trakt database initialized', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Failed to initialize Trakt database: {e}', xbmc.LOGERROR)
            return None
    
    return _trakt_db

# In-memory cache for batch show progress (invalidated on watched status changes)
_show_progress_batch_cache = {}
_show_progress_cache_valid = False


def invalidate_progress_cache():
    """Invalidate in-memory show progress cache.

    Clears in-memory caches. Database is the source of truth, no disk cache to clear.
    """
    global _show_progress_cache_valid, _show_progress_batch_cache, _show_progress_cache
    _show_progress_cache_valid = False
    _show_progress_batch_cache.clear()
    _show_progress_cache.clear()

    xbmc.log('[AIOStreams] Trakt progress cache invalidated (memory only)', xbmc.LOGDEBUG)


def _get_trakt_id_from_imdb(imdb_id):
    """Get Trakt ID for a show from IMDB ID, with API fallback.
    
    Checks batch cache first, then falls back to Trakt search API if needed.
    
    Args:
        imdb_id: IMDB ID (e.g., 'tt1234567')
    
    Returns:
        Trakt ID (int) or None if not found
    """
    global _show_progress_batch_cache
    
    # Fast path: Check batch cache first
    if imdb_id in _show_progress_batch_cache:
        show_data = _show_progress_batch_cache[imdb_id].get('show', {})
        trakt_id = show_data.get('ids', {}).get('trakt')
        if trakt_id:
            xbmc.log(f'[AIOStreams] Found Trakt ID {trakt_id} for {imdb_id} in batch cache', xbmc.LOGDEBUG)
            return trakt_id
    
    # Fallback: Query Trakt API to get Trakt ID from IMDB ID
    xbmc.log(f'[AIOStreams] Trakt ID not in cache for {imdb_id}, querying API', xbmc.LOGDEBUG)
    try:
        # Use Trakt search API: /search/imdb/{id}?type=show
        result = call_trakt(f'search/imdb/{imdb_id}?type=show', with_auth=False)
        if result and isinstance(result, list) and len(result) > 0:
            show_data = result[0].get('show', {})
            trakt_id = show_data.get('ids', {}).get('trakt')
            if trakt_id:
                xbmc.log(f'[AIOStreams] Found Trakt ID {trakt_id} for {imdb_id} via API', xbmc.LOGDEBUG)
                return trakt_id
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error getting Trakt ID for {imdb_id}: {e}', xbmc.LOGERROR)
    
    xbmc.log(f'[AIOStreams] Could not find Trakt ID for {imdb_id}', xbmc.LOGWARNING)
    return None


def get_all_show_progress():
    """Get progress for all shows from SQLite database.
    Falls back to API if database is unavailable.

    Returns dict of {imdb_id: show_data} for all shows with watch history.
    """
    global _show_progress_batch_cache, _show_progress_cache_valid

    # Return cached data if still valid
    if _show_progress_cache_valid and _show_progress_batch_cache:
        xbmc.log(f'[AIOStreams] Using cached show progress ({len(_show_progress_batch_cache)} shows)', xbmc.LOGDEBUG)
        return _show_progress_batch_cache

    # Try database first
    db = get_trakt_db()
    if db and db.connect():
        try:
            # Get all shows that have at least one watched episode
            shows = db.fetchall("""
                SELECT DISTINCT s.*,
                    (SELECT MAX(e.last_watched_at) FROM episodes e WHERE e.show_trakt_id = s.trakt_id AND e.watched = 1) as last_watched_at
                FROM shows s
                WHERE EXISTS (SELECT 1 FROM episodes WHERE show_trakt_id = s.trakt_id AND watched = 1)
                ORDER BY last_watched_at DESC
            """)

            _show_progress_batch_cache = {}
            for show in shows:
                imdb_id = show.get('imdb_id')
                if not imdb_id:
                    continue

                show_trakt_id = show.get('trakt_id')

                # Get watched episodes for this show to build seasons data
                episodes = db.fetchall("""
                    SELECT season, episode, watched, last_watched_at
                    FROM episodes
                    WHERE show_trakt_id = ? AND watched = 1
                    ORDER BY season, episode
                """, (show_trakt_id,))

                # Build seasons structure (similar to Trakt API format)
                seasons_dict = {}
                for ep in episodes:
                    season_num = ep.get('season', 0)
                    if season_num not in seasons_dict:
                        seasons_dict[season_num] = {
                            'number': season_num,
                            'episodes': []
                        }
                    seasons_dict[season_num]['episodes'].append({
                        'number': ep.get('episode', 0),
                        'plays': 1,
                        'last_watched_at': ep.get('last_watched_at', '')
                    })

                # Build show data structure compatible with API format
                show_data = {
                    'show': {
                        'title': show.get('title', 'Unknown'),
                        'year': None,  # Not stored in database
                        'ids': {
                            'trakt': show_trakt_id,
                            'imdb': imdb_id,
                            'tvdb': show.get('tvdb_id'),
                            'tmdb': show.get('tmdb_id'),
                            'slug': show.get('slug')
                        }
                    },
                    'seasons': list(seasons_dict.values()),
                    'last_watched_at': show.get('last_watched_at', '')
                }
                _show_progress_batch_cache[imdb_id] = show_data

            _show_progress_cache_valid = True
            xbmc.log(f'[AIOStreams] Built show progress from database for {len(_show_progress_batch_cache)} shows', xbmc.LOGDEBUG)
            return _show_progress_batch_cache

        except Exception as e:
            xbmc.log(f'[AIOStreams] Database error getting all show progress: {e}', xbmc.LOGWARNING)
        finally:
            db.disconnect()

    # Fallback to API
    xbmc.log('[AIOStreams] Database unavailable, fetching all show progress from API', xbmc.LOGDEBUG)
    try:
        watched_shows = call_trakt('sync/watched/shows')
        if not watched_shows:
            return {}

        # Build cache: {imdb_id: progress_data}
        _show_progress_batch_cache = {}
        for show in watched_shows:
            show_data = show.get('show', {})
            imdb_id = show_data.get('ids', {}).get('imdb')
            if imdb_id:
                _show_progress_batch_cache[imdb_id] = show

        _show_progress_cache_valid = True
        xbmc.log(f'[AIOStreams] Fetched and cached progress for {len(_show_progress_batch_cache)} shows from API', xbmc.LOGDEBUG)
        return _show_progress_batch_cache

    except Exception as e:
        xbmc.log(f'[AIOStreams] Error fetching batch show progress from API: {e}', xbmc.LOGERROR)
        return {}


def get_trakt_username():
    """Get current Trakt username from settings or API."""
    # Try to get from settings first
    username = ADDON.getSetting('trakt.username')
    if username:
        return username
    
    # If not in settings, fetch from Trakt API and cache it
    if get_access_token():
        try:
            user_settings = call_trakt('users/settings', with_auth=True)
            if user_settings and 'user' in user_settings:
                username = user_settings['user'].get('username', '')
                if username:
                    ADDON.setSetting('trakt.username', username)
                    return username
        except Exception as e:
            xbmc.log(f'[AIOStreams] Failed to get Trakt username: {e}', xbmc.LOGERROR)
    
    return ''


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


def call_trakt(path, method='GET', data=None, params=None, with_auth=True, extra_headers=None):
    """Make authenticated request to Trakt API.

    Args:
        extra_headers: Optional dict of additional headers (e.g., {'X-Start-Date': '2024-01-01T00:00:00Z'})
    """
    client_id = get_client_id()
    if not client_id:
        xbmcgui.Dialog().notification('AIOStreams', 'Trakt Client ID not set', xbmcgui.NOTIFICATION_WARNING)
        return None

    headers = {
        'Content-Type': 'application/json',
        'trakt-api-version': API_VERSION,
        'trakt-api-key': client_id
    }

    # Add any extra headers (like X-Start-Date for delta sync)
    if extra_headers:
        headers.update(extra_headers)
    
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


def get_watchlist(list_type='movies', force_refresh=False, check_delta=True):
    """Get user's watchlist with incremental sync caching."""
    from datetime import datetime, timezone

    cache_key = f'watchlist_{list_type}'
    sync_key = f'watchlist_{list_type}_last_sync'

    # Try cache first
    if not force_refresh and HAS_MODULES:
        cached = cache.get_cached_data(cache_key, 'trakt')
        last_sync = cache.get_cached_data(sync_key, 'trakt')

        if cached:
            # Check for delta updates
            if check_delta and last_sync:
                xbmc.log(f'[AIOStreams] Checking for watchlist changes since {last_sync}', xbmc.LOGDEBUG)
                extra_headers = {'X-Start-Date': last_sync}
                delta = call_trakt(f'sync/watchlist/{list_type}', params={'limit': 1000}, extra_headers=extra_headers)

                if delta and isinstance(delta, list):
                    updated = list(cached)
                    changes = 0
                    for item in delta:
                        if item not in updated:
                            updated.append(item)
                            changes += 1

                    if changes > 0:
                        cache.cache_data(cache_key, 'trakt', updated)
                        cache.cache_data(sync_key, 'trakt', datetime.now(timezone.utc).isoformat())
                        xbmc.log(f'[AIOStreams] Watchlist delta: +{changes} items', xbmc.LOGINFO)
                        return updated
                    cache.cache_data(sync_key, 'trakt', datetime.now(timezone.utc).isoformat())
                    return cached
            return cached

    # Full sync
    xbmc.log(f'[AIOStreams] Full watchlist sync for {list_type}', xbmc.LOGDEBUG)
    all_items = []
    page = 1
    while True:
        items = call_trakt(f'sync/watchlist/{list_type}', params={'page': page, 'limit': 100})
        if not items:
            break
        all_items.extend(items)
        if len(items) < 100:
            break
        page += 1

    if HAS_MODULES:
        cache.cache_data(cache_key, 'trakt', all_items)
        cache.cache_data(sync_key, 'trakt', datetime.now(timezone.utc).isoformat())
    return all_items


def get_collection(list_type='movies', force_refresh=False, check_delta=True):
    """Get user's collection with incremental sync caching."""
    from datetime import datetime, timezone

    cache_key = f'collection_{list_type}'
    sync_key = f'collection_{list_type}_last_sync'

    # Try cache first
    if not force_refresh and HAS_MODULES:
        cached = cache.get_cached_data(cache_key, 'trakt')
        last_sync = cache.get_cached_data(sync_key, 'trakt')

        if cached:
            # Check for delta updates
            if check_delta and last_sync:
                xbmc.log(f'[AIOStreams] Checking for collection changes since {last_sync}', xbmc.LOGDEBUG)
                extra_headers = {'X-Start-Date': last_sync}
                delta = call_trakt(f'sync/collection/{list_type}', params={'limit': 1000}, extra_headers=extra_headers)

                if delta and isinstance(delta, list):
                    updated = list(cached)
                    changes = 0
                    for item in delta:
                        if item not in updated:
                            updated.append(item)
                            changes += 1

                    if changes > 0:
                        cache.cache_data(cache_key, 'trakt', updated)
                        cache.cache_data(sync_key, 'trakt', datetime.now(timezone.utc).isoformat())
                        xbmc.log(f'[AIOStreams] Collection delta: +{changes} items', xbmc.LOGINFO)
                        return updated
                    cache.cache_data(sync_key, 'trakt', datetime.now(timezone.utc).isoformat())
                    return cached
            return cached

    # Full sync
    xbmc.log(f'[AIOStreams] Full collection sync for {list_type}', xbmc.LOGDEBUG)
    all_items = []
    page = 1
    while True:
        items = call_trakt(f'sync/collection/{list_type}', params={'page': page, 'limit': 100})
        if not items:
            break
        all_items.extend(items)
        if len(items) < 100:
            break
        page += 1

    if HAS_MODULES:
        cache.cache_data(cache_key, 'trakt', all_items)
        cache.cache_data(sync_key, 'trakt', datetime.now(timezone.utc).isoformat())
    return all_items


def get_watched(list_type='movies', force_refresh=False, check_delta=True):
    """Get user's watched history with incremental sync caching."""
    from datetime import datetime, timezone

    cache_key = f'watched_{list_type}'
    sync_key = f'watched_{list_type}_last_sync'

    # Try cache first
    if not force_refresh and HAS_MODULES:
        cached = cache.get_cached_data(cache_key, 'trakt')
        last_sync = cache.get_cached_data(sync_key, 'trakt')

        if cached:
            # Check for delta updates
            if check_delta and last_sync:
                xbmc.log(f'[AIOStreams] Checking for watched changes since {last_sync}', xbmc.LOGDEBUG)
                extra_headers = {'X-Start-Date': last_sync}
                delta = call_trakt(f'sync/watched/{list_type}', params={'limit': 1000}, extra_headers=extra_headers)

                if delta and isinstance(delta, list):
                    updated = list(cached)
                    changes = 0
                    for item in delta:
                        if item not in updated:
                            updated.append(item)
                            changes += 1

                    if changes > 0:
                        cache.cache_data(cache_key, 'trakt', updated)
                        cache.cache_data(sync_key, 'trakt', datetime.now(timezone.utc).isoformat())
                        xbmc.log(f'[AIOStreams] Watched delta: +{changes} items', xbmc.LOGINFO)
                        return updated
                    cache.cache_data(sync_key, 'trakt', datetime.now(timezone.utc).isoformat())
                    return cached
            return cached

    # Full sync
    xbmc.log(f'[AIOStreams] Full watched sync for {list_type}', xbmc.LOGDEBUG)
    all_items = []
    page = 1
    while True:
        items = call_trakt(f'sync/watched/{list_type}', params={'page': page, 'limit': 100})
        if not items:
            break
        all_items.extend(items)
        if len(items) < 100:
            break
        page += 1

    if HAS_MODULES:
        cache.cache_data(cache_key, 'trakt', all_items)
        cache.cache_data(sync_key, 'trakt', datetime.now(timezone.utc).isoformat())
    return all_items


def get_trending(media_type='movies', page=1, limit=20):
    """Get trending items."""
    return call_trakt(f'{media_type}/trending', params={'page': page, 'limit': limit}, with_auth=False)


def get_popular(media_type='movies', page=1, limit=20):
    """Get popular items."""
    return call_trakt(f'{media_type}/popular', params={'page': page, 'limit': limit}, with_auth=False)


def get_show_progress_by_trakt_id(show_id):
    """Get progress for a specific show by Trakt ID.

    Uses Trakt API to get complete progress including next episode information.
    The database only stores watched episodes, but we need all aired episodes
    to determine the next unwatched episode.

    Cached for 1 hour to reduce API calls (especially for Next Up with many shows).

    Returns progress data with next episode information.
    """
    if not show_id:
        return None

    # Check cache first (1 hour TTL)
    if HAS_MODULES:
        cache_key = f'show_progress_{show_id}'
        cached = cache.get_cached_data(cache_key, 'trakt', max_age=3600)  # 1 hour cache
        if cached:
            xbmc.log(f'[AIOStreams] Using cached show progress for {show_id}', xbmc.LOGDEBUG)
            return cached

    # Fetch from API
    xbmc.log(f'[AIOStreams] Fetching show progress from API for {show_id}', xbmc.LOGDEBUG)
    result = call_trakt(f'shows/{show_id}/progress/watched')

    # Cache the result
    if result and HAS_MODULES:
        cache.cache_data(cache_key, 'trakt', result)

    return result


def get_hidden_shows(force_refresh=False, check_delta=True):
    """Get list of shows user has hidden from progress with incremental sync.

    Uses event-driven caching with delta sync:
    - Local changes (hide/unhide) update cache immediately
    - External changes (from web/other devices) fetched via delta sync using X-Start-Date
    - Full refresh only on cache miss or forced refresh

    Args:
        force_refresh: If True, bypass cache and fetch all data
        check_delta: If True, check for external changes since last sync
    """
    import xbmcaddon
    from datetime import datetime, timezone
    addon = xbmcaddon.Addon()

    # Try cache first
    if not force_refresh and HAS_MODULES:
        cached = cache.get_cached_data('hidden_shows', 'progress_watched')
        last_sync = cache.get_cached_data('hidden_shows_last_sync', 'progress_watched')

        if cached:
            # If we have cache and should check for delta updates
            if check_delta and last_sync:
                xbmc.log(f'[AIOStreams] Checking for external changes to hidden shows since {last_sync}', xbmc.LOGDEBUG)

                # Use X-Start-Date header to fetch only changes since last sync
                extra_headers = {'X-Start-Date': last_sync}
                delta_result = call_trakt('users/hidden/progress_watched', params={'limit': 1000}, extra_headers=extra_headers)

                if delta_result and isinstance(delta_result, list):
                    # Apply delta changes to cache
                    updated_cache = list(cached)  # Copy cached list
                    changes_applied = 0

                    for item in delta_result:
                        show = item.get('show', {})
                        trakt_id = show.get('ids', {}).get('trakt')
                        hidden_at = item.get('hidden_at')  # When it was hidden

                        if trakt_id:
                            # If hidden_at is after last_sync, it's a new addition
                            # If it was already in cache, it might have been re-hidden or it's already there
                            if trakt_id not in updated_cache:
                                updated_cache.append(trakt_id)
                                changes_applied += 1
                                xbmc.log(f'[AIOStreams] Delta sync: Added show {trakt_id} hidden at {hidden_at}', xbmc.LOGDEBUG)

                    if changes_applied > 0:
                        # Update cache with changes
                        cache.cache_data('hidden_shows', 'progress_watched', updated_cache)
                        sync_time = datetime.now(timezone.utc).isoformat()
                        cache.cache_data('hidden_shows_last_sync', 'progress_watched', sync_time)
                        xbmc.log(f'[AIOStreams] Delta sync applied {changes_applied} changes, updated cache to {len(updated_cache)} items', xbmc.LOGINFO)
                        return updated_cache
                    else:
                        # No changes, update sync time and return cached
                        sync_time = datetime.now(timezone.utc).isoformat()
                        cache.cache_data('hidden_shows_last_sync', 'progress_watched', sync_time)
                        xbmc.log(f'[AIOStreams] Delta sync: No changes detected, using cache ({len(cached)} items)', xbmc.LOGDEBUG)
                        return cached
                else:
                    # Delta sync failed, return cached data
                    xbmc.log('[AIOStreams] Delta sync failed, using cached data', xbmc.LOGWARNING)
                    return cached
            elif cached:
                xbmc.log(f'[AIOStreams] get_hidden_shows() returning {len(cached)} Trakt IDs from cache (no delta check)', xbmc.LOGDEBUG)
                return cached

    xbmc.log('[AIOStreams] Fetching all hidden shows from Trakt API (full sync)', xbmc.LOGDEBUG)

    hidden_ids = []
    page = 1
    limit = 100  # Fetch 100 per page

    while True:
        params = {'page': page, 'limit': limit}
        result = call_trakt('users/hidden/progress_watched', params=params)

        if not result or not isinstance(result, list):
            break

        # Add all shows from this page
        for item in result:
            show = item.get('show', {})
            ids = show.get('ids', {})
            trakt_id = ids.get('trakt')
            imdb_id = ids.get('imdb')

            # Log for debugging ID mismatches (only first page to avoid spam)
            if page == 1 and trakt_id:
                xbmc.log(f'[AIOStreams] Hidden show: Trakt={trakt_id}, IMDB={imdb_id}, Title={show.get("title")}', xbmc.LOGDEBUG)

            if trakt_id:
                hidden_ids.append(trakt_id)

        # If we got less than the limit, we've reached the end
        if len(result) < limit:
            break

        page += 1

        # Safety check to prevent infinite loops
        if page > 100:
            xbmc.log('[AIOStreams] Reached maximum pagination limit (100 pages)', xbmc.LOGWARNING)
            break

    xbmc.log(f'[AIOStreams] get_hidden_shows() fetched {len(hidden_ids)} Trakt IDs from {page} page(s), caching with incremental sync support', xbmc.LOGINFO)

    # Cache the result and sync timestamp (for delta sync)
    if HAS_MODULES:
        from datetime import datetime, timezone
        cache.cache_data('hidden_shows', 'progress_watched', hidden_ids)
        # Store sync timestamp in ISO format for X-Start-Date header
        sync_time = datetime.now(timezone.utc).isoformat()
        cache.cache_data('hidden_shows_last_sync', 'progress_watched', sync_time)
        xbmc.log(f'[AIOStreams] Cached hidden shows with sync timestamp: {sync_time}', xbmc.LOGDEBUG)

    return hidden_ids


def get_progress_watching(type='shows', page=1, limit=20):
    """Get shows/movies currently watching (continue watching)."""
    return call_trakt(f'sync/playback/{type}', params={'page': page, 'limit': limit})


def get_recommended(media_type='movies', page=1, limit=20):
    """Get personalized recommendations."""
    return call_trakt(f'recommendations/{media_type}', params={'page': page, 'limit': limit})


def get_related(media_type, item_id, page=1, limit=20):
    """Get related items (similar shows/movies). Requires authentication."""
    # media_type should be 'movies' or 'shows'
    api_type = 'movies' if media_type == 'movie' else 'shows'
    return call_trakt(f'{api_type}/{item_id}/related', params={'page': page, 'limit': limit})


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


def hide_from_progress(media_type, imdb_id):
    """Hide a movie or show from progress/recommendations using IMDB ID.

    This is the 'Stop Watching' or 'Drop' feature.
    Per Trakt's March 2025 'Drop' feature, this hides from progress, calendar, and recommendations.
    API Docs: https://trakt.docs.apiary.io/#reference/users/add-hidden-items
    """
    if not imdb_id:
        xbmc.log('[AIOStreams] Cannot hide from progress: no IMDB ID provided', xbmc.LOGWARNING)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to drop show: Invalid ID', xbmcgui.NOTIFICATION_ERROR)
        return False

    # Determine the data key based on media type
    if media_type in ['movie', 'movies']:
        data_key = 'movies'
    else:
        data_key = 'shows'

    data = {
        data_key: [{'ids': {'imdb': imdb_id}}]
    }

    import json
    xbmc.log(f'[AIOStreams] Dropping {media_type} ({imdb_id}) from all sections', xbmc.LOGINFO)
    xbmc.log(f'[AIOStreams] Request data being sent to Trakt:', xbmc.LOGINFO)
    xbmc.log(f'{json.dumps(data, indent=2)}', xbmc.LOGINFO)

    success_count = 0

    # Hide from all relevant sections for complete "Drop" functionality
    # Note: progress_collected is where Trakt tracks "Dropped" shows
    sections = ['progress_watched', 'progress_collected', 'calendar', 'recommendations']

    for section in sections:
        xbmc.log(f'[AIOStreams] Hiding from section: {section}', xbmc.LOGINFO)
        result = call_trakt(f'users/hidden/{section}', method='POST', data=data)

        # Log full API response for debugging
        if result:
            import json
            xbmc.log(f'[AIOStreams] Trakt API Response for {section}:', xbmc.LOGINFO)
            xbmc.log(f'{json.dumps(result, indent=2)}', xbmc.LOGINFO)
        else:
            xbmc.log(f'[AIOStreams] Trakt API returned no data for {section}', xbmc.LOGWARNING)

        if result:
            # Check what was actually added
            if isinstance(result, dict):
                added = result.get('added', {})
                existing = result.get('existing', {})
                not_found = result.get('not_found', {})

                added_count = added.get(data_key, 0) if isinstance(added, dict) else 0
                existing_count = existing.get(data_key, 0) if isinstance(existing, dict) else 0
                not_found_count = len(not_found.get(data_key, [])) if isinstance(not_found, dict) else 0

                xbmc.log(f'[AIOStreams] {section} - Added: {added_count}, Already existed: {existing_count}, Not found: {not_found_count}', xbmc.LOGINFO)

                if not_found_count > 0:
                    xbmc.log(f'[AIOStreams] ⚠ Warning: {data_key} not found in Trakt: {not_found.get(data_key, [])}', xbmc.LOGWARNING)

                if added_count > 0 or existing_count > 0:
                    xbmc.log(f'[AIOStreams] ✓ Successfully hidden from {section}', xbmc.LOGINFO)
                    success_count += 1
                else:
                    xbmc.log(f'[AIOStreams] ✗ Item not added to {section} (not found by Trakt)', xbmc.LOGWARNING)
            else:
                # Simple boolean response
                xbmc.log(f'[AIOStreams] ✓ Successfully hidden from {section}', xbmc.LOGINFO)
                success_count += 1
        else:
            xbmc.log(f'[AIOStreams] ✗ Failed to hide from {section}', xbmc.LOGWARNING)

    # Success if at least one section succeeded
    if success_count > 0:
        item_type = 'Movie' if media_type in ['movie', 'movies'] else 'Show'
        xbmc.log(f'[AIOStreams] Successfully dropped {item_type} ({imdb_id}) - hidden from {success_count}/{len(sections)} sections', xbmc.LOGINFO)

        # Validate and extract Trakt ID for cache update
        xbmc.log(f'[AIOStreams] Validating drop operation by checking hidden lists...', xbmc.LOGDEBUG)
        trakt_id_to_cache = None
        for section in sections:
            hidden_items = get_hidden_items(section=section, media_type=data_key, limit=1000)
            # Find the item and extract Trakt ID
            for item in hidden_items:
                item_data = item.get(data_key[:-1], {})
                if item_data.get('ids', {}).get('imdb') == imdb_id:
                    trakt_id_to_cache = item_data.get('ids', {}).get('trakt')
                    xbmc.log(f'[AIOStreams] ✓ Validation: Item confirmed hidden in {section}, Trakt ID: {trakt_id_to_cache}', xbmc.LOGINFO)
                    break
            if not trakt_id_to_cache:
                xbmc.log(f'[AIOStreams] ⚠ Validation: Item NOT found in {section} hidden list', xbmc.LOGWARNING)

        xbmcgui.Dialog().notification('AIOStreams', f'{item_type} dropped from watching', xbmcgui.NOTIFICATION_INFO)
        # Invalidate progress cache since we've hidden an item
        invalidate_progress_cache()

        # Update hidden shows cache directly instead of invalidating (incremental sync)
        if HAS_MODULES and trakt_id_to_cache:
            cached = cache.get_cached_data('hidden_shows', 'progress_watched')
            if cached and isinstance(cached, list):
                if trakt_id_to_cache not in cached:
                    cached.append(trakt_id_to_cache)
                    cache.cache_data('hidden_shows', 'progress_watched', cached)
                    xbmc.log(f'[AIOStreams] Added Trakt ID {trakt_id_to_cache} to hidden shows cache (incremental update)', xbmc.LOGINFO)
                else:
                    xbmc.log(f'[AIOStreams] Trakt ID {trakt_id_to_cache} already in hidden shows cache', xbmc.LOGDEBUG)
            else:
                xbmc.log('[AIOStreams] No hidden shows cache found, will be populated on next fetch', xbmc.LOGDEBUG)

            # Also add to local database so Next Up list updates immediately
            try:
                from resources.lib.database.trakt_sync import TraktSyncDatabase
                db = TraktSyncDatabase()
                # Add to all sections that were hidden
                for section in sections:
                    db.add_hidden_item(trakt_id_to_cache, data_key[:-1], section)  # data_key[:-1] converts 'shows' -> 'show'
                xbmc.log(f'[AIOStreams] Added Trakt ID {trakt_id_to_cache} to local database hidden table', xbmc.LOGINFO)
            except Exception as e:
                xbmc.log(f'[AIOStreams] Failed to add to local database hidden table: {e}', xbmc.LOGERROR)

        return True
    else:
        xbmc.log(f'[AIOStreams] Failed to drop {media_type} ({imdb_id}) from all sections', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to drop from watching', xbmcgui.NOTIFICATION_ERROR)
        return False


def unhide_from_progress(media_type, imdb_id):
    """Remove a movie or show from hidden lists (unhide/undrop).

    This reverses the 'Stop Watching' or 'Drop' action by removing from all hidden sections.
    API Docs: https://trakt.docs.apiary.io/#reference/users/remove-hidden-items
    """
    if not imdb_id:
        xbmc.log('[AIOStreams] Cannot unhide: no IMDB ID provided', xbmc.LOGWARNING)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to unhide show: Invalid ID', xbmcgui.NOTIFICATION_ERROR)
        return False

    # Determine the data key based on media type
    if media_type in ['movie', 'movies']:
        data_key = 'movies'
    else:
        data_key = 'shows'

    data = {
        data_key: [{'ids': {'imdb': imdb_id}}]
    }

    import json
    xbmc.log(f'[AIOStreams] Unhiding {media_type} ({imdb_id}) from all sections', xbmc.LOGINFO)
    xbmc.log(f'[AIOStreams] Request data being sent to Trakt:', xbmc.LOGINFO)
    xbmc.log(f'{json.dumps(data, indent=2)}', xbmc.LOGINFO)

    success_count = 0

    # Remove from all hidden sections
    sections = ['progress_watched', 'progress_collected', 'calendar', 'recommendations']

    for section in sections:
        xbmc.log(f'[AIOStreams] Removing from hidden section: {section}', xbmc.LOGINFO)
        result = call_trakt(f'users/hidden/{section}/remove', method='POST', data=data)

        # Log full API response for debugging
        if result:
            xbmc.log(f'[AIOStreams] Trakt API Response for {section}:', xbmc.LOGINFO)
            xbmc.log(f'{json.dumps(result, indent=2)}', xbmc.LOGINFO)
        else:
            xbmc.log(f'[AIOStreams] Trakt API returned no data for {section}', xbmc.LOGWARNING)

        if result:
            # Check what was actually removed
            if isinstance(result, dict):
                deleted = result.get('deleted', {})
                not_found = result.get('not_found', {})

                deleted_count = deleted.get(data_key, 0) if isinstance(deleted, dict) else 0
                not_found_count = len(not_found.get(data_key, [])) if isinstance(not_found, dict) else 0

                xbmc.log(f'[AIOStreams] {section} - Deleted: {deleted_count}, Not found: {not_found_count}', xbmc.LOGINFO)

                if deleted_count > 0:
                    xbmc.log(f'[AIOStreams] ✓ Successfully removed from {section}', xbmc.LOGINFO)
                    success_count += 1
                elif not_found_count > 0:
                    xbmc.log(f'[AIOStreams] Item not found in {section} (may not have been hidden there)', xbmc.LOGDEBUG)
            else:
                xbmc.log(f'[AIOStreams] Unexpected response format from {section}', xbmc.LOGWARNING)
        else:
            xbmc.log(f'[AIOStreams] No response from Trakt for {section}', xbmc.LOGWARNING)

    if success_count > 0:
        xbmc.log(f'[AIOStreams] Successfully unhid {media_type} ({imdb_id}) from {success_count} sections', xbmc.LOGINFO)
        xbmcgui.Dialog().notification('AIOStreams', 'Show unhidden successfully', xbmcgui.NOTIFICATION_INFO)

        # Remove from local database hidden table
        try:
            from resources.lib.database.trakt_sync import TraktSyncDatabase
            db = TraktSyncDatabase()
            db.execute_sql("DELETE FROM hidden WHERE trakt_id IN (SELECT trakt_id FROM shows WHERE imdb_id=?)", (imdb_id,))
            xbmc.log(f'[AIOStreams] Removed {imdb_id} from local database hidden table', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Failed to remove from local database hidden table: {e}', xbmc.LOGERROR)

        # Invalidate progress cache to force refresh
        invalidate_progress_cache()

        return True
    else:
        xbmc.log(f'[AIOStreams] {media_type} ({imdb_id}) may not have been hidden on Trakt', xbmc.LOGINFO)
        xbmcgui.Dialog().notification('AIOStreams', 'Show was not hidden on Trakt', xbmcgui.NOTIFICATION_INFO)
        return True  # Still return True since it's technically successful (show isn't hidden)


def get_hidden_items(section='progress_watched', media_type='shows', limit=100):
    """Retrieve currently hidden items from Trakt for validation.

    Args:
        section: One of 'progress_watched', 'calendar', 'recommendations'
        media_type: 'shows' or 'movies'
        limit: Number of items to retrieve (default 100)

    Returns:
        List of hidden items with their metadata

    API Docs: https://trakt.docs.apiary.io/#reference/users/get-hidden-items
    """
    if not get_access_token():
        xbmc.log('[AIOStreams] Not authorized with Trakt', xbmc.LOGWARNING)
        return []

    params = {
        'type': media_type,
        'limit': limit
    }

    xbmc.log(f'[AIOStreams] Fetching hidden items from {section} (type: {media_type})', xbmc.LOGDEBUG)
    result = call_trakt(f'users/hidden/{section}', method='GET', params=params)

    if result and isinstance(result, list):
        xbmc.log(f'[AIOStreams] Found {len(result)} hidden {media_type} in {section}', xbmc.LOGINFO)

        # Log first few items for debugging
        for idx, item in enumerate(result[:5]):  # Log first 5 items
            show_data = item.get('show', {})
            title = show_data.get('title', 'Unknown')
            year = show_data.get('year', 'Unknown')
            ids = show_data.get('ids', {})
            imdb = ids.get('imdb', 'No IMDB')
            xbmc.log(f'[AIOStreams]   Hidden item {idx+1}: {title} ({year}) - IMDB: {imdb}', xbmc.LOGDEBUG)

        if len(result) > 5:
            xbmc.log(f'[AIOStreams]   ... and {len(result) - 5} more', xbmc.LOGDEBUG)

        return result
    else:
        xbmc.log(f'[AIOStreams] No hidden {media_type} found in {section}', xbmc.LOGINFO)
        return []


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
    """Add item to watchlist with optimistic database update.
    
    Updates database first for instant UI response, then syncs to Trakt in background.
    Rollback on Trakt API failure.
    """
    import threading
    from datetime import datetime, timezone
    
    if not imdb_id:
        xbmc.log('[AIOStreams] Cannot add to watchlist: no IMDB ID', xbmc.LOGWARNING)
        return False
    
    # For episodes/shows/series, we use 'shows' in the API
    api_type = 'shows' if media_type in ['episode', 'show', 'series'] or season is not None else media_type + 's'
    mediatype_db = 'show' if api_type == 'shows' else 'movie'
    
    # 1. Optimistic database update (instant UI response)
    # Use IMDB ID directly for now, Trakt ID will be updated in background
    db = get_trakt_db()
    if db:
        try:
            listed_at = datetime.now(timezone.utc).isoformat()
            # Use 0 as temporary Trakt ID, will be updated by background thread
            db.execute_sql("""
                INSERT OR IGNORE INTO watchlist (trakt_id, mediatype, imdb_id, listed_at)
                VALUES (0, ?, ?, ?)
            """, (mediatype_db, imdb_id, listed_at))
            xbmc.log(f'[AIOStreams] Optimistically added {imdb_id} to watchlist database', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Database update failed: {e}', xbmc.LOGERROR)
    
    # Show instant feedback
    xbmcgui.Dialog().notification('AIOStreams', 'Added to Trakt watchlist', xbmcgui.NOTIFICATION_INFO)
    
    # Refresh container immediately for instant UI update
    if utils:
        utils.refresh_container()
    
    # 2. Background sync to Trakt API with rollback on failure
    def sync_to_trakt():
        """Background thread to sync to Trakt with rollback on failure."""
        # Get Trakt ID in background (non-blocking)
        trakt_id = None
        try:
            search_result = call_trakt(f'search/imdb/{imdb_id}', with_auth=False)
            if search_result and isinstance(search_result, list) and len(search_result) > 0:
                item_data = search_result[0].get(mediatype_db, {})
                trakt_id = item_data.get('ids', {}).get('trakt')
        except Exception as e:
            xbmc.log(f'[AIOStreams] Failed to get Trakt ID: {e}', xbmc.LOGDEBUG)
        
        # Sync to Trakt API
        data = {api_type: []}
        item = {'ids': {'imdb': imdb_id}}
        if season is not None:
            item['seasons'] = [{'number': season}]
            if episode is not None:
                item['seasons'][0]['episodes'] = [{'number': episode}]
        data[api_type].append(item)
        
        result = call_trakt('sync/watchlist', method='POST', data=data)
        
        if not result:
            # Rollback database on API failure
            xbmc.log(f'[AIOStreams] Trakt API failed, rolling back watchlist add for {imdb_id}', xbmc.LOGWARNING)
            if db:
                db.execute_sql(
                    "DELETE FROM watchlist WHERE imdb_id=? AND mediatype=?",
                    (imdb_id, mediatype_db)
                )
            xbmcgui.Dialog().notification('AIOStreams', 'Failed to sync to Trakt', xbmcgui.NOTIFICATION_ERROR)
        else:
            xbmc.log(f'[AIOStreams] Successfully synced {imdb_id} to Trakt watchlist', xbmc.LOGINFO)
            # Update database with real Trakt ID now that we have it
            if db and trakt_id:
                db.execute_sql(
                    "UPDATE watchlist SET trakt_id=? WHERE imdb_id=? AND mediatype=?",
                    (trakt_id, imdb_id, mediatype_db)
                )
        
        # Trigger smart widget refresh after sync
        if utils:
            utils.trigger_background_refresh(delay=0.5)
    
    # Start background sync thread
    try:
        sync_thread = threading.Thread(target=sync_to_trakt)
        sync_thread.daemon = True
        sync_thread.start()
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to start background sync: {e}', xbmc.LOGERROR)
        # Fallback to synchronous sync
        sync_to_trakt()
    
    return True


def remove_from_watchlist(media_type, imdb_id, season=None, episode=None):
    """Remove item from watchlist with optimistic database update.
    
    Updates database first for instant UI response, then syncs to Trakt in background.
    Rollback on Trakt API failure.
    """
    import threading
    
    if not imdb_id:
        xbmc.log('[AIOStreams] Cannot remove from watchlist: no IMDB ID', xbmc.LOGWARNING)
        return False
    
    # For episodes/shows/series, we use 'shows' in the API
    api_type = 'shows' if media_type in ['episode', 'show', 'series'] or season is not None else media_type + 's'
    mediatype_db = 'show' if api_type == 'shows' else 'movie'
    
    # Store original state for potential rollback (using IMDB ID for lookup)
    original_state = None
    db = get_trakt_db()
    if db:
        try:
            original_state = db.fetchone(
                "SELECT * FROM watchlist WHERE imdb_id=? AND mediatype=?",
                (imdb_id, mediatype_db)
            )
        except Exception as e:
            xbmc.log(f'[AIOStreams] Failed to get original state: {e}', xbmc.LOGDEBUG)
    
    # 1. Optimistic database update (instant UI response)
    if db:
        try:
            db.execute_sql(
                "DELETE FROM watchlist WHERE imdb_id=? AND mediatype=?",
                (imdb_id, mediatype_db)
            )
            xbmc.log(f'[AIOStreams] Optimistically removed {imdb_id} from watchlist database', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Database update failed: {e}', xbmc.LOGERROR)
    
    # Show instant feedback
    xbmcgui.Dialog().notification('AIOStreams', 'Removed from Trakt watchlist', xbmcgui.NOTIFICATION_INFO)
    
    # Refresh container immediately for instant UI update
    if utils:
        utils.refresh_container()
    
    # 2. Background sync to Trakt API with rollback on failure
    def sync_to_trakt():
        """Background thread to sync to Trakt with rollback on failure."""
        data = {api_type: []}
        item = {'ids': {'imdb': imdb_id}}
        if season is not None:
            item['seasons'] = [{'number': season}]
            if episode is not None:
                item['seasons'][0]['episodes'] = [{'number': episode}]
        data[api_type].append(item)
        
        result = call_trakt('sync/watchlist/remove', method='POST', data=data)
        
        if not result:
            # Rollback database on API failure
            xbmc.log(f'[AIOStreams] Trakt API failed, rolling back watchlist removal for {imdb_id}', xbmc.LOGWARNING)
            if db and original_state:
                try:
                    db.execute_sql("""
                        INSERT OR REPLACE INTO watchlist (trakt_id, mediatype, imdb_id, listed_at)
                        VALUES (?, ?, ?, ?)
                    """, (
                        original_state['trakt_id'],
                        original_state['mediatype'],
                        original_state['imdb_id'],
                        original_state['listed_at']
                    ))
                except Exception as e:
                    xbmc.log(f'[AIOStreams] Rollback failed: {e}', xbmc.LOGERROR)
            xbmcgui.Dialog().notification('AIOStreams', 'Failed to sync to Trakt', xbmcgui.NOTIFICATION_ERROR)
        else:
            xbmc.log(f'[AIOStreams] Successfully removed {imdb_id} from Trakt watchlist', xbmc.LOGINFO)
        
        # Trigger smart widget refresh after sync
        if utils:
            utils.trigger_background_refresh(delay=0.5)
    
    # Start background sync thread
    try:
        sync_thread = threading.Thread(target=sync_to_trakt)
        sync_thread.daemon = True
        sync_thread.start()
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to start background sync: {e}', xbmc.LOGERROR)
        # Fallback to synchronous sync
        sync_to_trakt()
    
    return True


def _add_show_to_pending_updates(imdb_id):
    """Add show to pending updates list and refresh Kodi widgets.
    
    Helper function to track recently updated shows to handle Trakt's eventual consistency.
    
    Args:
        imdb_id: IMDB ID of the show that was updated
    """
    global _pending_show_updates
    
    # Fetch show data to get Trakt ID
    show_data = call_trakt(f'search/imdb/{imdb_id}', with_auth=False)
    if show_data and isinstance(show_data, list) and len(show_data) > 0:
        show_trakt_id = show_data[0].get('show', {}).get('ids', {}).get('trakt')
        if show_trakt_id:
            _pending_show_updates[show_trakt_id] = time.time()
            xbmc.log(f'[AIOStreams] Added show {show_trakt_id} to pending updates (10s grace period)', xbmc.LOGDEBUG)
            
            # Refresh Kodi widgets to show updated data
            try:
                xbmc.executebuiltin('Container.Refresh')
            except Exception as e:
                xbmc.log(f'[AIOStreams] Failed to refresh container: {e}', xbmc.LOGWARNING)
            
            return show_trakt_id
    return None


def mark_watched(media_type, imdb_id, season=None, episode=None, playback_id=None):
    """Mark item as watched with optimistic database update.

    Handles three scenarios for shows:
    1. Episode: season + episode provided → Mark single episode
    2. Season: season provided, episode is None → Mark all episodes in season
    3. Show: neither season nor episode → Mark all episodes in all seasons

    Updates database first for instant UI response, then syncs to Trakt in background.
    Rollback on Trakt API failure.
    """
    import threading
    from datetime import datetime, timezone

    xbmc.log(f'[AIOStreams] mark_watched() called with: media_type={media_type}, imdb_id={imdb_id}, season={season}, episode={episode}', xbmc.LOGINFO)

    if not imdb_id:
        xbmc.log('[AIOStreams] Cannot mark as watched: no IMDB ID provided', xbmc.LOGWARNING)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to mark as watched: Invalid ID', xbmcgui.NOTIFICATION_ERROR)
        return False

    # Determine operation type
    is_show_operation = media_type in ['episode', 'show', 'series'] or season is not None
    api_type = 'shows' if is_show_operation else media_type + 's'
    xbmc.log(f'[AIOStreams] Operation type: api_type={api_type}, is_show={is_show_operation}', xbmc.LOGINFO)

    # Determine scenario
    if is_show_operation:
        if season is not None and episode is not None:
            scenario = 'episode'
            xbmc.log(f'[AIOStreams] Scenario: Mark EPISODE S{season}E{episode}', xbmc.LOGINFO)
        elif season is not None:
            scenario = 'season'
            xbmc.log(f'[AIOStreams] Scenario: Mark SEASON {season} (all episodes)', xbmc.LOGINFO)
        else:
            scenario = 'show'
            xbmc.log(f'[AIOStreams] Scenario: Mark SHOW (all seasons and episodes)', xbmc.LOGINFO)
    else:
        scenario = 'movie'
        xbmc.log(f'[AIOStreams] Scenario: Mark MOVIE', xbmc.LOGINFO)

    # Get Trakt ID and full show data
    trakt_id = None
    show_trakt_id = None
    show_data = None
    try:
        search_result = call_trakt(f'search/imdb/{imdb_id}', with_auth=False)
        if search_result and isinstance(search_result, list) and len(search_result) > 0:
            if is_show_operation:
                show_data = search_result[0].get('show', {})
                show_trakt_id = show_data.get('ids', {}).get('trakt')
                trakt_id = show_trakt_id
            else:
                movie_data = search_result[0].get('movie', {})
                trakt_id = movie_data.get('ids', {}).get('trakt')
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to get Trakt ID: {e}', xbmc.LOGERROR)

    if not trakt_id:
        xbmc.log(f'[AIOStreams] Could not find Trakt ID for {imdb_id}', xbmc.LOGWARNING)
        xbmcgui.Dialog().notification('AIOStreams', 'Could not find item on Trakt', xbmcgui.NOTIFICATION_ERROR)
        return False

    db = get_trakt_db()
    watched_at = datetime.now(timezone.utc).isoformat()
    original_states = []  # For rollback

    # 1. Optimistic database update (instant UI response)
    if db:
        try:
            if scenario == 'episode':
                # Mark single episode
                xbmc.log(f'[AIOStreams] Database: Marking episode S{season}E{episode}', xbmc.LOGINFO)

                # Ensure show exists
                _ensure_show_exists(db, show_trakt_id, show_data)

                # Store original state
                original_states.append(db.fetchone(
                    "SELECT * FROM episodes WHERE show_trakt_id=? AND season=? AND episode=?",
                    (show_trakt_id, season, episode)
                ))

                # Update episode
                db.execute_sql("""
                    INSERT OR REPLACE INTO episodes (
                        show_trakt_id, season, episode, watched, last_watched_at
                    ) VALUES (?, ?, ?, 1, ?)
                """, (show_trakt_id, season, episode, watched_at))

                xbmc.log(f'[AIOStreams] ✓ Marked ONLY episode S{season}E{episode} as watched', xbmc.LOGINFO)

                # Unhide show if it was dropped
                _unhide_show_if_needed(db, show_trakt_id)

            elif scenario == 'season':
                # Mark all episodes in season
                xbmc.log(f'[AIOStreams] Database: Fetching all episodes for season {season}', xbmc.LOGINFO)

                # Ensure show exists
                _ensure_show_exists(db, show_trakt_id, show_data)

                # Get all episodes in this season from Trakt
                season_data = call_trakt(f'shows/{show_trakt_id}/seasons/{season}?extended=episodes')
                if season_data and isinstance(season_data, list):
                    xbmc.log(f'[AIOStreams] Found {len(season_data)} episodes in season {season}', xbmc.LOGINFO)

                    for ep in season_data:
                        ep_num = ep.get('number')
                        if ep_num:
                            # Store original state
                            original_states.append(db.fetchone(
                                "SELECT * FROM episodes WHERE show_trakt_id=? AND season=? AND episode=?",
                                (show_trakt_id, season, ep_num)
                            ))

                            # Mark episode as watched
                            db.execute_sql("""
                                INSERT OR REPLACE INTO episodes (
                                    show_trakt_id, season, episode, watched, last_watched_at
                                ) VALUES (?, ?, ?, 1, ?)
                            """, (show_trakt_id, season, ep_num, watched_at))

                    xbmc.log(f'[AIOStreams] ✓ Marked {len(season_data)} episodes in season {season} as watched', xbmc.LOGINFO)
                else:
                    xbmc.log(f'[AIOStreams] Warning: Could not fetch episodes for season {season}', xbmc.LOGWARNING)

                # Unhide show if it was dropped
                _unhide_show_if_needed(db, show_trakt_id)

            elif scenario == 'show':
                # Mark all episodes in all seasons
                xbmc.log(f'[AIOStreams] Database: Fetching all seasons and episodes', xbmc.LOGINFO)

                # Ensure show exists
                _ensure_show_exists(db, show_trakt_id, show_data)

                # Get all seasons from Trakt
                seasons_data = call_trakt(f'shows/{show_trakt_id}/seasons?extended=episodes')
                if seasons_data and isinstance(seasons_data, list):
                    total_episodes = 0
                    for season_obj in seasons_data:
                        season_num = season_obj.get('number')
                        if season_num == 0:  # Skip specials
                            continue

                        episodes = season_obj.get('episodes', [])
                        xbmc.log(f'[AIOStreams] Season {season_num}: {len(episodes)} episodes', xbmc.LOGINFO)

                        for ep in episodes:
                            ep_num = ep.get('number')
                            if ep_num:
                                # Store original state
                                original_states.append(db.fetchone(
                                    "SELECT * FROM episodes WHERE show_trakt_id=? AND season=? AND episode=?",
                                    (show_trakt_id, season_num, ep_num)
                                ))

                                # Mark episode as watched
                                db.execute_sql("""
                                    INSERT OR REPLACE INTO episodes (
                                        show_trakt_id, season, episode, watched, last_watched_at
                                    ) VALUES (?, ?, ?, 1, ?)
                                """, (show_trakt_id, season_num, ep_num, watched_at))
                                total_episodes += 1

                    xbmc.log(f'[AIOStreams] ✓ Marked {total_episodes} episodes across all seasons as watched', xbmc.LOGINFO)
                else:
                    xbmc.log(f'[AIOStreams] Warning: Could not fetch seasons/episodes', xbmc.LOGWARNING)

                # Unhide show if it was dropped
                _unhide_show_if_needed(db, show_trakt_id)

            elif scenario == 'movie':
                # Mark movie as watched
                xbmc.log(f'[AIOStreams] Database: Marking movie as watched', xbmc.LOGINFO)

                # Store original state
                original_states.append(db.fetchone(
                    "SELECT * FROM movies WHERE trakt_id=?",
                    (trakt_id,)
                ))

                # Update movie
                db.execute_sql("""
                    INSERT OR REPLACE INTO movies (
                        trakt_id, imdb_id, watched, last_watched_at
                    ) VALUES (?, ?, 1, ?)
                """, (trakt_id, imdb_id, watched_at))

                xbmc.log(f'[AIOStreams] ✓ Marked movie as watched', xbmc.LOGINFO)

            # Clear caches
            if is_show_operation:
                xbmc.log(f'[AIOStreams] Clearing caches for show', xbmc.LOGINFO)
                if imdb_id in _show_progress_cache:
                    del _show_progress_cache[imdb_id]
                if imdb_id in _show_progress_batch_cache:
                    del _show_progress_batch_cache[imdb_id]
                if HAS_MODULES:
                    cache.delete_cached_data(f'show_progress_{show_trakt_id}', 'trakt')
                invalidate_progress_cache()

        except Exception as e:
            xbmc.log(f'[AIOStreams] Database update failed: {e}', xbmc.LOGERROR)
            import traceback
            xbmc.log(f'[AIOStreams] Traceback: {traceback.format_exc()}', xbmc.LOGERROR)

    # Show instant feedback
    if scenario == 'episode':
        xbmcgui.Dialog().notification('AIOStreams', f'Episode S{season}E{episode} marked as watched', xbmcgui.NOTIFICATION_INFO)
    elif scenario == 'season':
        xbmcgui.Dialog().notification('AIOStreams', f'Season {season} marked as watched', xbmcgui.NOTIFICATION_INFO)
    elif scenario == 'show':
        xbmcgui.Dialog().notification('AIOStreams', 'Show marked as watched', xbmcgui.NOTIFICATION_INFO)
    else:
        xbmcgui.Dialog().notification('AIOStreams', 'Marked as watched on Trakt', xbmcgui.NOTIFICATION_INFO)

    # Refresh container immediately for instant UI update
    if utils:
        utils.refresh_container()

    # 2. Background sync to Trakt API with rollback on failure
    def sync_to_trakt():
        """Background thread to sync to Trakt with rollback on failure."""
        # Build Trakt API request
        data = {api_type: []}
        item = {'ids': {'imdb': imdb_id}}

        if scenario == 'episode':
            item['seasons'] = [{'number': season, 'episodes': [{'number': episode}]}]
        elif scenario == 'season':
            item['seasons'] = [{'number': season}]  # No episodes array = marks all episodes in season
        # elif scenario == 'show': item has no seasons array = marks all episodes in all seasons

        data[api_type].append(item)

        import json
        xbmc.log(f'[AIOStreams] ====== TRAKT API REQUEST ======', xbmc.LOGINFO)
        xbmc.log(f'[AIOStreams] Scenario: {scenario.upper()}', xbmc.LOGINFO)
        xbmc.log(f'[AIOStreams] Endpoint: sync/history (POST)', xbmc.LOGINFO)
        xbmc.log(f'[AIOStreams] Request data:', xbmc.LOGINFO)
        xbmc.log(f'{json.dumps(data, indent=2)}', xbmc.LOGINFO)
        xbmc.log(f'[AIOStreams] ===============================', xbmc.LOGINFO)

        result = call_trakt('sync/history', method='POST', data=data)

        xbmc.log(f'[AIOStreams] ====== TRAKT API RESPONSE ======', xbmc.LOGINFO)
        if result:
            xbmc.log(f'{json.dumps(result, indent=2)}', xbmc.LOGINFO)
        else:
            xbmc.log(f'[AIOStreams] No response received from Trakt', xbmc.LOGWARNING)
        xbmc.log(f'[AIOStreams] ================================', xbmc.LOGINFO)

        if not result:
            # Rollback database on API failure
            xbmc.log(f'[AIOStreams] Trakt API failed, rolling back watched status', xbmc.LOGWARNING)
            if db:
                _rollback_watched_changes(db, scenario, show_trakt_id, trakt_id, season, episode, original_states)
            xbmcgui.Dialog().notification('AIOStreams', 'Failed to sync to Trakt', xbmcgui.NOTIFICATION_ERROR)
        else:
            # Success - remove from playback progress if we have playback_id
            if playback_id:
                call_trakt(f'sync/playback/{playback_id}', method='DELETE')

            xbmc.log(f'[AIOStreams] ✓ Successfully synced to Trakt', xbmc.LOGINFO)

        # Trigger smart widget refresh after sync
        if utils:
            xbmc.log(f'[AIOStreams] Triggering background widget refresh', xbmc.LOGINFO)
            utils.trigger_background_refresh(delay=0.5)

    # Start background sync thread
    try:
        sync_thread = threading.Thread(target=sync_to_trakt)
        sync_thread.daemon = True
        sync_thread.start()
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to start background sync: {e}', xbmc.LOGERROR)
        # Fallback to synchronous sync
        sync_to_trakt()

    return True


def _ensure_show_exists(db, show_trakt_id, show_data):
    """Ensure show entry exists in database."""
    if not show_trakt_id or not show_data:
        return

    show_exists = db.fetchone(
        "SELECT 1 FROM shows WHERE trakt_id=?",
        (show_trakt_id,)
    )
    if not show_exists:
        db.execute_sql("""
            INSERT OR IGNORE INTO shows (trakt_id, imdb_id, tvdb_id, tmdb_id, slug, title)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            show_trakt_id,
            show_data.get('ids', {}).get('imdb'),
            show_data.get('ids', {}).get('tvdb'),
            show_data.get('ids', {}).get('tmdb'),
            show_data.get('ids', {}).get('slug'),
            show_data.get('title', 'Unknown')
        ))
        xbmc.log(f'[AIOStreams] Created show entry for {show_trakt_id}', xbmc.LOGDEBUG)


def _unhide_show_if_needed(db, show_trakt_id):
    """Unhide show if it was dropped - user is watching again!"""
    try:
        hidden_check = db.fetchone(
            "SELECT 1 FROM hidden WHERE trakt_id=? AND mediatype='show' AND section='progress_watched'",
            (show_trakt_id,)
        )
        if hidden_check:
            db.execute_sql(
                "DELETE FROM hidden WHERE trakt_id=? AND mediatype='show'",
                (show_trakt_id,)
            )
            xbmc.log(f'[AIOStreams] Unhid show {show_trakt_id} - user is watching again!', xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to unhide show: {e}', xbmc.LOGERROR)


def _rollback_watched_changes(db, scenario, show_trakt_id, trakt_id, season, episode, original_states):
    """Rollback database changes on Trakt API failure."""
    try:
        if scenario == 'episode':
            if original_states and original_states[0]:
                # Restore original state
                orig = original_states[0]
                db.execute_sql("""
                    INSERT OR REPLACE INTO episodes (
                        show_trakt_id, season, episode, watched, last_watched_at
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    orig['show_trakt_id'],
                    orig['season'],
                    orig['episode'],
                    orig.get('watched', 0),
                    orig.get('last_watched_at')
                ))
            else:
                # Delete if it didn't exist before
                db.execute_sql(
                    "DELETE FROM episodes WHERE show_trakt_id=? AND season=? AND episode=?",
                    (show_trakt_id, season, episode)
                )
        elif scenario in ['season', 'show']:
            # Rollback multiple episodes
            for orig in original_states:
                if orig:
                    db.execute_sql("""
                        INSERT OR REPLACE INTO episodes (
                            show_trakt_id, season, episode, watched, last_watched_at
                        ) VALUES (?, ?, ?, ?, ?)
                    """, (
                        orig['show_trakt_id'],
                        orig['season'],
                        orig['episode'],
                        orig.get('watched', 0),
                        orig.get('last_watched_at')
                    ))
        elif scenario == 'movie':
            if original_states and original_states[0]:
                orig = original_states[0]
                db.execute_sql("""
                    INSERT OR REPLACE INTO movies (
                        trakt_id, imdb_id, watched, last_watched_at
                    ) VALUES (?, ?, ?, ?)
                """, (
                    orig['trakt_id'],
                    orig['imdb_id'],
                    orig.get('watched', 0),
                    orig.get('last_watched_at')
                ))
            else:
                db.execute_sql(
                    "DELETE FROM movies WHERE trakt_id=?",
                    (trakt_id,)
                )
        xbmc.log(f'[AIOStreams] Rollback completed', xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Rollback failed: {e}', xbmc.LOGERROR)

def mark_unwatched(media_type, imdb_id, season=None, episode=None):
    """Mark item as unwatched with optimistic database update.

    Handles three scenarios for shows:
    1. Episode: season + episode provided → Mark single episode as unwatched
    2. Season: season provided, episode is None → Mark all episodes in season as unwatched
    3. Show: neither season nor episode → Mark all episodes in all seasons as unwatched

    Updates database first for instant UI response, then syncs to Trakt in background.
    Rollback on Trakt API failure.
    """
    import threading

    xbmc.log(f'[AIOStreams] mark_unwatched() called with: media_type={media_type}, imdb_id={imdb_id}, season={season}, episode={episode}', xbmc.LOGINFO)

    if not imdb_id:
        xbmc.log('[AIOStreams] Cannot mark as unwatched: no IMDB ID provided', xbmc.LOGWARNING)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to mark as unwatched: Invalid ID', xbmcgui.NOTIFICATION_ERROR)
        return False

    # Determine operation type
    is_show_operation = media_type in ['episode', 'show', 'series'] or season is not None
    api_type = 'shows' if is_show_operation else media_type + 's'
    xbmc.log(f'[AIOStreams] Operation type: api_type={api_type}, is_show={is_show_operation}', xbmc.LOGINFO)

    # Determine scenario
    if is_show_operation:
        if season is not None and episode is not None:
            scenario = 'episode'
            xbmc.log(f'[AIOStreams] Scenario: Mark EPISODE S{season}E{episode} as UNWATCHED', xbmc.LOGINFO)
        elif season is not None:
            scenario = 'season'
            xbmc.log(f'[AIOStreams] Scenario: Mark SEASON {season} as UNWATCHED (all episodes)', xbmc.LOGINFO)
        else:
            scenario = 'show'
            xbmc.log(f'[AIOStreams] Scenario: Mark SHOW as UNWATCHED (all seasons and episodes)', xbmc.LOGINFO)
    else:
        scenario = 'movie'
        xbmc.log(f'[AIOStreams] Scenario: Mark MOVIE as UNWATCHED', xbmc.LOGINFO)

    # Get Trakt ID and full show data
    trakt_id = None
    show_trakt_id = None
    show_data = None
    try:
        search_result = call_trakt(f'search/imdb/{imdb_id}', with_auth=False)
        if search_result and isinstance(search_result, list) and len(search_result) > 0:
            if is_show_operation:
                show_data = search_result[0].get('show', {})
                show_trakt_id = show_data.get('ids', {}).get('trakt')
                trakt_id = show_trakt_id
            else:
                movie_data = search_result[0].get('movie', {})
                trakt_id = movie_data.get('ids', {}).get('trakt')
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to get Trakt ID: {e}', xbmc.LOGERROR)

    if not trakt_id:
        xbmc.log(f'[AIOStreams] Could not find Trakt ID for {imdb_id}', xbmc.LOGWARNING)
        xbmcgui.Dialog().notification('AIOStreams', 'Could not find item on Trakt', xbmcgui.NOTIFICATION_ERROR)
        return False

    db = get_trakt_db()
    original_states = []  # For rollback

    # 1. Optimistic database update (instant UI response)
    if db:
        try:
            if scenario == 'episode':
                # Mark single episode as unwatched
                xbmc.log(f'[AIOStreams] Database: Marking episode S{season}E{episode} as unwatched', xbmc.LOGINFO)

                # Ensure show exists
                _ensure_show_exists(db, show_trakt_id, show_data)

                # Store original state
                original_states.append(db.fetchone(
                    "SELECT * FROM episodes WHERE show_trakt_id=? AND season=? AND episode=?",
                    (show_trakt_id, season, episode)
                ))

                # Mark episode as unwatched
                db.execute_sql("""
                    UPDATE episodes
                    SET watched=0, last_watched_at=NULL
                    WHERE show_trakt_id=? AND season=? AND episode=?
                """, (show_trakt_id, season, episode))

                xbmc.log(f'[AIOStreams] ✓ Marked ONLY episode S{season}E{episode} as unwatched', xbmc.LOGINFO)

            elif scenario == 'season':
                # Mark all episodes in season as unwatched
                xbmc.log(f'[AIOStreams] Database: Fetching all episodes for season {season}', xbmc.LOGINFO)

                # Ensure show exists
                _ensure_show_exists(db, show_trakt_id, show_data)

                # Get all episodes in this season from Trakt
                season_data = call_trakt(f'shows/{show_trakt_id}/seasons/{season}?extended=episodes')
                if season_data and isinstance(season_data, list):
                    xbmc.log(f'[AIOStreams] Found {len(season_data)} episodes in season {season}', xbmc.LOGINFO)

                    for ep in season_data:
                        ep_num = ep.get('number')
                        if ep_num:
                            # Store original state
                            original_states.append(db.fetchone(
                                "SELECT * FROM episodes WHERE show_trakt_id=? AND season=? AND episode=?",
                                (show_trakt_id, season, ep_num)
                            ))

                            # Mark episode as unwatched
                            db.execute_sql("""
                                UPDATE episodes
                                SET watched=0, last_watched_at=NULL
                                WHERE show_trakt_id=? AND season=? AND episode=?
                            """, (show_trakt_id, season, ep_num))

                    xbmc.log(f'[AIOStreams] ✓ Marked {len(season_data)} episodes in season {season} as unwatched', xbmc.LOGINFO)
                else:
                    xbmc.log(f'[AIOStreams] Warning: Could not fetch episodes for season {season}', xbmc.LOGWARNING)

            elif scenario == 'show':
                # Mark all episodes in all seasons as unwatched
                xbmc.log(f'[AIOStreams] Database: Fetching all seasons and episodes', xbmc.LOGINFO)

                # Ensure show exists
                _ensure_show_exists(db, show_trakt_id, show_data)

                # Get all seasons from Trakt
                seasons_data = call_trakt(f'shows/{show_trakt_id}/seasons?extended=episodes')
                if seasons_data and isinstance(seasons_data, list):
                    total_episodes = 0
                    for season_obj in seasons_data:
                        season_num = season_obj.get('number')
                        if season_num == 0:  # Skip specials
                            continue

                        episodes = season_obj.get('episodes', [])
                        xbmc.log(f'[AIOStreams] Season {season_num}: {len(episodes)} episodes', xbmc.LOGINFO)

                        for ep in episodes:
                            ep_num = ep.get('number')
                            if ep_num:
                                # Store original state
                                original_states.append(db.fetchone(
                                    "SELECT * FROM episodes WHERE show_trakt_id=? AND season=? AND episode=?",
                                    (show_trakt_id, season_num, ep_num)
                                ))

                                # Mark episode as unwatched
                                db.execute_sql("""
                                    UPDATE episodes
                                    SET watched=0, last_watched_at=NULL
                                    WHERE show_trakt_id=? AND season=? AND episode=?
                                """, (show_trakt_id, season_num, ep_num))
                                total_episodes += 1

                    xbmc.log(f'[AIOStreams] ✓ Marked {total_episodes} episodes across all seasons as unwatched', xbmc.LOGINFO)
                else:
                    xbmc.log(f'[AIOStreams] Warning: Could not fetch seasons/episodes', xbmc.LOGWARNING)

            elif scenario == 'movie':
                # Mark movie as unwatched
                xbmc.log(f'[AIOStreams] Database: Marking movie as unwatched', xbmc.LOGINFO)

                # Store original state
                original_states.append(db.fetchone(
                    "SELECT * FROM movies WHERE trakt_id=?",
                    (trakt_id,)
                ))

                # Mark movie as unwatched
                db.execute_sql("""
                    UPDATE movies
                    SET watched=0, last_watched_at=NULL
                    WHERE trakt_id=?
                """, (trakt_id,))

                xbmc.log(f'[AIOStreams] ✓ Marked movie as unwatched', xbmc.LOGINFO)

            # Clear caches
            if is_show_operation:
                xbmc.log(f'[AIOStreams] Clearing caches for show', xbmc.LOGINFO)
                if imdb_id in _show_progress_cache:
                    del _show_progress_cache[imdb_id]
                if imdb_id in _show_progress_batch_cache:
                    del _show_progress_batch_cache[imdb_id]
                if HAS_MODULES:
                    cache.delete_cached_data(f'show_progress_{show_trakt_id}', 'trakt')
                invalidate_progress_cache()

        except Exception as e:
            xbmc.log(f'[AIOStreams] Database update failed: {e}', xbmc.LOGERROR)
            import traceback
            xbmc.log(f'[AIOStreams] Traceback: {traceback.format_exc()}', xbmc.LOGERROR)

    # Show instant feedback
    if scenario == 'episode':
        xbmcgui.Dialog().notification('AIOStreams', f'Episode S{season}E{episode} marked as unwatched', xbmcgui.NOTIFICATION_INFO)
    elif scenario == 'season':
        xbmcgui.Dialog().notification('AIOStreams', f'Season {season} marked as unwatched', xbmcgui.NOTIFICATION_INFO)
    elif scenario == 'show':
        xbmcgui.Dialog().notification('AIOStreams', 'Show marked as unwatched', xbmcgui.NOTIFICATION_INFO)
    else:
        xbmcgui.Dialog().notification('AIOStreams', 'Marked as unwatched on Trakt', xbmcgui.NOTIFICATION_INFO)

    # Refresh container immediately for instant UI update
    if utils:
        utils.refresh_container()

    # 2. Background sync to Trakt API with rollback on failure
    def sync_to_trakt():
        """Background thread to sync to Trakt with rollback on failure."""
        # Build Trakt API request
        data = {api_type: []}
        item = {'ids': {'imdb': imdb_id}}

        if scenario == 'episode':
            item['seasons'] = [{'number': season, 'episodes': [{'number': episode}]}]
        elif scenario == 'season':
            item['seasons'] = [{'number': season}]  # No episodes array = marks all episodes in season
        # elif scenario == 'show': item has no seasons array = marks all episodes in all seasons

        data[api_type].append(item)

        import json
        xbmc.log(f'[AIOStreams] ====== TRAKT API REQUEST ======', xbmc.LOGINFO)
        xbmc.log(f'[AIOStreams] Scenario: {scenario.upper()} UNWATCHED', xbmc.LOGINFO)
        xbmc.log(f'[AIOStreams] Endpoint: sync/history/remove (POST)', xbmc.LOGINFO)
        xbmc.log(f'[AIOStreams] Request data:', xbmc.LOGINFO)
        xbmc.log(f'{json.dumps(data, indent=2)}', xbmc.LOGINFO)
        xbmc.log(f'[AIOStreams] ===============================', xbmc.LOGINFO)

        result = call_trakt('sync/history/remove', method='POST', data=data)

        xbmc.log(f'[AIOStreams] ====== TRAKT API RESPONSE ======', xbmc.LOGINFO)
        if result:
            xbmc.log(f'{json.dumps(result, indent=2)}', xbmc.LOGINFO)
        else:
            xbmc.log(f'[AIOStreams] No response received from Trakt', xbmc.LOGWARNING)
        xbmc.log(f'[AIOStreams] ================================', xbmc.LOGINFO)

        if not result:
            # Rollback database on API failure
            xbmc.log(f'[AIOStreams] Trakt API failed, rolling back unwatched status', xbmc.LOGWARNING)
            if db:
                _rollback_unwatched_changes(db, scenario, show_trakt_id, trakt_id, season, episode, original_states)
            xbmcgui.Dialog().notification('AIOStreams', 'Failed to sync to Trakt', xbmcgui.NOTIFICATION_ERROR)
        else:
            xbmc.log(f'[AIOStreams] ✓ Successfully synced to Trakt', xbmc.LOGINFO)

        # Trigger smart widget refresh after sync
        if utils:
            xbmc.log(f'[AIOStreams] Triggering background widget refresh', xbmc.LOGINFO)
            utils.trigger_background_refresh(delay=0.5)

    # Start background sync thread
    try:
        sync_thread = threading.Thread(target=sync_to_trakt)
        sync_thread.daemon = True
        sync_thread.start()
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to start background sync: {e}', xbmc.LOGERROR)
        # Fallback to synchronous sync
        sync_to_trakt()

    return True


def _rollback_unwatched_changes(db, scenario, show_trakt_id, trakt_id, season, episode, original_states):
    """Rollback database changes on Trakt API failure."""
    try:
        if scenario == 'episode':
            if original_states and original_states[0]:
                # Restore original state
                orig = original_states[0]
                db.execute_sql("""
                    UPDATE episodes
                    SET watched=?, last_watched_at=?
                    WHERE show_trakt_id=? AND season=? AND episode=?
                """, (
                    orig.get('watched', 0),
                    orig.get('last_watched_at'),
                    show_trakt_id,
                    season,
                    episode
                ))
        elif scenario in ['season', 'show']:
            # Rollback multiple episodes
            for orig in original_states:
                if orig:
                    db.execute_sql("""
                        UPDATE episodes
                        SET watched=?, last_watched_at=?
                        WHERE show_trakt_id=? AND season=? AND episode=?
                    """, (
                        orig.get('watched', 0),
                        orig.get('last_watched_at'),
                        orig['show_trakt_id'],
                        orig['season'],
                        orig['episode']
                    ))
        elif scenario == 'movie':
            if original_states and original_states[0]:
                orig = original_states[0]
                db.execute_sql("""
                    UPDATE movies
                    SET watched=?, last_watched_at=?
                    WHERE trakt_id=?
                """, (
                    orig.get('watched', 0),
                    orig.get('last_watched_at'),
                    trakt_id
                ))
        xbmc.log(f'[AIOStreams] Rollback completed', xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Rollback failed: {e}', xbmc.LOGERROR)



# Cache for watched status to avoid repeated API calls
_watched_cache = {}
_show_progress_cache = {}
_watchlist_cache = {}

# Batch cache for watched history (invalidated on watched status changes)
_watched_history_batch = {'movies': {}, 'shows': {}}
_watched_history_valid = {'movies': False, 'shows': False}

# Batch cache for watchlist (invalidated on watchlist changes)
_watchlist_batch = {'movies': {}, 'shows': {}}
_watchlist_valid = {'movies': False, 'shows': False}


def remove_from_playback(playback_id):
    """Remove item from continue watching (playback progress) without marking as watched."""
    if not playback_id:
        return False

    result = call_trakt(f'sync/playback/{playback_id}', method='DELETE')

    if result is not None:  # DELETE returns None on success
        xbmcgui.Dialog().notification('AIOStreams', 'Removed from Continue Watching', xbmcgui.NOTIFICATION_INFO)
        xbmc.executebuiltin('Container.Refresh')
        return True
    else:
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to remove from Continue Watching', xbmcgui.NOTIFICATION_ERROR)
        return False


def fetch_all_watchlist(media_type):
    """Batch fetch entire watchlist for a media type."""
    global _watchlist_batch, _watchlist_valid

    api_type = 'movies' if media_type == 'movie' else 'shows'

    # Return cached data if still valid
    if _watchlist_valid[api_type] and _watchlist_batch[api_type]:
        xbmc.log(f'[AIOStreams] Using cached watchlist for {api_type} ({len(_watchlist_batch[api_type])} items)', xbmc.LOGDEBUG)
        return _watchlist_batch[api_type]

    # Fetch entire watchlist
    try:
        result = call_trakt(f'sync/watchlist/{api_type}')
        if not result:
            _watchlist_batch[api_type] = {}
            _watchlist_valid[api_type] = True
            return {}

        # Build cache: {imdb_id: True}
        watchlist_dict = {}
        for item in result:
            # Use correct Trakt API key: 'movie' or 'show' (not 'series')
            item_key = 'movie' if media_type == 'movie' else 'show'
            item_data = item.get(item_key, {})
            item_imdb = item_data.get('ids', {}).get('imdb', '')
            if item_imdb:
                watchlist_dict[item_imdb] = True

        _watchlist_batch[api_type] = watchlist_dict
        _watchlist_valid[api_type] = True
        xbmc.log(f'[AIOStreams] Fetched and cached watchlist for {api_type}: {len(watchlist_dict)} items', xbmc.LOGDEBUG)
        return watchlist_dict

    except Exception as e:
        xbmc.log(f'[AIOStreams] Error fetching watchlist for {api_type}: {e}', xbmc.LOGERROR)
        _watchlist_batch[api_type] = {}
        _watchlist_valid[api_type] = True
        return {}


def is_in_watchlist(media_type, imdb_id):
    """Check if item is in Trakt watchlist using SQLite database.
    Falls back to API if database is unavailable.
    """
    if not imdb_id:
        return False
    
    # Try database first
    db = get_trakt_db()
    if db and db.connect():
        try:
            mediatype_filter = 'movie' if media_type == 'movie' else 'show'
            result = db.fetchone(
                "SELECT 1 FROM watchlist WHERE imdb_id=? AND mediatype=?",
                (imdb_id, mediatype_filter)
            )
            return result is not None
        except Exception as e:
            xbmc.log(f'[AIOStreams] Database error checking watchlist: {e}', xbmc.LOGWARNING)
        finally:
            db.disconnect()
    
    # Fallback to API cache
    api_type = 'movies' if media_type == 'movie' else 'shows'
    watchlist = fetch_all_watchlist(media_type)
    return imdb_id in watchlist


def fetch_all_watched_history(media_type):
    """Batch fetch entire watched history for a media type."""
    global _watched_history_batch, _watched_history_valid

    api_type = 'movies' if media_type == 'movie' else 'shows'

    # Return cached data if still valid
    if _watched_history_valid[api_type] and _watched_history_batch[api_type]:
        xbmc.log(f'[AIOStreams] Using cached watched history for {api_type} ({len(_watched_history_batch[api_type])} items)', xbmc.LOGDEBUG)
        return _watched_history_batch[api_type]

    # Fetch entire watched history
    try:
        result = call_trakt(f'sync/history/{api_type}', params={'limit': 1000})
        if not result:
            _watched_history_batch[api_type] = {}
            _watched_history_valid[api_type] = True
            return {}

        # Build cache: {imdb_id: True}
        watched_dict = {}
        for item in result:
            # Use correct Trakt API key: 'movie' or 'show' (not 'series')
            item_key = 'movie' if media_type == 'movie' else 'show'
            item_data = item.get(item_key, {})
            item_imdb = item_data.get('ids', {}).get('imdb', '')
            if item_imdb:
                watched_dict[item_imdb] = True

        _watched_history_batch[api_type] = watched_dict
        _watched_history_valid[api_type] = True
        xbmc.log(f'[AIOStreams] Fetched and cached watched history for {api_type}: {len(watched_dict)} items', xbmc.LOGDEBUG)
        return watched_dict

    except Exception as e:
        xbmc.log(f'[AIOStreams] Error fetching watched history for {api_type}: {e}', xbmc.LOGERROR)
        _watched_history_batch[api_type] = {}
        _watched_history_valid[api_type] = True
        return {}


def is_watched(media_type, imdb_id):
    """Check if item is watched using SQLite database.
    Falls back to API if database is unavailable.
    """
    if not imdb_id:
        return False
    
    # Try database first
    db = get_trakt_db()
    if db and db.connect():
        try:
            if media_type == 'movie':
                result = db.fetchone(
                    "SELECT watched FROM movies WHERE imdb_id=?",
                    (imdb_id,)
                )
                if result:
                    return result.get('watched', 0) == 1
            else:  # series/show
                # For shows, check if any episodes are watched
                result = db.fetchone(
                    "SELECT trakt_id FROM shows WHERE imdb_id=?",
                    (imdb_id,)
                )
                if result:
                    show_trakt_id = result.get('trakt_id')
                    # Check if there are any watched episodes
                    episode_result = db.fetchone(
                        "SELECT COUNT(*) as count FROM episodes WHERE show_trakt_id=? AND watched=1",
                        (show_trakt_id,)
                    )
                    if episode_result:
                        return episode_result.get('count', 0) > 0
            return False
        except Exception as e:
            xbmc.log(f'[AIOStreams] Database error checking watched status: {e}', xbmc.LOGWARNING)
        finally:
            db.disconnect()
    
    # Fallback to API cache
    api_type = 'movies' if media_type == 'movie' else 'shows'
    watched_history = fetch_all_watched_history(media_type)
    return imdb_id in watched_history


def get_show_progress(imdb_id):
    """Get show progress (which seasons/episodes are watched) using SQLite database.
    Falls back to API if database is unavailable.
    
    Uses event-driven caching that persists until watched status changes.
    """
    # Check in-memory cache first (fastest)
    if imdb_id in _show_progress_cache:
        xbmc.log(f'[AIOStreams] Cache HIT (memory): show_progress_{imdb_id}', xbmc.LOGDEBUG)
        return _show_progress_cache[imdb_id]
    
    # Try database
    db = get_trakt_db()
    if db and db.connect():
        try:
            # Get show info
            show = db.fetchone("SELECT trakt_id FROM shows WHERE imdb_id=?", (imdb_id,))
            if show:
                show_trakt_id = show.get('trakt_id')
                
                # Get all episodes for this show
                episodes = db.fetchall(
                    "SELECT season, episode, watched FROM episodes WHERE show_trakt_id=? ORDER BY season, episode",
                    (show_trakt_id,)
                )
                
                # Build progress structure compatible with Trakt API format
                progress = {
                    'aired': 0,
                    'completed': 0,
                    'seasons': []
                }
                
                # Group by season
                seasons_dict = {}
                next_episode = None
                
                for ep in episodes:
                    season_num = ep.get('season', 0)
                    episode_num = ep.get('episode', 0)
                    is_watched = ep.get('watched', 0) == 1
                    
                    if season_num not in seasons_dict:
                        seasons_dict[season_num] = {
                            'number': season_num,
                            'aired': 0,
                            'completed': 0,
                            'episodes': []
                        }
                    
                    seasons_dict[season_num]['aired'] += 1
                    progress['aired'] += 1
                    
                    if is_watched:
                        seasons_dict[season_num]['completed'] += 1
                        progress['completed'] += 1
                    else:
                        # Track first unwatched episode as next episode
                        if next_episode is None and season_num > 0:  # Ignore specials (season 0)
                            next_episode = {
                                'season': season_num,
                                'number': episode_num
                            }
                    
                    seasons_dict[season_num]['episodes'].append({
                        'number': episode_num,
                        'completed': is_watched
                    })
                
                progress['seasons'] = list(seasons_dict.values())
                if next_episode:
                    progress['next_episode'] = next_episode

                # Cache the result in memory only
                _show_progress_cache[imdb_id] = progress

                xbmc.log(f'[AIOStreams] Built show progress from database for {imdb_id}', xbmc.LOGDEBUG)
                return progress
        except Exception as e:
            xbmc.log(f'[AIOStreams] Database error getting show progress: {e}', xbmc.LOGWARNING)
        finally:
            db.disconnect()

    # Fallback to API call
    xbmc.log(f'[AIOStreams] Database unavailable, fetching show progress from API for {imdb_id}', xbmc.LOGDEBUG)
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
