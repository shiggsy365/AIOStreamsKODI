# -*- coding: utf-8 -*-
"""
Database migration from JSON cache to SQLite.
Migrates watchlist, watched status, and playback progress from old JSON files.
"""
import os
import json
import xbmc
import xbmcvfs
import xbmcaddon
from resources.lib.database.trakt_sync import TraktSyncDatabase


class DatabaseMigration:
    """Handle migration from JSON cache files to SQLite database."""
    
    def __init__(self):
        """Initialize migration handler."""
        self.addon = xbmcaddon.Addon()
        self.profile_path = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        self.cache_dir = os.path.join(self.profile_path, 'cache')
        self.db = TraktSyncDatabase()
        self.migration_flag = os.path.join(self.profile_path, '.migration_complete')
    
    def is_migration_needed(self):
        """Check if migration has already been completed.
        
        Returns:
            bool: True if migration is needed, False if already done
        """
        # If migration flag exists, migration is complete
        if xbmcvfs.exists(self.migration_flag):
            xbmc.log('[AIOStreams] Migration already completed', xbmc.LOGDEBUG)
            return False
        
        # Check if there are JSON cache files that might contain Trakt data
        if not xbmcvfs.exists(self.cache_dir):
            xbmc.log('[AIOStreams] No cache directory found, skipping migration', xbmc.LOGDEBUG)
            self._mark_migration_complete()
            return False
        
        # Check for any JSON files that might be old Trakt data
        try:
            dirs, files = xbmcvfs.listdir(self.cache_dir)
            json_files = [f for f in files if f.endswith('.json')]
            
            if not json_files:
                xbmc.log('[AIOStreams] No JSON cache files found, skipping migration', xbmc.LOGDEBUG)
                self._mark_migration_complete()
                return False
            
            xbmc.log(f'[AIOStreams] Found {len(json_files)} JSON cache files, migration may be needed', xbmc.LOGINFO)
            return True
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error checking for migration: {e}', xbmc.LOGERROR)
            return False
    
    def _mark_migration_complete(self):
        """Mark migration as complete by creating a flag file."""
        try:
            with open(self.migration_flag, 'w') as f:
                f.write('Migration completed')
            xbmc.log('[AIOStreams] Migration marked as complete', xbmc.LOGINFO)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Failed to create migration flag: {e}', xbmc.LOGERROR)
    
    def migrate(self):
        """Run full migration from JSON to SQLite.
        
        Returns:
            dict: Migration results with counts of migrated items
        """
        if not self.is_migration_needed():
            return {'skipped': True, 'reason': 'Migration already completed'}
        
        xbmc.log('[AIOStreams] Starting migration from JSON to SQLite', xbmc.LOGINFO)
        
        results = {
            'watchlist_movies': 0,
            'watchlist_shows': 0,
            'watched_movies': 0,
            'watched_episodes': 0,
            'playback_progress': 0,
            'errors': []
        }
        
        try:
            # Note: The old system didn't use JSON files for Trakt data persistently.
            # Trakt data was always fetched from the API on demand.
            # The JSON cache was only for AIOStreams metadata (manifest, catalogs, meta).
            # Therefore, there's no actual data to migrate from JSON to SQLite.
            
            # The SQLite database will be populated when:
            # 1. The service performs its first sync
            # 2. Users access Trakt lists (which trigger auto-sync)
            
            xbmc.log('[AIOStreams] No legacy Trakt data found in JSON cache (as expected)', xbmc.LOGINFO)
            xbmc.log('[AIOStreams] SQLite database will be populated on first sync', xbmc.LOGINFO)
            
            # Mark migration as complete so we don't check again
            self._mark_migration_complete()
            
        except Exception as e:
            error_msg = f'Migration error: {str(e)}'
            xbmc.log(f'[AIOStreams] {error_msg}', xbmc.LOGERROR)
            results['errors'].append(error_msg)
        
        return results
    
    def migrate_watchlist(self):
        """Migrate watchlist data from JSON cache.
        
        Since the old implementation didn't persistently cache watchlist in JSON,
        this is a no-op. Data will be fetched fresh from Trakt on first sync.
        
        Returns:
            int: Number of items migrated (always 0)
        """
        xbmc.log('[AIOStreams] Watchlist migration: No legacy data to migrate', xbmc.LOGDEBUG)
        return 0
    
    def migrate_watched_status(self):
        """Migrate watched status from JSON cache.
        
        Since the old implementation didn't persistently cache watched status in JSON,
        this is a no-op. Data will be fetched fresh from Trakt on first sync.
        
        Returns:
            int: Number of items migrated (always 0)
        """
        xbmc.log('[AIOStreams] Watched status migration: No legacy data to migrate', xbmc.LOGDEBUG)
        return 0
    
    def migrate_playback_progress(self):
        """Migrate playback progress from JSON cache.
        
        Since the old implementation didn't persistently cache playback progress in JSON,
        this is a no-op. Data will be fetched fresh from Trakt on first sync.
        
        Returns:
            int: Number of items migrated (always 0)
        """
        xbmc.log('[AIOStreams] Playback progress migration: No legacy data to migrate', xbmc.LOGDEBUG)
        return 0
