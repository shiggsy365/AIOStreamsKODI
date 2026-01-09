"""
AIOStreams Widget Manager for AIODI Skin
Manages dynamic widget configuration and integration with AIOStreams addon.
"""

import xbmc
import xbmcaddon
import xbmcgui
import json
import sys

ADDON = xbmcaddon.Addon('skin.aiodi')
AIOSTREAMS_ID = 'plugin.video.aiostreams'


class WidgetManager:
    """Manage AIOStreams widgets for skin."""

    AVAILABLE_WIDGETS = {
        'continue_watching': {
            'label': 'Continue Watching',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_progress',
            'icon': 'DefaultTVShows.png',
            'category': 'trakt'
        },
        'next_up': {
            'label': 'Next Up',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_next_up',
            'icon': 'DefaultTVShows.png',
            'category': 'trakt'
        },
        'trending_movies': {
            'label': 'Trending Movies',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_trending&media_type=movies',
            'icon': 'DefaultMovies.png',
            'category': 'movies'
        },
        'trending_shows': {
            'label': 'Trending TV Shows',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_trending&media_type=shows',
            'icon': 'DefaultTVShows.png',
            'category': 'shows'
        },
        'popular_movies': {
            'label': 'Popular Movies',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_popular&media_type=movies',
            'icon': 'DefaultMovies.png',
            'category': 'movies'
        },
        'popular_shows': {
            'label': 'Popular TV Shows',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_popular&media_type=shows',
            'icon': 'DefaultTVShows.png',
            'category': 'shows'
        },
        'watchlist_movies': {
            'label': 'Watchlist - Movies',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_watchlist&media_type=movies',
            'icon': 'DefaultMovies.png',
            'category': 'movies'
        },
        'watchlist_shows': {
            'label': 'Watchlist - Shows',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_watchlist&media_type=shows',
            'icon': 'DefaultTVShows.png',
            'category': 'shows'
        },
        'recommended_movies': {
            'label': 'Recommended Movies',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_recommended&media_type=movies',
            'icon': 'DefaultMovies.png',
            'category': 'movies'
        },
        'recommended_shows': {
            'label': 'Recommended Shows',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_recommended&media_type=shows',
            'icon': 'DefaultTVShows.png',
            'category': 'shows'
        },
        'collection_movies': {
            'label': 'Collection - Movies',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_collection&media_type=movies',
            'icon': 'DefaultMovies.png',
            'category': 'movies'
        },
        'collection_shows': {
            'label': 'Collection - Shows',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_collection&media_type=shows',
            'icon': 'DefaultTVShows.png',
            'category': 'shows'
        },
        'anticipated_movies': {
            'label': 'Anticipated Movies',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_anticipated&media_type=movies',
            'icon': 'DefaultMovies.png',
            'category': 'movies'
        },
        'anticipated_shows': {
            'label': 'Anticipated Shows',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_anticipated&media_type=shows',
            'icon': 'DefaultTVShows.png',
            'category': 'shows'
        },
        'most_watched_movies': {
            'label': 'Most Watched Movies',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_most_watched&media_type=movies',
            'icon': 'DefaultMovies.png',
            'category': 'movies'
        },
        'most_watched_shows': {
            'label': 'Most Watched Shows',
            'action': 'plugin://plugin.video.aiostreams/?action=trakt_most_watched&media_type=shows',
            'icon': 'DefaultTVShows.png',
            'category': 'shows'
        }
    }

    DEFAULT_WIDGETS = {
        'home': ['continue_watching', 'trending_movies', 'trending_shows', 'watchlist_movies'],
        'movies': ['trending_movies', 'popular_movies', 'watchlist_movies', 'collection_movies'],
        'shows': ['continue_watching', 'next_up', 'trending_shows', 'watchlist_shows']
    }

    def __init__(self):
        self.window = xbmcgui.Window(10000)  # Home window

    def check_aiostreams_installed(self):
        """Check if AIOStreams addon is installed."""
        try:
            xbmcaddon.Addon(AIOSTREAMS_ID)
            return True
        except RuntimeError:
            return False

    def get_page_widgets(self, page):
        """Get active widgets for a page."""
        setting_key = f'{page}_widgets'
        widgets_json = ADDON.getSetting(setting_key)

        if widgets_json:
            try:
                return json.loads(widgets_json)
            except (json.JSONDecodeError, ValueError):
                xbmc.log(f'AIODI: Failed to parse widgets for {page}, using defaults', xbmc.LOGWARNING)

        # Return defaults
        return self.DEFAULT_WIDGETS.get(page, [])

    def save_page_widgets(self, page, widgets):
        """Save widget configuration for a page."""
        setting_key = f'{page}_widgets'
        ADDON.setSetting(setting_key, json.dumps(widgets))
        xbmc.log(f'AIODI: Saved {len(widgets)} widgets for {page}', xbmc.LOGINFO)

    def set_window_properties(self, page):
        """Set window properties for skin to use."""
        widgets = self.get_page_widgets(page)

        # Clear existing properties
        for i in range(20):
            self.window.clearProperty(f'AIOStreams.{page}.Widget.{i}.Label')
            self.window.clearProperty(f'AIOStreams.{page}.Widget.{i}.Action')
            self.window.clearProperty(f'AIOStreams.{page}.Widget.{i}.Icon')

        # Set new properties
        for i, widget_id in enumerate(widgets):
            if widget_id in self.AVAILABLE_WIDGETS:
                widget = self.AVAILABLE_WIDGETS[widget_id]
                self.window.setProperty(f'AIOStreams.{page}.Widget.{i}.Label', widget['label'])
                self.window.setProperty(f'AIOStreams.{page}.Widget.{i}.Action', widget['action'])
                self.window.setProperty(f'AIOStreams.{page}.Widget.{i}.Icon', widget['icon'])

        self.window.setProperty(f'AIOStreams.{page}.Widget.Count', str(len(widgets)))
        xbmc.log(f'AIODI: Set {len(widgets)} widget properties for {page}', xbmc.LOGDEBUG)

    def move_widget_up(self, page, index):
        """Move widget up in the list."""
        widgets = self.get_page_widgets(page)
        if index > 0 and index < len(widgets):
            widgets[index], widgets[index - 1] = widgets[index - 1], widgets[index]
            self.save_page_widgets(page, widgets)
            self.set_window_properties(page)
            return True
        return False

    def move_widget_down(self, page, index):
        """Move widget down in the list."""
        widgets = self.get_page_widgets(page)
        if index >= 0 and index < len(widgets) - 1:
            widgets[index], widgets[index + 1] = widgets[index + 1], widgets[index]
            self.save_page_widgets(page, widgets)
            self.set_window_properties(page)
            return True
        return False

    def add_widget(self, page, widget_id):
        """Add a widget to the page."""
        if widget_id not in self.AVAILABLE_WIDGETS:
            return False

        widgets = self.get_page_widgets(page)
        if widget_id not in widgets:
            widgets.append(widget_id)
            self.save_page_widgets(page, widgets)
            self.set_window_properties(page)
            return True
        return False

    def remove_widget(self, page, widget_id):
        """Remove a widget from the page."""
        widgets = self.get_page_widgets(page)
        if widget_id in widgets:
            widgets.remove(widget_id)
            self.save_page_widgets(page, widgets)
            self.set_window_properties(page)
            return True
        return False

    def reset_widgets(self, page):
        """Reset widgets to defaults for a page."""
        defaults = self.DEFAULT_WIDGETS.get(page, [])
        self.save_page_widgets(page, defaults)
        self.set_window_properties(page)
        return True


