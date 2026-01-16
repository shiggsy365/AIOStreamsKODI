import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import os
import hashlib
import requests
import threading
import pickle
import time

# Try to import modules
try:
    from resources.lib import trakt
    HAS_MODULES = True
except ImportError:
    HAS_MODULES = False

# Cache for 404 responses to avoid retrying failed logo fetches
# Format: {cache_key: timestamp}
_clearlogo_404_cache = {}
_404_cache_ttl = 86400  # 24 hours in seconds

def _is_404_cached(content_type, meta_id):
    """Check if this logo previously returned 404."""
    cache_key = f"{content_type}_{meta_id}"
    if cache_key in _clearlogo_404_cache:
        age = time.time() - _clearlogo_404_cache[cache_key]
        if age < _404_cache_ttl:
            return True
        else:
            # Expired, remove it
            del _clearlogo_404_cache[cache_key]
    return False

def _cache_404(content_type, meta_id):
    """Mark this logo as 404 (not found)."""
    cache_key = f"{content_type}_{meta_id}"
    _clearlogo_404_cache[cache_key] = time.time()
    xbmc.log(f'[AIOStreams] Cached 404 for clearlogo: {cache_key}', xbmc.LOGDEBUG)

def get_addon():
    return xbmcaddon.Addon()

def get_setting(setting_id, default=None):
    """Get addon setting."""
    value = get_addon().getSetting(setting_id)
    return value if value else default

def get_clearlogo_cache_dir():
    """Get the clearlogo cache directory path, creating it if needed."""
    addon_data_path = xbmcvfs.translatePath(get_addon().getAddonInfo('profile'))
    clearlogo_dir = os.path.join(addon_data_path, 'clearlogos')
    
    if not xbmcvfs.exists(clearlogo_dir):
        xbmcvfs.mkdirs(clearlogo_dir)
        xbmc.log(f'[AIOStreams] Created clearlogo cache directory: {clearlogo_dir}', xbmc.LOGDEBUG)
    
    return clearlogo_dir

def get_cached_clearlogo_path(content_type, meta_id):
    """Get the cached clearlogo file path if it exists."""
    safe_id = hashlib.md5(f"{content_type}_{meta_id}".encode()).hexdigest()
    clearlogo_dir = get_clearlogo_cache_dir()
    clearlogo_path = os.path.join(clearlogo_dir, f"{safe_id}.png")
    
    if xbmcvfs.exists(clearlogo_path):
        return f"special://userdata/addon_data/plugin.video.aiostreams/clearlogos/{safe_id}.png"
    
    return None

def download_and_cache_clearlogo(url, content_type, meta_id):
    """Download clearlogo image and cache it to local file."""
    if not url:
        return None

    # Check if this logo previously returned 404
    if _is_404_cached(content_type, meta_id):
        xbmc.log(f'[AIOStreams] Skipping clearlogo fetch (cached 404): {content_type}/{meta_id}', xbmc.LOGDEBUG)
        return None

    try:
        cached_path = get_cached_clearlogo_path(content_type, meta_id)
        if cached_path:
            return cached_path

        # Determine timeout from settings
        try:
            timeout = int(get_setting('timeout', '10'))
        except ValueError:
            timeout = 10

        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        safe_id = hashlib.md5(f"{content_type}_{meta_id}".encode()).hexdigest()
        clearlogo_dir = get_clearlogo_cache_dir()
        clearlogo_path = os.path.join(clearlogo_dir, f"{safe_id}.png")

        with open(clearlogo_path, 'wb') as f:
            f.write(response.content)

        xbmc.log(f'[AIOStreams] Cached clearlogo for {content_type}/{meta_id}: {clearlogo_path}', xbmc.LOGINFO)
        return clearlogo_path

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            # Cache 404 to avoid retrying
            _cache_404(content_type, meta_id)
            xbmc.log(f'[AIOStreams] Clearlogo not found (404), caching failure: {content_type}/{meta_id}', xbmc.LOGDEBUG)
        else:
            xbmc.log(f'[AIOStreams] Error caching clearlogo for {content_type}/{meta_id}: {e}', xbmc.LOGERROR)
        return None
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error caching clearlogo for {content_type}/{meta_id}: {e}', xbmc.LOGERROR)
        return None

def clear_clearlogo_cache():
    """Delete all cached clearlogo files."""
    import shutil
    try:
        clearlogo_dir = get_clearlogo_cache_dir()
        if xbmcvfs.exists(clearlogo_dir):
            shutil.rmtree(clearlogo_dir)
            xbmc.log('[AIOStreams] Cleared clearlogo cache', xbmc.LOGINFO)
            xbmcvfs.mkdirs(clearlogo_dir)
            return True
        return True
    except Exception as e:
        xbmc.log(f'[AIOStreams] Error clearing clearlogo cache: {e}', xbmc.LOGERROR)
        return False

def check_missing_clearlogos_on_startup():
    """Check for missing clearlogos and download them in background."""
    def background_check():
        try:
            if not HAS_MODULES:
                return
            
            xbmc.log('[AIOStreams] Starting background clearlogo check', xbmc.LOGINFO)
            
            db = trakt.get_trakt_db()
            if not db:
                return
            
            missing_count = 0
            downloaded_count = 0
            
            for c_type in ['movie', 'series']:
                try:
                    if db.connect():
                        cursor = db.execute(f"SELECT id, content_type, metadata FROM metas WHERE content_type = '{c_type}'")
                        if cursor:
                            for row in cursor.fetchall():
                                meta_id = row['id']
                                content_type = row['content_type']
                                
                                if not get_cached_clearlogo_path(content_type, meta_id):
                                    try:
                                        metadata = pickle.loads(row['metadata'])
                                        clearlogo_url = metadata.get('meta', {}).get('logo')
                                        if clearlogo_url:
                                            missing_count += 1
                                            if download_and_cache_clearlogo(clearlogo_url, content_type, meta_id):
                                                downloaded_count += 1
                                    except:
                                        pass
                        db.disconnect()
                except Exception as e:
                    xbmc.log(f'[AIOStreams] Error checking {c_type} clearlogos: {e}', xbmc.LOGERROR)
            
            if missing_count > 0:
                xbmc.log(f'[AIOStreams] Clearlogo check complete: {downloaded_count}/{missing_count} downloaded', xbmc.LOGINFO)
            else:
                xbmc.log('[AIOStreams] No missing clearlogos found', xbmc.LOGDEBUG)
                
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error in background clearlogo check: {e}', xbmc.LOGERROR)
    
    try:
        if get_setting('startup_clearlogo_check', 'false') == 'true':
            thread = threading.Thread(target=background_check)
            thread.daemon = True
            thread.start()
            xbmc.log('[AIOStreams] Started background clearlogo check thread', xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Failed to start clearlogo check thread: {e}', xbmc.LOGERROR)
