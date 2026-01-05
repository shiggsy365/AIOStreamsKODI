"""
Disk-based metadata cache for AIOStreams API calls.
Reduces duplicate API calls with zero RAM impact.
Stores cache files on disk with 30-day automatic cleanup.
"""

import os
import json
import time
import hashlib
import xbmc
import xbmcaddon
import xbmcvfs


def get_cache_dir():
    """Get cache directory path."""
    addon = xbmcaddon.Addon()
    profile_path = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
    cache_dir = os.path.join(profile_path, 'cache')
    
    # Create cache directory if it doesn't exist
    if not xbmcvfs.exists(cache_dir):
        xbmcvfs.mkdirs(cache_dir)
    
    return cache_dir


def get_cache_key(content_type, item_id):
    """Generate cache filename from content_type and item_id."""
    # Use hash to keep filenames short and valid
    key_string = f"{content_type}:{item_id}"
    key_hash = hashlib.md5(key_string.encode()).hexdigest()
    return f"{key_hash}.json"


def get_cached_meta(content_type, item_id):
    """Get metadata from disk cache if available and not expired."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, get_cache_key(content_type, item_id))
    
    if not xbmcvfs.exists(cache_file):
        return None
    
    try:
        # Read cache file
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
        
        timestamp = cache_data.get('timestamp', 0)
        
        # Check if cache is still valid (30 days = 2592000 seconds)
        if time.time() - timestamp < 2592000:
            xbmc.log(f'[AIOStreams] Cache HIT: {content_type}:{item_id}', xbmc.LOGDEBUG)
            return cache_data.get('data')
        else:
            # Expired, delete file
            xbmcvfs.delete(cache_file)
            xbmc.log(f'[AIOStreams] Cache EXPIRED: {content_type}:{item_id}', xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Cache read error: {e}', xbmc.LOGERROR)
    
    return None


def cache_meta(content_type, item_id, metadata):
    """Store metadata in disk cache."""
    cache_dir = get_cache_dir()
    cache_file = os.path.join(cache_dir, get_cache_key(content_type, item_id))
    
    try:
        cache_data = {
            'timestamp': time.time(),
            'content_type': content_type,
            'item_id': item_id,
            'data': metadata
        }
        
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
        
        xbmc.log(f'[AIOStreams] Cache SET: {content_type}:{item_id}', xbmc.LOGDEBUG)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Cache write error: {e}', xbmc.LOGERROR)


def cleanup_expired_cache(force_all=False):
    """Remove cache files older than 30 days, or all files if force_all=True."""
    cache_dir = get_cache_dir()

    if not xbmcvfs.exists(cache_dir):
        return

    try:
        dirs, files = xbmcvfs.listdir(cache_dir)
        expired_count = 0

        for filename in files:
            if not filename.endswith('.json'):
                continue

            file_path = os.path.join(cache_dir, filename)

            if force_all:
                # Force delete all cache files
                try:
                    os.remove(file_path)
                    expired_count += 1
                except:
                    pass
                continue

            try:
                with open(file_path, 'r') as f:
                    cache_data = json.load(f)
                
                timestamp = cache_data.get('timestamp', 0)
                
                # Delete if older than 30 days
                if time.time() - timestamp >= 2592000:
                    xbmcvfs.delete(file_path)
                    expired_count += 1
            except:
                # Delete corrupted cache files
                xbmcvfs.delete(file_path)
        
        if expired_count > 0:
            xbmc.log(f'[AIOStreams] Cleaned up {expired_count} expired cache files', xbmc.LOGINFO)
    except Exception as e:
        xbmc.log(f'[AIOStreams] Cache cleanup error: {e}', xbmc.LOGERROR)
