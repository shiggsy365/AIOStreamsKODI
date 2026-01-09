"""
AIODI Skin Background Service
Monitors and updates widget properties for AIOStreams integration.
"""

import xbmc
import xbmcaddon
import xbmcgui
import time
from scripts.widget_manager import WidgetManager


class AIODIService:
    """Background service for AIODI skin."""

    def __init__(self):
        self.addon = xbmcaddon.Addon('skin.aiodi')
        self.monitor = xbmc.Monitor()
        self.widget_manager = WidgetManager()
        self.update_interval = 60  # seconds
        xbmc.log('AIODI Service: Started', xbmc.LOGINFO)

    def update_all_widgets(self):
        """Update widget properties for all pages."""
        try:
            for page in ['home', 'movies', 'shows']:
                self.widget_manager.set_window_properties(page)
            xbmc.log('AIODI Service: Updated all widget properties', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'AIODI Service: Error updating widgets: {str(e)}', xbmc.LOGERROR)

    def run(self):
        """Main service loop."""
        # Initial update
        self.update_all_widgets()

        # Monitor loop
        while not self.monitor.abortRequested():
            # Wait for abort or update interval
            if self.monitor.waitForAbort(self.update_interval):
                break

            # Periodic update of widget properties
            self.update_all_widgets()

        xbmc.log('AIODI Service: Stopped', xbmc.LOGINFO)


if __name__ == '__main__':
    service = AIODIService()
    service.run()
