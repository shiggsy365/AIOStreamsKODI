# -*- coding: utf-8 -*-
"""
Autoplay next episode dialog.

Shows a countdown overlay when approaching the end of an episode,
allowing user to immediately play the next episode or cancel.
"""
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import threading
import time


# Control IDs matching the XML skin
CONTROL_PLAY_NOW = 3001
CONTROL_CANCEL = 3002
CONTROL_COUNTDOWN_LABEL = 2001


class AutoplayNextDialog(xbmcgui.WindowXMLDialog):
    """
    Dialog that shows a countdown to autoplay the next episode.

    Displays episode thumbnail, title, and buttons to play now or cancel.
    After 10 seconds, automatically triggers playback unless cancelled.

    Usage:
        dialog = AutoplayNextDialog(
            'aiostreams-autoplay-next.xml',
            addon_path,
            'Default',
            '1080i',
            episode_title='S02E03 - The Episode Title',
            episode_thumb='path/to/thumb.jpg'
        )
        should_play = dialog.show_and_wait()
        del dialog

        if should_play:
            # Start playing next episode
    """

    # Action types
    ACTION_PLAY = 'play'
    ACTION_CANCEL = 'cancel'
    ACTION_TIMEOUT = 'timeout'

    def __init__(self, *args, **kwargs):
        """
        Initialize the autoplay dialog.

        Kwargs:
            episode_title: Title of next episode (e.g., "S02E03 - Episode Title")
            episode_thumb: Thumbnail image path for the episode
            countdown_seconds: Number of seconds to countdown (default: 10)
        """
        self.episode_title = kwargs.pop('episode_title', 'Next Episode')
        self.episode_thumb = kwargs.pop('episode_thumb', '')
        self.countdown_seconds = kwargs.pop('countdown_seconds', 10)

        self.action = None  # Will be ACTION_PLAY, ACTION_CANCEL, or ACTION_TIMEOUT
        self._countdown_thread = None
        self._stop_countdown = threading.Event()

        xbmc.log(f'[AIOStreams] AutoplayNextDialog init: {self.episode_title}', xbmc.LOGDEBUG)

    def onInit(self):
        """Called when dialog is initialized. Set up window properties and start countdown."""
        try:
            xbmc.log('[AIOStreams] AutoplayNextDialog onInit started', xbmc.LOGDEBUG)

            # Set window properties for the skin
            self.setProperty('episode_title', self.episode_title)

            if self.episode_thumb:
                xbmc.log(f'[AIOStreams] Setting episode thumb: {self.episode_thumb}', xbmc.LOGDEBUG)
                self.setProperty('episode_thumb', self.episode_thumb)

            # Start countdown in background thread
            self._start_countdown()

            # Set focus to cancel button by default (safer default)
            try:
                self.setFocusId(CONTROL_CANCEL)
            except Exception as e:
                xbmc.log(f'[AIOStreams] Could not set focus: {e}', xbmc.LOGWARNING)

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error in AutoplayNextDialog onInit: {e}', xbmc.LOGERROR)
            import traceback
            xbmc.log(f'[AIOStreams] Traceback: {traceback.format_exc()}', xbmc.LOGERROR)

    def _start_countdown(self):
        """Start the countdown thread."""
        self._stop_countdown.clear()
        self._countdown_thread = threading.Thread(target=self._countdown_loop)
        self._countdown_thread.daemon = True
        self._countdown_thread.start()

    def _countdown_loop(self):
        """Countdown loop that updates the label and auto-closes after timeout."""
        try:
            for remaining in range(self.countdown_seconds, 0, -1):
                if self._stop_countdown.is_set():
                    return

                # Update countdown text
                countdown_text = f'Playing in {remaining} second{"s" if remaining != 1 else ""}...'
                self.setProperty('countdown_text', countdown_text)

                # Wait 1 second (but check stop event frequently for responsiveness)
                for _ in range(10):
                    if self._stop_countdown.is_set():
                        return
                    time.sleep(0.1)

            # Countdown finished - trigger autoplay
            if not self._stop_countdown.is_set():
                xbmc.log('[AIOStreams] Countdown finished, auto-playing next episode', xbmc.LOGINFO)
                self.action = self.ACTION_TIMEOUT
                self.close()

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error in countdown loop: {e}', xbmc.LOGERROR)

    def onClick(self, control_id):
        """Handle button clicks."""
        try:
            if control_id == CONTROL_PLAY_NOW:
                xbmc.log('[AIOStreams] User clicked Play Now', xbmc.LOGINFO)
                self.action = self.ACTION_PLAY
                self._stop_countdown.set()
                self.close()

            elif control_id == CONTROL_CANCEL:
                xbmc.log('[AIOStreams] User clicked Cancel', xbmc.LOGINFO)
                self.action = self.ACTION_CANCEL
                self._stop_countdown.set()
                self.close()

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error in onClick: {e}', xbmc.LOGERROR)

    def onAction(self, action):
        """Handle action events (keyboard, remote control)."""
        action_id = action.getId()

        # Back/Escape actions - treat as cancel
        if action_id in (xbmcgui.ACTION_NAV_BACK,
                         xbmcgui.ACTION_PREVIOUS_MENU,
                         xbmcgui.ACTION_STOP,
                         92):  # BACKSPACE
            xbmc.log('[AIOStreams] Autoplay cancelled by user (back button)', xbmc.LOGINFO)
            self.action = self.ACTION_CANCEL
            self._stop_countdown.set()
            self.close()

        # Select action (Enter/OK) - trigger the focused button
        elif action_id in (xbmcgui.ACTION_SELECT_ITEM,
                           xbmcgui.ACTION_MOUSE_LEFT_CLICK,
                           7):  # ENTER
            self.onClick(self.getFocusId())

    def should_play(self):
        """
        Check if the next episode should be played.

        Returns:
            bool: True if user clicked Play Now or countdown expired,
                  False if user cancelled
        """
        return self.action in (self.ACTION_PLAY, self.ACTION_TIMEOUT)

    def show_and_wait(self):
        """
        Show the dialog and wait for user action or timeout.

        Returns:
            bool: True if should play next episode, False if cancelled
        """
        self.doModal()
        return self.should_play()


def show_autoplay_dialog(episode_title, episode_thumb='', countdown_seconds=10):
    """
    Convenience function to show the autoplay next episode dialog.

    Args:
        episode_title: Title of next episode (e.g., "S02E03 - Episode Title")
        episode_thumb: Optional episode thumbnail image path
        countdown_seconds: Number of seconds to countdown (default: 10)

    Returns:
        bool: True if should play next episode, False if cancelled
    """
    addon = xbmcaddon.Addon()
    addon_path = xbmcvfs.translatePath(addon.getAddonInfo('path'))

    try:
        dialog = AutoplayNextDialog(
            'aiostreams-autoplay-next.xml',
            addon_path,
            'Default',
            '1080i',
            episode_title=episode_title,
            episode_thumb=episode_thumb,
            countdown_seconds=countdown_seconds
        )

        should_play = dialog.show_and_wait()
        del dialog

        return should_play

    except Exception as e:
        xbmc.log(f'[AIOStreams] Error showing autoplay dialog: {e}', xbmc.LOGERROR)
        import traceback
        xbmc.log(f'[AIOStreams] Traceback: {traceback.format_exc()}', xbmc.LOGERROR)
        return False
