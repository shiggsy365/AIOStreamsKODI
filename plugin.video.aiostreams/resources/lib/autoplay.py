# -*- coding: utf-8 -*-
"""
Autoplay next episode functionality.

Monitors playback and triggers autoplay dialog near end of episode.
"""
import xbmc
import xbmcaddon
import xbmcgui
import threading
import time

ADDON = xbmcaddon.Addon()


class AutoplayManager:
    """
    Manages autoplay next episode functionality.

    Monitors playback time, scrapes next episode streams in background,
    and shows autoplay dialog when approaching end of current episode.
    """

    def __init__(self, player):
        """
        Initialize autoplay manager.

        Args:
            player: AIOStreamsPlayer instance
        """
        self.player = player
        self.monitor_thread = None
        self.stop_monitoring = threading.Event()
        self.streams_ready = False
        self.next_episode_streams = None
        self.next_episode_meta = None
        self.dialog_shown = False

    def is_enabled(self):
        """Check if autoplay is enabled in settings."""
        return ADDON.getSetting('autoplay_next_episode') == 'true'

    def get_timing_config(self, duration_minutes):
        """
        Get the configured timing for autoplay based on episode duration.

        Args:
            duration_minutes: Episode duration in minutes

        Returns:
            int: Number of seconds before end to show autoplay dialog
        """
        # Default values if settings aren't set
        defaults = {
            'under_15': 20,
            'under_30': 30,
            'under_45': 45,
            'over_45': 60
        }

        try:
            if duration_minutes < 15:
                return int(ADDON.getSetting('autoplay_under_15') or defaults['under_15'])
            elif duration_minutes < 30:
                return int(ADDON.getSetting('autoplay_under_30') or defaults['under_30'])
            elif duration_minutes < 45:
                return int(ADDON.getSetting('autoplay_under_45') or defaults['under_45'])
            else:
                return int(ADDON.getSetting('autoplay_over_45') or defaults['over_45'])
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error getting autoplay timing: {e}', xbmc.LOGERROR)
            return 30  # Safe default

    def get_next_episode(self, imdb_id, season, episode):
        """
        Determine the next episode to play.

        Simple logic: increment episode by 1. If we need to go to next season,
        we'll try and see if it exists when fetching metadata.

        Args:
            imdb_id: IMDb ID of the show
            season: Current season number
            episode: Current episode number

        Returns:
            tuple: (season, episode) for next episode, or (None, None) if can't determine
        """
        try:
            # Simple logic: try next episode in same season first
            next_season = season
            next_episode = episode + 1

            xbmc.log(f'[AIOStreams] Next episode determined: S{next_season:02d}E{next_episode:02d}', xbmc.LOGINFO)
            return next_season, next_episode

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error determining next episode: {e}', xbmc.LOGERROR)
            return None, None

    def fetch_streams_background(self, imdb_id, season, episode):
        """
        Fetch streams for next episode in background thread.

        Args:
            imdb_id: IMDb ID of the show
            season: Season number
            episode: Episode number
        """
        def fetch():
            try:
                xbmc.log(f'[AIOStreams] Background fetch started for S{season:02d}E{episode:02d}', xbmc.LOGINFO)

                # Import here to avoid circular imports
                import sys
                import os
                addon_path = xbmcaddon.Addon().getAddonInfo('path')
                sys.path.insert(0, addon_path)

                # Import addon functions (we need to do this dynamically)
                from addon import get_streams, get_meta

                # Fetch metadata first to get episode title and thumbnail
                media_id = f"{imdb_id}:{season}:{episode}"
                xbmc.log(f'[AIOStreams] Fetching metadata for {media_id}', xbmc.LOGDEBUG)
                self.next_episode_meta = get_meta('series', media_id)

                # Fetch streams
                xbmc.log(f'[AIOStreams] Fetching streams for {media_id}', xbmc.LOGDEBUG)
                result = get_streams('series', media_id)

                if result and result.get('streams'):
                    self.next_episode_streams = result.get('streams')
                    self.streams_ready = True
                    xbmc.log(f'[AIOStreams] Successfully fetched {len(self.next_episode_streams)} streams', xbmc.LOGINFO)
                else:
                    xbmc.log('[AIOStreams] No streams found for next episode', xbmc.LOGWARNING)
                    self.streams_ready = False

            except Exception as e:
                xbmc.log(f'[AIOStreams] Error fetching streams in background: {e}', xbmc.LOGERROR)
                import traceback
                xbmc.log(f'[AIOStreams] Traceback: {traceback.format_exc()}', xbmc.LOGERROR)
                self.streams_ready = False

        # Start background thread
        fetch_thread = threading.Thread(target=fetch)
        fetch_thread.daemon = True
        fetch_thread.start()

    def show_autoplay_dialog(self, next_season, next_episode):
        """
        Show autoplay dialog with countdown.

        Args:
            next_season: Next episode season
            next_episode: Next episode episode number

        Returns:
            bool: True if should autoplay, False if cancelled
        """
        try:
            from resources.lib.gui.windows import show_autoplay_dialog

            # Build episode title
            episode_title = f'S{next_season:02d}E{next_episode:02d}'

            # Try to get better title from metadata
            if self.next_episode_meta:
                meta = self.next_episode_meta.get('meta', {})
                ep_title = meta.get('name', meta.get('title', ''))
                if ep_title:
                    episode_title = f'S{next_season:02d}E{next_episode:02d} - {ep_title}'

            # Get episode thumbnail
            episode_thumb = ''
            if self.next_episode_meta:
                meta = self.next_episode_meta.get('meta', {})
                # Try various thumbnail fields
                episode_thumb = (meta.get('thumb') or
                               meta.get('poster') or
                               meta.get('background') or '')

            xbmc.log(f'[AIOStreams] Showing autoplay dialog for {episode_title}', xbmc.LOGINFO)

            # Show dialog (this blocks until user responds or timeout)
            should_play = show_autoplay_dialog(
                episode_title=episode_title,
                episode_thumb=episode_thumb,
                countdown_seconds=10
            )

            self.dialog_shown = True
            return should_play

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error showing autoplay dialog: {e}', xbmc.LOGERROR)
            import traceback
            xbmc.log(f'[AIOStreams] Traceback: {traceback.format_exc()}', xbmc.LOGERROR)
            return False

    def play_next_episode(self, imdb_id, next_season, next_episode):
        """
        Play the next episode.

        Args:
            imdb_id: IMDb ID of the show
            next_season: Season number
            next_episode: Episode number
        """
        try:
            xbmc.log(f'[AIOStreams] Playing next episode S{next_season:02d}E{next_episode:02d}', xbmc.LOGINFO)

            # Import addon functions
            import sys
            addon_path = xbmcaddon.Addon().getAddonInfo('path')
            sys.path.insert(0, addon_path)
            from addon import play_stream_by_index

            # Build media_id
            media_id = f"{imdb_id}:{next_season}:{next_episode}"

            # Use the fetched streams if available
            if self.streams_ready and self.next_episode_streams:
                # Play first stream (index 0)
                play_stream_by_index(
                    0,
                    self.next_episode_streams,
                    'series',
                    media_id,
                    self.next_episode_meta
                )
            else:
                # Fallback: trigger play action which will fetch streams
                xbmc.log('[AIOStreams] Streams not ready, triggering play action', xbmc.LOGWARNING)
                xbmc.executebuiltin(
                    f'RunPlugin(plugin://plugin.video.aiostreams/'
                    f'?action=play&content_type=series&imdb_id={imdb_id}'
                    f'&season={next_season}&episode={next_episode})'
                )

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error playing next episode: {e}', xbmc.LOGERROR)
            import traceback
            xbmc.log(f'[AIOStreams] Traceback: {traceback.format_exc()}', xbmc.LOGERROR)

    def monitor_playback(self, imdb_id, season, episode):
        """
        Monitor playback and trigger autoplay at appropriate time.

        Args:
            imdb_id: IMDb ID of the show
            season: Current season
            episode: Current episode
        """
        xbmc.log(f'[AIOStreams] Starting autoplay monitoring for S{season:02d}E{episode:02d}', xbmc.LOGINFO)

        try:
            # Wait a bit for playback to stabilize
            time.sleep(5)

            # Get total duration
            if not self.player.isPlaying():
                xbmc.log('[AIOStreams] Playback stopped, ending autoplay monitoring', xbmc.LOGINFO)
                return

            try:
                total_time = self.player.getTotalTime()
            except:
                xbmc.log('[AIOStreams] Could not get total time, ending autoplay monitoring', xbmc.LOGWARNING)
                return

            if total_time <= 0:
                xbmc.log('[AIOStreams] Invalid total time, ending autoplay monitoring', xbmc.LOGWARNING)
                return

            duration_minutes = total_time / 60.0

            # Get timing configuration
            dialog_time = self.get_timing_config(duration_minutes)
            scrape_time = dialog_time + 10  # Start scraping 10 seconds before dialog

            # Calculate when to trigger (in seconds from start)
            trigger_scrape_at = total_time - scrape_time
            trigger_dialog_at = total_time - dialog_time

            xbmc.log(f'[AIOStreams] Autoplay timing: total={total_time:.0f}s, '
                    f'scrape_at={trigger_scrape_at:.0f}s, dialog_at={trigger_dialog_at:.0f}s',
                    xbmc.LOGINFO)

            # Get next episode info
            next_season, next_episode = self.get_next_episode(imdb_id, season, episode)
            if not next_season or not next_episode:
                xbmc.log('[AIOStreams] Could not determine next episode', xbmc.LOGWARNING)
                return

            scrape_triggered = False
            dialog_triggered = False

            # Monitor playback time
            while not self.stop_monitoring.is_set():
                if not self.player.isPlaying():
                    xbmc.log('[AIOStreams] Playback stopped, ending autoplay monitoring', xbmc.LOGINFO)
                    return

                try:
                    current_time = self.player.getTime()
                except:
                    # Player might not be ready yet
                    time.sleep(1)
                    continue

                # Check if we should start scraping
                if not scrape_triggered and current_time >= trigger_scrape_at:
                    xbmc.log('[AIOStreams] Triggering stream scraping', xbmc.LOGINFO)
                    self.fetch_streams_background(imdb_id, next_season, next_episode)
                    scrape_triggered = True

                # Check if we should show dialog
                if not dialog_triggered and current_time >= trigger_dialog_at:
                    xbmc.log('[AIOStreams] Triggering autoplay dialog', xbmc.LOGINFO)
                    dialog_triggered = True

                    # Show dialog (blocks until user responds or timeout)
                    should_play = self.show_autoplay_dialog(next_season, next_episode)

                    if should_play:
                        # Stop current playback
                        self.player.stop()

                        # Wait a moment for stop to complete
                        time.sleep(0.5)

                        # Play next episode
                        self.play_next_episode(imdb_id, next_season, next_episode)

                    # Either way, we're done monitoring
                    return

                # Sleep briefly before next check
                time.sleep(0.5)

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error in autoplay monitoring: {e}', xbmc.LOGERROR)
            import traceback
            xbmc.log(f'[AIOStreams] Traceback: {traceback.format_exc()}', xbmc.LOGERROR)

    def start_monitoring(self, imdb_id, season, episode):
        """
        Start monitoring playback for autoplay.

        Args:
            imdb_id: IMDb ID of the show
            season: Current season
            episode: Current episode
        """
        # Stop any existing monitoring
        self.stop()

        # Reset state
        self.stop_monitoring.clear()
        self.streams_ready = False
        self.next_episode_streams = None
        self.next_episode_meta = None
        self.dialog_shown = False

        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self.monitor_playback,
            args=(imdb_id, season, episode)
        )
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

        xbmc.log('[AIOStreams] Autoplay monitoring started', xbmc.LOGINFO)

    def stop(self):
        """Stop autoplay monitoring."""
        if self.monitor_thread and self.monitor_thread.is_alive():
            xbmc.log('[AIOStreams] Stopping autoplay monitoring', xbmc.LOGINFO)
            self.stop_monitoring.set()
            self.monitor_thread = None