def main():
    """Main entry point for script calls."""
    manager = WidgetManager()

    # Parse arguments
    args = {}
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if '=' in arg:
                key, value = arg.split('=', 1)
                args[key] = value

    action = args.get('action', 'update')
    page = args.get('page', 'home')

    # Check if AIOStreams is installed
    if not manager.check_aiostreams_installed():
        xbmc.log('AIODI: AIOStreams addon not found!', xbmc.LOGWARNING)
        manager.window.setProperty('AIOStreams.Installed', 'false')
        return
    else:
        manager.window.setProperty('AIOStreams.Installed', 'true')

    # Handle actions
    if action == 'update':
        manager.set_window_properties(page)
    elif action == 'load':
        # Load all pages
        for page in ['home', 'movies', 'shows']:
            manager.set_window_properties(page)
    elif action == 'add':
        widget_id = args.get('widget_id', '')
        if widget_id:
            manager.add_widget(page, widget_id)
    elif action == 'remove':
        widget_id = args.get('widget_id', '')
        if widget_id:
            manager.remove_widget(page, widget_id)
    elif action == 'move_up':
        index = int(args.get('index', -1))
        manager.move_widget_up(page, index)
    elif action == 'move_down':
        index = int(args.get('index', -1))
        manager.move_widget_down(page, index)
    elif action == 'reset':
        manager.reset_widgets(page)


if __name__ == '__main__':
    main()
