# -*- coding: utf-8 -*-
"""
Shared cache management for AIOStreams addon.
Manages cache directories that are shared across all Kodi profiles to save disk space.
"""
import os
import xbmc
import xbmcvfs


class SharedCacheManager:
    """
    Manages shared cache directories that persist across Kodi profiles.
    
    Uses special://masterprofile for shared data storage, which is accessible
    by all Kodi profiles. This is used for:
    - Metadata cache (movie/show info from AIOStreams)
    - Clearlogo cache (logo images)
    
    Benefits:
    - Reduces disk space usage (no duplicate cache files)
    - Reduces API calls (metadata cached once for all profiles)
    - Faster load times for subsequent profiles
    """
    
    # Shared cache base directory (outside any specific profile)
    _SHARED_BASE = 'special://masterprofile/addon_data/plugin.video.aiostreams/'
    _directories_ensured = False
    
    @staticmethod
    def get_shared_cache_dir():
        """
        Get shared metadata cache directory.
        
        Returns:
            str: Absolute path to shared cache directory
        """
        path = xbmcvfs.translatePath(
            os.path.join(SharedCacheManager._SHARED_BASE, 'shared_cache')
        )
        return path
    
    @staticmethod
    def get_shared_clearlogo_dir():
        """
        Get shared clearlogo cache directory.
        
        Returns:
            str: Absolute path to shared clearlogo directory
        """
        path = xbmcvfs.translatePath(
            os.path.join(SharedCacheManager._SHARED_BASE, 'shared_clearlogos')
        )
        return path
    
    @staticmethod
    def ensure_shared_dirs():
        """
        Create shared cache directories if they don't exist.
        
        This should be called during addon initialization to ensure
        shared directories are available before first use.
        
        Returns:
            bool: True if directories exist or were created successfully
        """
        # Use Window property as a session-level guard (persists across processes)
        import xbmcgui
        win = xbmcgui.Window(10000)
        if win.getProperty('AIOStreams.SharedDirsEnsured') == 'true':
            return True

        if SharedCacheManager._directories_ensured:
            return True

        try:
            shared_cache = SharedCacheManager.get_shared_cache_dir()
            shared_clearlogos = SharedCacheManager.get_shared_clearlogo_dir()
            
            for dir_path in [shared_cache, shared_clearlogos]:
                if not xbmcvfs.exists(dir_path):
                    xbmcvfs.mkdirs(dir_path)
                    xbmc.log(
                        f'[AIOStreams] Created shared directory: {dir_path}',
                        xbmc.LOGDEBUG
                    )
                else:
                    xbmc.log(f'[AIOStreams] Shared directory exists: {dir_path}', xbmc.LOGDEBUG)
            
            SharedCacheManager._directories_ensured = True
            win.setProperty('AIOStreams.SharedDirsEnsured', 'true')
            return True
            
        except Exception as e:
            xbmc.log(
                f'[AIOStreams] Failed to create shared directories: {e}',
                xbmc.LOGERROR
            )
            return False
    
    @staticmethod
    def get_cache_stats():
        """
        Get statistics about shared cache usage.
        
        Returns:
            dict: Cache statistics including file counts and sizes
        """
        stats = {
            'metadata_cache': {'files': 0, 'size_bytes': 0},
            'clearlogo_cache': {'files': 0, 'size_bytes': 0}
        }
        
        try:
            # Count metadata cache files
            cache_dir = SharedCacheManager.get_shared_cache_dir()
            if xbmcvfs.exists(cache_dir):
                dirs, files = xbmcvfs.listdir(cache_dir)
                stats['metadata_cache']['files'] = len(files)
                for filename in files:
                    file_path = os.path.join(cache_dir, filename)
                    try:
                        stats['metadata_cache']['size_bytes'] += os.path.getsize(file_path)
                    except:
                        pass
            
            # Count clearlogo files
            clearlogo_dir = SharedCacheManager.get_shared_clearlogo_dir()
            if xbmcvfs.exists(clearlogo_dir):
                dirs, files = xbmcvfs.listdir(clearlogo_dir)
                stats['clearlogo_cache']['files'] = len(files)
                for filename in files:
                    file_path = os.path.join(clearlogo_dir, filename)
                    try:
                        stats['clearlogo_cache']['size_bytes'] += os.path.getsize(file_path)
                    except:
                        pass
        
        except Exception as e:
            xbmc.log(
                f'[AIOStreams] Error getting cache stats: {e}',
                xbmc.LOGERROR
            )
        
        return stats
