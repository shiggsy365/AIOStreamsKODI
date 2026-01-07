# -*- coding: utf-8 -*-
"""
Stream prefetch module for AIOStreams.
Pre-resolves streams for Next Up episodes to reduce playback start time.
"""
import xbmc
import threading
import time


class StreamPrefetchManager:
    """Manages prefetching of streams for Next Up episodes."""

    def __init__(self):
        """Initialize stream prefetch manager."""
        self.prefetch_cache = {}  # {episode_key: {'streams': [], 'timestamp': float, 'best_stream': dict}}
        self.cache_ttl = 900  # 15 minutes (900 seconds)
        self.lock = threading.Lock()
        self.prefetch_in_progress = False

    def get_episode_key(self, show_imdb, season, episode):
        """Generate cache key for an episode.

        Args:
            show_imdb: IMDB ID of the show
            season: Season number
            episode: Episode number

        Returns:
            str: Cache key
        """
        return f"{show_imdb}:{season}:{episode}"

    def is_cache_valid(self, episode_key):
        """Check if cached streams are still valid.

        Args:
            episode_key: Episode cache key

        Returns:
            bool: True if cache is valid, False otherwise
        """
        if episode_key not in self.prefetch_cache:
            return False

        cache_entry = self.prefetch_cache[episode_key]
        cache_age = time.time() - cache_entry.get('timestamp', 0)

        return cache_age < self.cache_ttl

    def get_cached_streams(self, show_imdb, season, episode):
        """Get cached streams for an episode.

        Args:
            show_imdb: IMDB ID of the show
            season: Season number
            episode: Episode number

        Returns:
            dict: {'streams': list, 'best_stream': dict} or None if not cached
        """
        episode_key = self.get_episode_key(show_imdb, season, episode)

        with self.lock:
            if self.is_cache_valid(episode_key):
                cache_entry = self.prefetch_cache[episode_key]
                xbmc.log(f'[AIOStreams] Prefetch cache hit for {episode_key}', xbmc.LOGINFO)
                return {
                    'streams': cache_entry.get('streams', []),
                    'best_stream': cache_entry.get('best_stream')
                }

        return None

    def prefetch_streams_async(self, episodes, get_streams_func):
        """Prefetch streams for top episodes in background.

        Args:
            episodes: List of episode dicts (from get_next_up_episodes)
            get_streams_func: Function to fetch streams - func(show_imdb, season, episode) -> list
        """
        if self.prefetch_in_progress:
            xbmc.log('[AIOStreams] Prefetch already in progress, skipping', xbmc.LOGDEBUG)
            return

        # Only prefetch top 3 episodes
        top_episodes = episodes[:3]

        if not top_episodes:
            return

        xbmc.log(f'[AIOStreams] Starting async prefetch for {len(top_episodes)} episodes', xbmc.LOGINFO)

        # Start background thread
        thread = threading.Thread(target=self._prefetch_worker, args=(top_episodes, get_streams_func))
        thread.daemon = True
        thread.start()

    def _prefetch_worker(self, episodes, get_streams_func):
        """Background worker to prefetch streams.

        Args:
            episodes: List of episode dicts
            get_streams_func: Function to fetch streams
        """
        self.prefetch_in_progress = True

        try:
            for ep in episodes:
                show_imdb = ep.get('show_imdb_id', '')
                season = ep.get('season', 0)
                episode = ep.get('episode', 0)

                if not show_imdb:
                    continue

                episode_key = self.get_episode_key(show_imdb, season, episode)

                # Skip if already cached and valid
                if self.is_cache_valid(episode_key):
                    xbmc.log(f'[AIOStreams] Skipping prefetch for {episode_key} (already cached)', xbmc.LOGDEBUG)
                    continue

                xbmc.log(f'[AIOStreams] Prefetching streams for {episode_key}', xbmc.LOGINFO)

                try:
                    # Fetch streams
                    stream_data = get_streams_func(show_imdb, season, episode)

                    # Extract streams list from response
                    streams = stream_data.get('streams', []) if isinstance(stream_data, dict) else stream_data

                    if streams:
                        # Get best stream using quality short-circuit
                        best_stream = None
                        try:
                            from resources.lib.streams import get_stream_manager
                            manager = get_stream_manager()
                            best_stream = manager.get_best_stream_fast(streams)
                        except Exception as e:
                            xbmc.log(f'[AIOStreams] Error getting best stream: {e}', xbmc.LOGERROR)

                        # Cache the results
                        with self.lock:
                            self.prefetch_cache[episode_key] = {
                                'streams': streams,
                                'best_stream': best_stream,
                                'timestamp': time.time()
                            }

                        xbmc.log(f'[AIOStreams] Prefetched {len(streams)} streams for {episode_key}', xbmc.LOGINFO)
                    else:
                        xbmc.log(f'[AIOStreams] No streams found for {episode_key}', xbmc.LOGWARNING)

                except Exception as e:
                    xbmc.log(f'[AIOStreams] Error prefetching streams for {episode_key}: {e}', xbmc.LOGERROR)

                # Small delay between requests to be nice to the API
                time.sleep(0.5)

        finally:
            self.prefetch_in_progress = False
            xbmc.log('[AIOStreams] Prefetch worker completed', xbmc.LOGINFO)

    def clear_cache(self):
        """Clear all prefetched streams."""
        with self.lock:
            self.prefetch_cache.clear()
        xbmc.log('[AIOStreams] Prefetch cache cleared', xbmc.LOGINFO)

    def cleanup_expired(self):
        """Remove expired entries from cache."""
        current_time = time.time()

        with self.lock:
            expired_keys = [
                key for key, entry in self.prefetch_cache.items()
                if current_time - entry.get('timestamp', 0) >= self.cache_ttl
            ]

            for key in expired_keys:
                del self.prefetch_cache[key]

            if expired_keys:
                xbmc.log(f'[AIOStreams] Cleaned up {len(expired_keys)} expired prefetch entries', xbmc.LOGDEBUG)


# Global instance
_prefetch_manager = None


def get_prefetch_manager():
    """Get global StreamPrefetchManager instance."""
    global _prefetch_manager
    if _prefetch_manager is None:
        _prefetch_manager = StreamPrefetchManager()
    return _prefetch_manager
