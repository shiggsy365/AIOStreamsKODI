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
                    xbmc.log('[AIOStreams] Activities called too recently, skipping sync', xbmc.LOGDEBUG)
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
                    
                # Check if search is active (Global or Internal)
                win_home = xbmcgui.Window(10000)
                if win_home.getProperty('AIOStreams.SearchActive') == 'true' or \
                   win_home.getProperty('AIOStreams.InternalSearchActive') == 'true':
                    xbmc.log('[AIOStreams] Sync interrupted by active search', xbmc.LOGDEBUG)
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
        local_time = local_activities.get(f'{category}_{field}') or '1970-01-01T00:00:00'
        remote_time = remote_activities.get(category, {}).get(field) or '1970-01-01T00:00:00'
        
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
                "INSERT OR IGNORE INTO activities (sync_id, trakt_username) VALUES (1, ?)",
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
        
        # Fetch from Trakt with full metadata for ratings
        watched_movies = trakt.call_trakt('sync/history/movies', params={'extended': 'full'}, with_auth=True)
        
        if not watched_movies:
            return
        
        # Prepare batch data
        batch_data = []
        for item in watched_movies:
            movie = item.get('movie', {})
            trakt_id = movie.get('ids', {}).get('trakt')
            
            if not trakt_id:
                continue
            
            import pickle
            batch_data.append((
                trakt_id,
                movie.get('ids', {}).get('imdb'),
                movie.get('ids', {}).get('tmdb'),
                pickle.dumps(movie),
                item.get('watched_at')
            ))
            
        # Execute batch update
        if batch_data:
            self.execute_sql_batch("""
                INSERT OR REPLACE INTO movies (
                    trakt_id, imdb_id, tmdb_id, metadata, watched, last_watched_at, last_updated
                ) VALUES (?, ?, ?, ?, 1, ?, datetime('now'))
            """, batch_data)
        
        xbmc.log(f'[AIOStreams] Synced {len(watched_movies)} watched movies', xbmc.LOGDEBUG)
    
    def _sync_collected_movies(self):
        """Sync collected movies from Trakt."""
        xbmc.log('[AIOStreams] Syncing collected movies...', xbmc.LOGDEBUG)
        
        collected_movies = trakt.call_trakt('sync/collection/movies', params={'extended': 'full'}, with_auth=True)
        
        if not collected_movies:
            return
        
        # Prepare batch data
        batch_data = []
        for item in collected_movies:
            movie = item.get('movie', {})
            trakt_id = movie.get('ids', {}).get('trakt')
            
            if not trakt_id:
                continue
            
            import pickle
            batch_data.append((
                trakt_id,
                movie.get('ids', {}).get('imdb'),
                movie.get('ids', {}).get('tmdb'),
                pickle.dumps(movie),
                item.get('collected_at')
            ))
            
        # Execute batch update
        if batch_data:
            self.execute_sql_batch("""
                INSERT OR REPLACE INTO movies (
                    trakt_id, imdb_id, tmdb_id, metadata, collected, collected_at, last_updated
                ) VALUES (?, ?, ?, ?, 1, ?, datetime('now'))
            """, batch_data)
        
        xbmc.log(f'[AIOStreams] Synced {len(collected_movies)} collected movies', xbmc.LOGDEBUG)
    
    def _sync_movie_watchlist(self):
        """Sync movie watchlist from Trakt."""
        xbmc.log('[AIOStreams] Syncing movie watchlist...', xbmc.LOGDEBUG)
        
        # Clear existing watchlist entries for movies
        self.execute_sql("DELETE FROM watchlist WHERE mediatype='movie'")
        
        # Fetch fresh watchlist with full metadata for ratings
        watchlist_movies = trakt.call_trakt('sync/watchlist/movies', params={'extended': 'full'}, with_auth=True)
        
        if not watchlist_movies:
            return
        
        # Prepare batch data
        batch_data = []
        for item in watchlist_movies:
            movie = item.get('movie', {})
            trakt_id = movie.get('ids', {}).get('trakt')
            
            if not trakt_id:
                continue
            
            import pickle
            batch_data.append((
                trakt_id,
                movie.get('ids', {}).get('imdb'),
                item.get('listed_at'),
                pickle.dumps(movie)
            ))
            
        # Execute batch update
        if batch_data:
            self.execute_sql_batch("""
                INSERT OR REPLACE INTO watchlist (trakt_id, mediatype, imdb_id, listed_at, metadata)
                VALUES (?, 'movie', ?, ?, ?)
            """, batch_data)
        
        xbmc.log(f'[AIOStreams] Synced {len(watchlist_movies)} watchlist movies', xbmc.LOGDEBUG)
    
    def _fetch_all_episodes_for_show(self, show_trakt_id):
        """Fetch all episodes for a show from Trakt API.

        Args:
            show_trakt_id: Trakt ID of the show

        Returns:
            list: List of all episodes with metadata
        """
        # Fetch all seasons with episodes and extended info (includes air dates, titles, overviews)
        seasons = trakt.call_trakt(f'shows/{show_trakt_id}/seasons?extended=episodes,full', with_auth=False)

        if not seasons:
            return []

        all_episodes = []
        for season in seasons:
            season_num = season.get('number', 0)
            for episode in season.get('episodes', []):
                # Build episode metadata dict for storage
                episode_meta = {
                    'title': episode.get('title', ''),
                    'overview': episode.get('overview', ''),
                    'rating': episode.get('rating'),
                    'votes': episode.get('votes'),
                    'runtime': episode.get('runtime'),
                    'ids': episode.get('ids', {}),
                }

                all_episodes.append({
                    'season': season_num,
                    'number': episode.get('number'),
                    'trakt_id': episode.get('ids', {}).get('trakt'),
                    'imdb_id': episode.get('ids', {}).get('imdb'),
                    'tmdb_id': episode.get('ids', {}).get('tmdb'),
                    'tvdb_id': episode.get('ids', {}).get('tvdb'),
                    'air_date': episode.get('first_aired'),
                    'metadata': episode_meta,
                })
        
        # Debug: log first episode to verify ID structure
        if all_episodes:
            sample = all_episodes[0]
            xbmc.log(f'[AIOStreams] Sample episode from API for show {show_trakt_id}: S{sample["season"]:02d}E{sample["number"]:02d}, trakt_id={sample["trakt_id"]}, ALL ids={sample["metadata"]["ids"]}', xbmc.LOGDEBUG)

        return all_episodes

    def _sync_watched_episodes(self):
        """Sync watched episodes from Trakt.

        Now also fetches ALL episodes for each show to enable Next Up calculation
        without API calls.
        """
        xbmc.log('[AIOStreams] Syncing watched episodes...', xbmc.LOGDEBUG)

        watched_shows = trakt.call_trakt('sync/watched/shows', params={'extended': 'full'}, with_auth=True)

        if not watched_shows:
            return

        episode_count = 0
        show_count = 0

        # 1. Batch insert/update shows
        batch_shows = []
        for item in watched_shows:
            show = item.get('show', {})
            show_trakt_id = show.get('ids', {}).get('trakt')
            
            batch_shows.append((
                show_trakt_id,
                show.get('ids', {}).get('imdb'),
                show.get('ids', {}).get('tmdb'),
                show.get('ids', {}).get('tvdb'),
                show.get('ids', {}).get('slug'),
                show.get('title', 'Unknown'),
                pickle.dumps(show)
            ))
        
        if batch_shows:
            self.execute_sql_batch("""
                INSERT OR IGNORE INTO shows (trakt_id, imdb_id, tmdb_id, tvdb_id, slug, title, metadata, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, batch_shows)
            
        import pickle

        # 2. Process episodes for each show
        for item in watched_shows:
            # Deep interruption check (Global or Internal)
            win_home = xbmcgui.Window(10000)
            if win_home.getProperty('AIOStreams.SearchActive') == 'true' or \
               win_home.getProperty('AIOStreams.InternalSearchActive') == 'true':
                xbmc.log('[AIOStreams] Sync (_sync_watched_episodes) interrupted by active search', xbmc.LOGDEBUG)
                return

            show = item.get('show', {})
            show_trakt_id = show.get('ids', {}).get('trakt')

            # Fetch ALL episodes for this show (needed for Next Up calculation)
            xbmc.log(f'[AIOStreams] Fetching all episodes for show {show_trakt_id}', xbmc.LOGDEBUG)
            all_episodes = self._fetch_all_episodes_for_show(show_trakt_id)

            # 2a. Batch insert all episodes
            batch_episodes = []
            for ep in all_episodes:
                pickled_metadata = pickle.dumps(ep.get('metadata', {}))
                
                batch_episodes.append((
                    show_trakt_id,
                    ep['season'],
                    ep['number'],
                    ep['trakt_id'],
                    ep['imdb_id'],
                    ep['tmdb_id'],
                    ep['tvdb_id'],
                    ep['air_date'],
                    pickled_metadata
                ))
            
            if batch_episodes:
                self.execute_sql_batch("""
                    INSERT OR IGNORE INTO episodes (
                        show_trakt_id, season, episode, trakt_id, imdb_id, tmdb_id, tvdb_id,
                        air_date, metadata, watched, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, datetime('now'))
                """, batch_episodes)

            # 2b. Batch update watched episodes
            batch_watched = []
            for season in item.get('seasons', []):
                season_num = season.get('number')

                for episode in season.get('episodes', []):
                    episode_num = episode.get('number')
                    
                    batch_watched.append((
                        item.get('last_watched_at'),
                        show_trakt_id,
                        season_num,
                        episode_num
                    ))
                    episode_count += 1
            
            if batch_watched:
                self.execute_sql_batch("""
                    UPDATE episodes
                    SET watched=1, last_watched_at=?, last_updated=datetime('now')
                    WHERE show_trakt_id=? AND season=? AND episode=?
                """, batch_watched)

            show_count += 1

        # Note: Auto-unhide logic removed from sync to preserve dropped shows
        # Shows are only auto-unhid when user actively marks episodes as watched

        # Update show statistics (watched/unwatched episode counts)
        self._update_all_show_statistics()

        xbmc.log(f'[AIOStreams] Synced {episode_count} watched episodes across {show_count} shows', xbmc.LOGDEBUG)
    
    def _sync_collected_episodes(self):
        """Sync collected episodes from Trakt."""
        xbmc.log('[AIOStreams] Syncing collected episodes...', xbmc.LOGDEBUG)
        
        collected_shows = trakt.call_trakt('sync/collection/shows', with_auth=True)
        
        if not collected_shows:
            return
        
        batch_data = []
        episode_count = 0
        
        for item in collected_shows:
            show = item.get('show', {})
            show_trakt_id = show.get('ids', {}).get('trakt')
            
            for season in item.get('seasons', []):
                season_num = season.get('number')
                
                for episode in season.get('episodes', []):
                    episode_num = episode.get('number')
                    
                    batch_data.append((
                        show_trakt_id,
                        season_num,
                        episode_num,
                        episode.get('collected_at')
                    ))
                    episode_count += 1
        
        if batch_data:
            self.execute_sql_batch("""
                INSERT OR REPLACE INTO episodes (
                    show_trakt_id, season, episode, collected,
                    collected_at, last_updated
                ) VALUES (?, ?, ?, 1, ?, datetime('now'))
            """, batch_data)
        
        xbmc.log(f'[AIOStreams] Synced {episode_count} collected episodes', xbmc.LOGDEBUG)
    
    def _sync_show_watchlist(self):
        """Sync show watchlist from Trakt."""
        xbmc.log('[AIOStreams] Syncing show watchlist...', xbmc.LOGDEBUG)
        
        # Clear existing show watchlist
        self.execute_sql("DELETE FROM watchlist WHERE mediatype='show'")
        
        watchlist_shows = trakt.call_trakt('sync/watchlist/shows', params={'extended': 'full'}, with_auth=True)
        
        if not watchlist_shows:
            return
        
        batch_data = []
        for item in watchlist_shows:
            show = item.get('show', {})
            trakt_id = show.get('ids', {}).get('trakt')
            
            if not trakt_id:
                continue
            
            import pickle
            batch_data.append((
                trakt_id,
                show.get('ids', {}).get('imdb'),
                item.get('listed_at'),
                pickle.dumps(show)
            ))
            
        if batch_data:
            self.execute_sql_batch("""
                INSERT OR REPLACE INTO watchlist (trakt_id, mediatype, imdb_id, listed_at, metadata)
                VALUES (?, 'show', ?, ?, ?)
            """, batch_data)
        
        xbmc.log(f'[AIOStreams] Synced {len(watchlist_shows)} watchlist shows', xbmc.LOGDEBUG)
    
    def _sync_playback_progress(self):
        """Sync playback progress (bookmarks) from Trakt."""
        xbmc.log('[AIOStreams] Syncing playback progress...', xbmc.LOGDEBUG)
        
        # Clear existing bookmarks
        self.execute_sql("DELETE FROM bookmarks")
        
        playback_progress = trakt.call_trakt('sync/playback', with_auth=True)
        
        if not playback_progress:
            xbmc.log('[AIOStreams] No playback progress found on Trakt', xbmc.LOGDEBUG)
            return
        

        batch_data = []
        for item in playback_progress:
            item_type = item.get('type')  # 'movie' or 'episode'
            trakt_id = item.get(item_type, {}).get('ids', {}).get('trakt')
            progress = item.get('progress', 0)
            
            # Debug: log all items to verify correct ID extraction
            if item_type == 'episode':
                episode_ids = item.get('episode', {}).get('ids', {})
                xbmc.log(f'[AIOStreams] Bookmark episode #{len(batch_data)+1}: ALL IDs={episode_ids}, using trakt_id={trakt_id}, progress={progress}%', xbmc.LOGDEBUG)
            else:
                xbmc.log(f'[AIOStreams] Bookmark item #{len(batch_data)+1}: type={item_type}, trakt_id={trakt_id}, progress={progress}%', xbmc.LOGDEBUG)
            
            if not trakt_id or progress <= 0:
                continue
            
            # Calculate resume time: progress is percentage, duration is runtime in minutes
            # We need resume_time in seconds
            duration_minutes = item.get(item_type, {}).get('runtime', item.get('duration', 0))
            resume_time = (progress / 100.0) * (duration_minutes * 60) if duration_minutes > 0 else 0
            
            batch_data.append((
                trakt_id,
                item.get(item_type, {}).get('ids', {}).get('tvdb'),
                item.get(item_type, {}).get('ids', {}).get('tmdb'),
                item.get(item_type, {}).get('ids', {}).get('imdb'),
                resume_time,
                progress,
                item_type,
                item.get('paused_at')
            ))
            
        if batch_data:
            self.execute_sql_batch("""
                INSERT OR REPLACE INTO bookmarks (trakt_id, tvdb_id, tmdb_id, imdb_id, resume_time, percent_played, type, paused_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, batch_data)
        
        
        xbmc.log(f'[AIOStreams] Synced {len(batch_data)} bookmarks from {len(playback_progress)} items', xbmc.LOGDEBUG)
        
        # Verify bookmarks were actually written
        verify_count = self.fetchone("SELECT COUNT(*) as count FROM bookmarks")
        xbmc.log(f'[AIOStreams] Verification: bookmarks table now has {verify_count["count"] if verify_count else 0} rows', xbmc.LOGDEBUG)
        
        # Show sample bookmark IDs for debugging
        sample_bookmarks = self.fetch_all("SELECT trakt_id, percent_played, type FROM bookmarks LIMIT 5")
        if sample_bookmarks:
            bookmark_ids = [row['trakt_id'] for row in sample_bookmarks]
            xbmc.log(f'[AIOStreams] Sample bookmark trakt_ids: {bookmark_ids}', xbmc.LOGDEBUG)
    
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
                
                batch_data = []
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
                    
                    batch_data.append((trakt_id, media_type, section))
                
                if batch_data:
                    self.execute_sql_batch("""
                        INSERT OR IGNORE INTO hidden (trakt_id, mediatype, section)
                        VALUES (?, ?, ?)
                    """, batch_data)
                
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

            # Fetch watched and total episode counts for this show (excluding specials)
            watched_count = self.fetchone(
                "SELECT COUNT(*) as count FROM episodes WHERE show_trakt_id=? AND season > 0 AND watched=1",
                (show_id,)
            )['count']
            total_count = self.fetchone(
                "SELECT COUNT(*) as count FROM episodes WHERE show_trakt_id=? AND season > 0",
                (show_id,)
            )['count']
            
            # Get show metadata to determine official episode count
            # This is critical because our episodes table might only contain watched episodes
            official_count = total_count
            try:
                sql_meta = "SELECT metadata FROM shows WHERE trakt_id=?"
                row_meta = self.fetchone(sql_meta, (show_id,))
                if row_meta and row_meta['metadata']:
                    import pickle
                    meta = pickle.loads(row_meta['metadata'])
                    # Try multiple fields that might contain total episode count
                    # aired_episodes is the canonical count from Trakt
                    if 'aired_episodes' in meta and meta['aired_episodes'] > 0:
                        official_count = meta['aired_episodes']
                    elif 'episode_count' in meta and meta['episode_count'] > 0:
                        official_count = meta['episode_count']
                    # If we have more episodes in DB than metadata says, trust the DB
                    if total_count > official_count:
                        official_count = total_count
            except Exception as e:
                xbmc.log(f'[AIOStreams] Could not get official count for show {show_id}: {e}', xbmc.LOGDEBUG)

            unwatched_count = max(0, official_count - watched_count)
            
            self.execute_sql("""
                UPDATE shows 
                SET watched_episodes=?, unwatched_episodes=?, episode_count=?
                WHERE trakt_id=?
            """, (watched_count, unwatched_count, official_count, show_id))
    
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
