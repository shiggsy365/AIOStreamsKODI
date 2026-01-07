# -*- coding: utf-8 -*-
"""
Trakt activities-based delta sync coordinator.
Implements intelligent timestamp-based sync to minimize API calls (90%+ reduction).

Based on Seren's activities sync implementation:
https://github.com/nixgates/plugin.video.seren/blob/b4f4b63bf59b38b93bd565a8503e121f64c91e30/resources/lib/database/trakt_sync/activities.py
"""
import time
import xbmc
import xbmcgui
from resources.lib.database.trakt_sync import TraktSyncDatabase as BaseTraktDB
from resources.lib import trakt


class TraktSyncDatabase(BaseTraktDB):
    """Trakt activities sync coordinator with delta sync logic."""
    
    def __init__(self):
        super().__init__()
        self.progress_dialog = None
        self.sync_errors = []
    
    # ===== Activities API =====
    
    def fetch_remote_activities(self, silent=False, force=False):
        """Fetch /sync/last_activities with 5-minute throttle.

        Args:
            silent: If False, log throttle messages
            force: If True, bypass throttle check

        Returns:
            dict: Activities JSON from Trakt, or None if called too soon
        """
        # Get last call timestamp from database
        activities = self.fetchone("SELECT last_activities_call FROM activities WHERE sync_id=1")

        if activities and not force:
            last_call = activities.get('last_activities_call', 0)
            # Throttle to 5 minutes
            if time.time() < (last_call + (5 * 60)):
                if not silent:
                    xbmc.log('[AIOStreams] Activities called too recently, skipping sync', xbmc.LOGINFO)
                return None
        
        # Fetch from Trakt
        try:
            remote_activities = trakt.call_trakt('sync/last_activities', with_auth=True)
            
            # Update last call timestamp
            self.execute_sql(
                "UPDATE activities SET last_activities_call=? WHERE sync_id=1",
                (int(time.time()),)
            )
            
            return remote_activities
        except Exception as e:
            xbmc.log(f'[AIOStreams] Failed to fetch activities: {e}', xbmc.LOGERROR)
            return None
    
    # ===== Main Sync Coordinator =====
    
    def sync_activities(self, silent=False, force=False):
        """Main sync coordinator - compares timestamps and syncs only changed data.

        Args:
            silent: If False, show progress dialog
            force: If True, bypass throttle check

        Returns:
            bool: True if sync completed without errors, False if errors occurred,
                  None if sync was skipped (throttled)
        """
        self.sync_errors = []

        # Fetch remote activities (throttled unless force=True)
        remote_activities = self.fetch_remote_activities(silent=silent, force=force)
        
        if remote_activities is None:
            return None  # Too soon since last sync
        
        # Show progress dialog unless silent
        if not silent:
            self.progress_dialog = xbmcgui.DialogProgress()
            self.progress_dialog.create('AIOStreams', 'Syncing with Trakt...')
        
        try:
            # Get local activities from database
            local_activities = self.get_local_activities()
            
            # Compare timestamps and sync changed categories
            sync_tasks = []
            
            # Movies - Watched
            if self._should_sync('movies', 'watched_at', local_activities, remote_activities):
                sync_tasks.append(('Syncing watched movies...', self._sync_watched_movies))
            
            # Movies - Collected
            if self._should_sync('movies', 'collected_at', local_activities, remote_activities):
                sync_tasks.append(('Syncing movie collection...', self._sync_collected_movies))
            
            # Movies - Watchlist
            if self._should_sync('movies', 'watchlisted_at', local_activities, remote_activities):
                sync_tasks.append(('Syncing movie watchlist...', self._sync_movie_watchlist))
            
            # Episodes - Watched
            if self._should_sync('episodes', 'watched_at', local_activities, remote_activities):
                sync_tasks.append(('Syncing watched episodes...', self._sync_watched_episodes))
            
            # Episodes - Collected
            if self._should_sync('episodes', 'collected_at', local_activities, remote_activities):
                sync_tasks.append(('Syncing episode collection...', self._sync_collected_episodes))
            
            # Shows - Watchlist
            if self._should_sync('shows', 'watchlisted_at', local_activities, remote_activities):
                sync_tasks.append(('Syncing show watchlist...', self._sync_show_watchlist))
            
            # Always sync playback progress (bookmarks)
            sync_tasks.append(('Syncing playback progress...', self._sync_playback_progress))
            
            # Always sync hidden items
            sync_tasks.append(('Syncing hidden items...', self._sync_hidden_items))
            
            # Execute sync tasks with progress updates
            total_tasks = len(sync_tasks)
            for index, (message, task_func) in enumerate(sync_tasks):
                if self.progress_dialog:
                    percent = int((index / total_tasks) * 100)
                    self.progress_dialog.update(percent, message)
                    
                    # Check if user cancelled
                    if self.progress_dialog.iscanceled():
                        xbmc.log('[AIOStreams] Sync cancelled by user', xbmc.LOGINFO)
                        return False
                
                try:
                    task_func()
                except Exception as e:
                    error_msg = f'Error in {message}: {e}'
                    xbmc.log(f'[AIOStreams] {error_msg}', xbmc.LOGERROR)
                    self.sync_errors.append(error_msg)
            
            # Update local activities timestamps to match remote
            self._update_local_activities(remote_activities)
            
            # Finalize
            self._finalize_sync(silent)
            
            return len(self.sync_errors) == 0
            
        finally:
            if self.progress_dialog:
                self.progress_dialog.close()
                self.progress_dialog = None
    
    # ===== Helper Methods =====
    
    def _should_sync(self, category, field, local_activities, remote_activities):
        """Compare timestamps to determine if category needs syncing.
        
        Args:
            category: 'movies', 'episodes', or 'shows'
            field: 'watched_at', 'collected_at', or 'watchlisted_at'
            local_activities: Local timestamp dict
            remote_activities: Remote timestamp dict from Trakt
        
        Returns:
            bool: True if remote is newer than local
        """
        local_time = local_activities.get(f'{category}_{field}', '1970-01-01T00:00:00')
        remote_time = remote_activities.get(category, {}).get(field, '1970-01-01T00:00:00')
        
        # Parse ISO timestamps and compare
        needs_sync = remote_time > local_time
        
        if needs_sync:
            xbmc.log(
                f'[AIOStreams] {category}/{field} needs sync: local={local_time}, remote={remote_time}',
                xbmc.LOGDEBUG
            )
        
        return needs_sync
    
    def get_local_activities(self):
        """Get local activities timestamps from database."""
        activities = self.fetchone("SELECT * FROM activities WHERE sync_id=1")
        
        if not activities:
            # Initialize activities table if empty
            self.execute_sql(
                "INSERT INTO activities (sync_id, trakt_username) VALUES (1, ?)",
                (trakt.get_trakt_username(),)
            )
            return {}
        
        return activities
    
    def _update_local_activities(self, remote_activities):
        """Update local activities table with remote timestamps.
        
        Args:
            remote_activities: Activities JSON from Trakt
        """
        # Extract timestamps from nested structure
        movies = remote_activities.get('movies', {})
        episodes = remote_activities.get('episodes', {})
        shows = remote_activities.get('shows', {})
        
        self.execute_sql("""
            UPDATE activities SET
                movies_watched_at = ?,
                movies_collected_at = ?,
                movies_watchlist_at = ?,
                episodes_watched_at = ?,
                episodes_collected_at = ?,
                shows_watchlist_at = ?,
                all_activities = ?
            WHERE sync_id = 1
        """, (
            movies.get('watched_at'),
            movies.get('collected_at'),
            movies.get('watchlisted_at'),
            episodes.get('watched_at'),
            episodes.get('collected_at'),
            shows.get('watchlisted_at'),
            str(remote_activities)  # Store full JSON for reference
        ))
        
        xbmc.log('[AIOStreams] Updated local activities timestamps', xbmc.LOGDEBUG)
    
    # ===== Sync Task Implementations =====
    
    def _sync_watched_movies(self):
        """Sync watched movies from Trakt."""
        xbmc.log('[AIOStreams] Syncing watched movies...', xbmc.LOGDEBUG)
        
        # Fetch from Trakt
        watched_movies = trakt.call_trakt('sync/history/movies', with_auth=True)
        
        if not watched_movies:
            return
        
        # Process each movie
        for item in watched_movies:
            movie = item.get('movie', {})
            trakt_id = movie.get('ids', {}).get('trakt')
            
            if not trakt_id:
                continue
            
            # Update or insert movie
            self.execute_sql("""
                INSERT OR REPLACE INTO movies (
                    trakt_id, imdb_id, tmdb_id, watched, last_watched_at, last_updated
                ) VALUES (?, ?, ?, 1, ?, datetime('now'))
            """, (
                trakt_id,
                movie.get('ids', {}).get('imdb'),
                movie.get('ids', {}).get('tmdb'),
                item.get('watched_at')
            ))
        
        xbmc.log(f'[AIOStreams] Synced {len(watched_movies)} watched movies', xbmc.LOGDEBUG)
    
    def _sync_collected_movies(self):
        """Sync collected movies from Trakt."""
        xbmc.log('[AIOStreams] Syncing collected movies...', xbmc.LOGDEBUG)
        
        collected_movies = trakt.call_trakt('sync/collection/movies', with_auth=True)
        
        if not collected_movies:
            return
        
        for item in collected_movies:
            movie = item.get('movie', {})
            trakt_id = movie.get('ids', {}).get('trakt')
            
            if not trakt_id:
                continue
            
            self.execute_sql("""
                INSERT OR REPLACE INTO movies (
                    trakt_id, imdb_id, tmdb_id, collected, collected_at, last_updated
                ) VALUES (?, ?, ?, 1, ?, datetime('now'))
            """, (
                trakt_id,
                movie.get('ids', {}).get('imdb'),
                movie.get('ids', {}).get('tmdb'),
                item.get('collected_at')
            ))
        
        xbmc.log(f'[AIOStreams] Synced {len(collected_movies)} collected movies', xbmc.LOGDEBUG)
    
    def _sync_movie_watchlist(self):
        """Sync movie watchlist from Trakt."""
        xbmc.log('[AIOStreams] Syncing movie watchlist...', xbmc.LOGDEBUG)
        
        # Clear existing watchlist entries for movies
        self.execute_sql("DELETE FROM watchlist WHERE mediatype='movie'")
        
        # Fetch fresh watchlist
        watchlist_movies = trakt.call_trakt('sync/watchlist/movies', with_auth=True)
        
        if not watchlist_movies:
            return
        
        for item in watchlist_movies:
            movie = item.get('movie', {})
            trakt_id = movie.get('ids', {}).get('trakt')
            
            if not trakt_id:
                continue
            
            self.execute_sql("""
                INSERT OR REPLACE INTO watchlist (trakt_id, mediatype, imdb_id, listed_at)
                VALUES (?, 'movie', ?, ?)
            """, (
                trakt_id,
                movie.get('ids', {}).get('imdb'),
                item.get('listed_at')
            ))
        
        xbmc.log(f'[AIOStreams] Synced {len(watchlist_movies)} watchlist movies', xbmc.LOGDEBUG)
    
    def _fetch_all_episodes_for_show(self, show_trakt_id):
        """Fetch all episodes for a show from Trakt API.

        Args:
            show_trakt_id: Trakt ID of the show

        Returns:
            list: List of all episodes with metadata
        """
        # Fetch all seasons with episodes and extended info (includes air dates)
        seasons = trakt.call_trakt(f'shows/{show_trakt_id}/seasons?extended=episodes', with_auth=False)

        if not seasons:
            return []

        all_episodes = []
        for season in seasons:
            season_num = season.get('number', 0)
            for episode in season.get('episodes', []):
                all_episodes.append({
                    'season': season_num,
                    'number': episode.get('number'),
                    'trakt_id': episode.get('ids', {}).get('trakt'),
                    'imdb_id': episode.get('ids', {}).get('imdb'),
                    'tmdb_id': episode.get('ids', {}).get('tmdb'),
                    'tvdb_id': episode.get('ids', {}).get('tvdb'),
                    'air_date': episode.get('first_aired'),
                })

        return all_episodes

    def _sync_watched_episodes(self):
        """Sync watched episodes from Trakt.

        Now also fetches ALL episodes for each show to enable Next Up calculation
        without API calls.
        """
        xbmc.log('[AIOStreams] Syncing watched episodes...', xbmc.LOGDEBUG)

        watched_shows = trakt.call_trakt('sync/watched/shows', with_auth=True)

        if not watched_shows:
            return

        episode_count = 0
        show_count = 0

        for item in watched_shows:
            show = item.get('show', {})
            show_trakt_id = show.get('ids', {}).get('trakt')

            # Insert/update show
            self.execute_sql("""
                INSERT OR IGNORE INTO shows (trakt_id, imdb_id, tmdb_id, tvdb_id, last_updated)
                VALUES (?, ?, ?, ?, datetime('now'))
            """, (
                show_trakt_id,
                show.get('ids', {}).get('imdb'),
                show.get('ids', {}).get('tmdb'),
                show.get('ids', {}).get('tvdb')
            ))

            # Fetch ALL episodes for this show (needed for Next Up calculation)
            xbmc.log(f'[AIOStreams] Fetching all episodes for show {show_trakt_id}', xbmc.LOGDEBUG)
            all_episodes = self._fetch_all_episodes_for_show(show_trakt_id)

            # Insert all episodes with watched=0 initially
            for ep in all_episodes:
                self.execute_sql("""
                    INSERT OR IGNORE INTO episodes (
                        show_trakt_id, season, episode, trakt_id, imdb_id, tmdb_id, tvdb_id,
                        air_date, watched, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now'))
                """, (
                    show_trakt_id,
                    ep['season'],
                    ep['number'],
                    ep['trakt_id'],
                    ep['imdb_id'],
                    ep['tmdb_id'],
                    ep['tvdb_id'],
                    ep['air_date']
                ))

            # Now mark watched episodes
            for season in item.get('seasons', []):
                season_num = season.get('number')

                for episode in season.get('episodes', []):
                    episode_num = episode.get('number')

                    # Update episode as watched
                    self.execute_sql("""
                        UPDATE episodes
                        SET watched=1, last_watched_at=?, last_updated=datetime('now')
                        WHERE show_trakt_id=? AND season=? AND episode=?
                    """, (
                        item.get('last_watched_at'),
                        show_trakt_id,
                        season_num,
                        episode_num
                    ))

                    episode_count += 1

            show_count += 1

        # Note: Auto-unhide logic removed from sync to preserve dropped shows
        # Shows are only auto-unhid when user actively marks episodes as watched

        # Update show statistics (watched/unwatched episode counts)
        self._update_all_show_statistics()

        xbmc.log(f'[AIOStreams] Synced {episode_count} watched episodes across {show_count} shows', xbmc.LOGINFO)
    
    def _sync_collected_episodes(self):
        """Sync collected episodes from Trakt."""
        xbmc.log('[AIOStreams] Syncing collected episodes...', xbmc.LOGDEBUG)
        
        collected_shows = trakt.call_trakt('sync/collection/shows', with_auth=True)
        
        if not collected_shows:
            return
        
        episode_count = 0
        
        for item in collected_shows:
            show = item.get('show', {})
            show_trakt_id = show.get('ids', {}).get('trakt')
            
            for season in item.get('seasons', []):
                season_num = season.get('number')
                
                for episode in season.get('episodes', []):
                    episode_num = episode.get('number')

                    self.execute_sql("""
                        INSERT OR REPLACE INTO episodes (
                            show_trakt_id, season, episode, collected,
                            collected_at, last_updated
                        ) VALUES (?, ?, ?, 1, ?, datetime('now'))
                    """, (
                        show_trakt_id,
                        season_num,
                        episode_num,
                        episode.get('collected_at')
                    ))
                    
                    episode_count += 1
        
        xbmc.log(f'[AIOStreams] Synced {episode_count} collected episodes', xbmc.LOGDEBUG)
    
    def _sync_show_watchlist(self):
        """Sync show watchlist from Trakt."""
        xbmc.log('[AIOStreams] Syncing show watchlist...', xbmc.LOGDEBUG)
        
        # Clear existing show watchlist
        self.execute_sql("DELETE FROM watchlist WHERE mediatype='show'")
        
        watchlist_shows = trakt.call_trakt('sync/watchlist/shows', with_auth=True)
        
        if not watchlist_shows:
            return
        
        for item in watchlist_shows:
            show = item.get('show', {})
            trakt_id = show.get('ids', {}).get('trakt')
            
            if not trakt_id:
                continue
            
            self.execute_sql("""
                INSERT OR REPLACE INTO watchlist (trakt_id, mediatype, imdb_id, listed_at)
                VALUES (?, 'show', ?, ?)
            """, (
                trakt_id,
                show.get('ids', {}).get('imdb'),
                item.get('listed_at')
            ))
        
        xbmc.log(f'[AIOStreams] Synced {len(watchlist_shows)} watchlist shows', xbmc.LOGDEBUG)
    
    def _sync_playback_progress(self):
        """Sync playback progress (bookmarks) from Trakt."""
        xbmc.log('[AIOStreams] Syncing playback progress...', xbmc.LOGDEBUG)
        
        # Clear existing bookmarks
        self.execute_sql("DELETE FROM bookmarks")
        
        playback_progress = trakt.call_trakt('sync/playback', with_auth=True)
        
        if not playback_progress:
            return
        
        for item in playback_progress:
            item_type = item.get('type')  # 'movie' or 'episode'
            trakt_id = item.get(item_type, {}).get('ids', {}).get('trakt')
            
            if not trakt_id:
                continue
            
            self.execute_sql("""
                INSERT OR REPLACE INTO bookmarks (trakt_id, resume_time, percent_played, type, paused_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                trakt_id,
                item.get('progress', 0) * item.get('duration', 0) / 100,  # Convert percent to seconds
                item.get('progress', 0),
                item_type,
                item.get('paused_at')
            ))
        
        xbmc.log(f'[AIOStreams] Synced {len(playback_progress)} bookmarks', xbmc.LOGDEBUG)
    
    def _sync_hidden_items(self):
        """Sync hidden items from Trakt."""
        xbmc.log('[AIOStreams] Syncing hidden items...', xbmc.LOGDEBUG)
        
        # Clear existing hidden items
        self.execute_sql("DELETE FROM hidden")
        
        # Sync each hidden section
        sections = ['calendar', 'progress_watched', 'progress_collected', 'recommendations']
        
        for section in sections:
            try:
                hidden_items = trakt.call_trakt(f'users/hidden/{section}', with_auth=True)
                
                if not hidden_items:
                    continue
                
                for item in hidden_items:
                    # Determine media type
                    if 'movie' in item:
                        trakt_id = item['movie']['ids']['trakt']
                        media_type = 'movie'
                    elif 'show' in item:
                        trakt_id = item['show']['ids']['trakt']
                        media_type = 'show'
                    else:
                        continue
                    
                    self.execute_sql("""
                        INSERT OR IGNORE INTO hidden (trakt_id, mediatype, section)
                        VALUES (?, ?, ?)
                    """, (trakt_id, media_type, section))
                
                xbmc.log(f'[AIOStreams] Synced {len(hidden_items)} hidden items for {section}', xbmc.LOGDEBUG)
            
            except Exception as e:
                xbmc.log(f'[AIOStreams] Failed to sync hidden/{section}: {e}', xbmc.LOGERROR)
    
    def _update_all_show_statistics(self):
        """Recalculate watched/unwatched episode counts for all shows."""
        xbmc.log('[AIOStreams] Updating show statistics...', xbmc.LOGDEBUG)

        # Get all shows
        shows = self.fetchall("SELECT DISTINCT show_trakt_id FROM episodes")

        for show in shows:
            show_id = show['show_trakt_id']

            # Count watched episodes
            watched_count = self.fetchone(
                "SELECT COUNT(*) as count FROM episodes WHERE show_trakt_id=? AND watched=1",
                (show_id,)
            )['count']

            # Count total episodes
            total_count = self.fetchone(
                "SELECT COUNT(*) as count FROM episodes WHERE show_trakt_id=?",
                (show_id,)
            )['count']
            
            unwatched_count = total_count - watched_count
            
            # Update show table
            self.execute_sql("""
                UPDATE shows 
                SET watched_episodes=?, unwatched_episodes=?, episode_count=?
                WHERE trakt_id=?
            """, (watched_count, unwatched_count, total_count, show_id))
    
    def _finalize_sync(self, silent):
        """Finalize sync and trigger widget refresh."""
        if not silent:
            if self.sync_errors:
                xbmcgui.Dialog().notification(
                    'AIOStreams',
                    f'Sync completed with {len(self.sync_errors)} errors',
                    xbmcgui.NOTIFICATION_WARNING
                )
            else:
                xbmcgui.Dialog().notification(
                    'AIOStreams',
                    'Trakt sync completed successfully',
                    xbmcgui.NOTIFICATION_INFO
                )
        
        # Trigger widget refresh
        xbmc.executebuiltin('UpdateLibrary(video)')
        
        xbmc.log('[AIOStreams] Sync finalized', xbmc.LOGDEBUG)
