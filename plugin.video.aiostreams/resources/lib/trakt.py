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
    HAS_MODULES = True
except:
    HAS_MODULES = False
    cache = None

ADDON = xbmcaddon.Addon()
API_ENDPOINT = 'https://api.trakt.tv'
API_VERSION = '2'

# In-memory cache for batch show progress (invalidated on watched status changes)
_show_progress_batch_cache = {}
_show_progress_cache_valid = False

# In-memory cache for show progress with next episode (invalidated on watched status changes)
_show_progress_with_next_cache = {}

# Track recently updated shows to handle Trakt's eventual consistency
_pending_show_updates = {}  # {show_trakt_id: timestamp}


def invalidate_progress_cache():
    """Invalidate the batch show progress cache (call when watched status changes).
    
    Clears both in-memory and disk caches for show progress.
    """
    global _show_progress_cache_valid, _show_progress_with_next_cache, _show_progress_batch_cache, _show_progress_cache, _pending_show_updates
    _show_progress_cache_valid = False
    _show_progress_with_next_cache.clear()
    _show_progress_batch_cache.clear()
    _show_progress_cache.clear()
    _pending_show_updates.clear()  # Clear pending updates when full invalidation
    
    # Clear all disk-cached show progress (both Trakt ID and IMDB ID based)
    if HAS_MODULES:
        import os
        cache_dir = cache.get_cache_dir()
        try:
            dirs, files = xbmcvfs.listdir(cache_dir)
            cleared_count = 0
            for filename in files:
                # Clear files matching show_progress_* pattern
                if filename.startswith('show_progress_') and filename.endswith('.json'):
                    file_path = os.path.join(cache_dir, filename)
                    try:
                        os.remove(file_path)
                        cleared_count += 1
                    except:
                        pass
            if cleared_count > 0:
                xbmc.log(f'[AIOStreams] Cleared {cleared_count} show progress cache files from disk', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error clearing show progress cache: {e}', xbmc.LOGERROR)
    
    xbmc.log('[AIOStreams] Trakt progress cache invalidated (memory + disk)', xbmc.LOGDEBUG)


def get_all_show_progress():
    """Fetch progress for ALL shows in one API call and cache in memory."""
    global _show_progress_batch_cache, _show_progress_cache_valid

    # Return cached data if still valid
    if _show_progress_cache_valid and _show_progress_batch_cache:
        xbmc.log(f'[AIOStreams] Using cached show progress ({len(_show_progress_batch_cache)} shows)', xbmc.LOGDEBUG)
        return _show_progress_batch_cache

    # Fetch all show progress from Trakt
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
                # Store the whole show data for progress calculations
                _show_progress_batch_cache[imdb_id] = show

        _show_progress_cache_valid = True
        xbmc.log(f'[AIOStreams] Fetched and cached progress for {len(_show_progress_batch_cache)} shows', xbmc.LOGDEBUG)
        return _show_progress_batch_cache

    except Exception as e:
        xbmc.log(f'[AIOStreams] Error fetching batch show progress: {e}', xbmc.LOGERROR)
        return {}


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
    """Get progress for a specific show by Trakt ID (includes next episode).
    
    Uses event-driven caching that persists until watched status changes.
    Handles Trakt's eventual consistency by not caching recently updated shows.
    """
    global _show_progress_with_next_cache, _pending_show_updates

    # Check if this show was recently updated (within last 10 seconds)
    recently_updated = False
    if show_id in _pending_show_updates:
        update_time = _pending_show_updates[show_id]
        age = time.time() - update_time
        if age < 10:  # 10 second grace period for Trakt to process
            recently_updated = True
            xbmc.log(f'[AIOStreams] Show {show_id} was recently updated ({age:.1f}s ago), skipping cache', xbmc.LOGDEBUG)
        else:
            # Update is old enough, remove from pending
            del _pending_show_updates[show_id]

    # Check in-memory cache first (fastest) - but not if recently updated
    if not recently_updated and show_id in _show_progress_with_next_cache:
        xbmc.log(f'[AIOStreams] Cache HIT (memory): show_progress_trakt_{show_id}', xbmc.LOGDEBUG)
        return _show_progress_with_next_cache[show_id]

    # Check disk cache - but not if recently updated
    if not recently_updated and HAS_MODULES:
        # Use 1 year TTL (event-driven cache, only cleared on watched changes)
        cached = cache.get_cached_data(f'show_progress_trakt_{show_id}', 'trakt', ttl_seconds=31536000)
        if cached:
            xbmc.log(f'[AIOStreams] Cache HIT (disk): show_progress_trakt_{show_id}', xbmc.LOGDEBUG)
            _show_progress_with_next_cache[show_id] = cached
            return cached

    # Fetch from API
    xbmc.log(f'[AIOStreams] Cache MISS: Fetching show_progress_trakt_{show_id} from API', xbmc.LOGDEBUG)
    result = call_trakt(f'shows/{show_id}/progress/watched')

    # Only cache if not recently updated
    if result and not recently_updated:
        _show_progress_with_next_cache[show_id] = result
        if HAS_MODULES:
            cache.cache_data(f'show_progress_trakt_{show_id}', 'trakt', result)
            xbmc.log(f'[AIOStreams] Cached show_progress_trakt_{show_id} to disk', xbmc.LOGDEBUG)
    elif result and recently_updated:
        xbmc.log(f'[AIOStreams] Fetched show_progress_trakt_{show_id} but NOT caching (recently updated)', xbmc.LOGDEBUG)

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

    xbmc.log(f'[AIOStreams] Dropping {media_type} ({imdb_id}) from all sections', xbmc.LOGINFO)
    xbmc.log(f'[AIOStreams] API data: {data}', xbmc.LOGDEBUG)

    success_count = 0

    # Hide from all relevant sections for complete "Drop" functionality
    sections = ['progress_watched', 'calendar', 'recommendations']

    for section in sections:
        xbmc.log(f'[AIOStreams] Hiding from section: {section}', xbmc.LOGDEBUG)
        result = call_trakt(f'users/hidden/{section}', method='POST', data=data)
        if result:
            # Log detailed response for debugging
            xbmc.log(f'[AIOStreams] API Response for {section}: {result}', xbmc.LOGDEBUG)

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

        return True
    else:
        xbmc.log(f'[AIOStreams] Failed to drop {media_type} ({imdb_id}) from all sections', xbmc.LOGERROR)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to drop from watching', xbmcgui.NOTIFICATION_ERROR)
        return False


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
    """Add item to watchlist."""
    # For episodes/shows/series, we use 'shows' in the API
    api_type = 'shows' if media_type in ['episode', 'show', 'series'] or season is not None else media_type + 's'

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

        # Invalidate batch watchlist cache
        global _watchlist_valid
        _watchlist_valid['movies'] = False
        _watchlist_valid['shows'] = False

        xbmcgui.Dialog().notification('AIOStreams', 'Added to Trakt watchlist', xbmcgui.NOTIFICATION_INFO)
        return True

    return False


def remove_from_watchlist(media_type, imdb_id, season=None, episode=None):
    """Remove item from watchlist."""
    # For episodes/shows/series, we use 'shows' in the API
    api_type = 'shows' if media_type in ['episode', 'show', 'series'] or season is not None else media_type + 's'

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

        # Invalidate batch watchlist cache
        global _watchlist_valid
        _watchlist_valid['movies'] = False
        _watchlist_valid['shows'] = False

        xbmcgui.Dialog().notification('AIOStreams', 'Removed from Trakt watchlist', xbmcgui.NOTIFICATION_INFO)
        return True

    return False


def mark_watched(media_type, imdb_id, season=None, episode=None, playback_id=None):
    """Mark item as watched and clear any in-progress status."""
    global _pending_show_updates
    
    if not imdb_id:
        xbmc.log('[AIOStreams] Cannot mark as watched: no IMDB ID provided', xbmc.LOGWARNING)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to mark as watched: Invalid ID', xbmcgui.NOTIFICATION_ERROR)
        return False

    # For episodes/shows/series, we use 'shows' in the API
    api_type = 'shows' if media_type in ['episode', 'show', 'series'] or season is not None else media_type + 's'

    # Add to watch history
    data = {api_type: []}

    item = {'ids': {'imdb': imdb_id}}
    if season is not None:
        item['seasons'] = [{'number': season}]
        if episode is not None:
            item['seasons'][0]['episodes'] = [{'number': episode}]

    data[api_type].append(item)

    xbmc.log(f'[AIOStreams] Marking as watched: media_type={media_type}, imdb_id={imdb_id}, season={season}, episode={episode}', xbmc.LOGINFO)
    xbmc.log(f'[AIOStreams] API request: POST sync/history - data: {data}', xbmc.LOGDEBUG)

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

        # Invalidate batch progress cache (also clears disk cache)
        invalidate_progress_cache()

        # Get Trakt ID for this show to track pending update (AFTER invalidation)
        if api_type == 'shows':
            # Fetch show data to get Trakt ID
            show_data = call_trakt(f'search/imdb/{imdb_id}', with_auth=False)
            if show_data and isinstance(show_data, list) and len(show_data) > 0:
                show_trakt_id = show_data[0].get('show', {}).get('ids', {}).get('trakt')
                if show_trakt_id:
                    _pending_show_updates[show_trakt_id] = time.time()
                    xbmc.log(f'[AIOStreams] Added show {show_trakt_id} to pending updates (10s grace period)', xbmc.LOGDEBUG)

        # Invalidate batch watched history cache
        global _watched_history_valid
        _watched_history_valid['movies'] = False
        _watched_history_valid['shows'] = False

        xbmcgui.Dialog().notification('AIOStreams', 'Marked as watched on Trakt', xbmcgui.NOTIFICATION_INFO)
        return True

    return False


def mark_unwatched(media_type, imdb_id, season=None, episode=None):
    """Remove item from watch history."""
    global _pending_show_updates
    
    if not imdb_id:
        xbmc.log('[AIOStreams] Cannot mark as unwatched: no IMDB ID provided', xbmc.LOGWARNING)
        xbmcgui.Dialog().notification('AIOStreams', 'Failed to mark as unwatched: Invalid ID', xbmcgui.NOTIFICATION_ERROR)
        return False

    # For episodes/shows/series, we use 'shows' in the API
    api_type = 'shows' if media_type in ['episode', 'show', 'series'] or season is not None else media_type + 's'

    # Remove from watch history
    data = {api_type: []}

    item = {'ids': {'imdb': imdb_id}}
    if season is not None:
        item['seasons'] = [{'number': season}]
        if episode is not None:
            item['seasons'][0]['episodes'] = [{'number': episode}]

    data[api_type].append(item)

    xbmc.log(f'[AIOStreams] Marking as unwatched: media_type={media_type}, imdb_id={imdb_id}, season={season}, episode={episode}', xbmc.LOGINFO)
    xbmc.log(f'[AIOStreams] API request: POST sync/history/remove - data: {data}', xbmc.LOGDEBUG)

    result = call_trakt('sync/history/remove', method='POST', data=data)

    if result:
        # Clear watched cache
        cache_key = f"{media_type}:{imdb_id}"
        if cache_key in _watched_cache:
            del _watched_cache[cache_key]
        if imdb_id in _show_progress_cache:
            del _show_progress_cache[imdb_id]

        # Invalidate batch progress cache (also clears disk cache)
        invalidate_progress_cache()

        # Get Trakt ID for this show to track pending update (AFTER invalidation)
        if api_type == 'shows':
            # Fetch show data to get Trakt ID
            show_data = call_trakt(f'search/imdb/{imdb_id}', with_auth=False)
            if show_data and isinstance(show_data, list) and len(show_data) > 0:
                show_trakt_id = show_data[0].get('show', {}).get('ids', {}).get('trakt')
                if show_trakt_id:
                    _pending_show_updates[show_trakt_id] = time.time()
                    xbmc.log(f'[AIOStreams] Added show {show_trakt_id} to pending updates (10s grace period)', xbmc.LOGDEBUG)

        # Invalidate batch watched history cache
        global _watched_history_valid
        _watched_history_valid['movies'] = False
        _watched_history_valid['shows'] = False

        xbmcgui.Dialog().notification('AIOStreams', 'Marked as unwatched on Trakt', xbmcgui.NOTIFICATION_INFO)
        return True

    return False


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
    """Check if item is in Trakt watchlist using batch cache."""
    if not imdb_id:
        return False

    api_type = 'movies' if media_type == 'movie' else 'shows'

    # Fetch all watchlist items (uses cache if available)
    watchlist = fetch_all_watchlist(media_type)

    # Check if item is in watchlist
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
    """Check if item is watched in Trakt history using batch cache."""
    if not imdb_id:
        return False

    api_type = 'movies' if media_type == 'movie' else 'shows'

    # Fetch all watched history items (uses cache if available)
    watched_history = fetch_all_watched_history(media_type)

    # Check if item is in watched history
    return imdb_id in watched_history


def get_show_progress(imdb_id):
    """Get show progress from Trakt (which seasons/episodes are watched).
    
    Uses event-driven caching that persists until watched status changes.
    """
    # Check in-memory cache first (fastest)
    if imdb_id in _show_progress_cache:
        xbmc.log(f'[AIOStreams] Cache HIT (memory): show_progress_{imdb_id}', xbmc.LOGDEBUG)
        return _show_progress_cache[imdb_id]
    
    # Check disk cache (persists until invalidated by watched status change)
    if HAS_MODULES:
        # Use 1 year TTL (event-driven cache, only cleared on watched changes)
        cached = cache.get_cached_data(f'show_progress_{imdb_id}', 'trakt', ttl_seconds=31536000)
        if cached:
            xbmc.log(f'[AIOStreams] Cache HIT (disk): show_progress_{imdb_id}', xbmc.LOGDEBUG)
            _show_progress_cache[imdb_id] = cached
            return cached
    
    # Get show progress from Trakt
    xbmc.log(f'[AIOStreams] Cache MISS: Fetching show_progress_{imdb_id} from API', xbmc.LOGDEBUG)
    result = call_trakt(f'shows/{imdb_id}/progress/watched')
    
    if result:
        _show_progress_cache[imdb_id] = result
        # Cache to disk as well
        if HAS_MODULES:
            cache.cache_data(f'show_progress_{imdb_id}', 'trakt', result)
            xbmc.log(f'[AIOStreams] Cached show_progress_{imdb_id} to disk', xbmc.LOGDEBUG)
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
