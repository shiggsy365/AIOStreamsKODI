"""
Helper script to handle Trakt actions from DialogVideoInfo buttons.
"""
import xbmc
import xbmcgui
import sys


def log(msg):
    xbmc.log(f'[AIOStreams] [TraktAction] {msg}', xbmc.LOGINFO)


def perform_action(action):
    """Perform a Trakt action using InfoWindow properties."""
    try:
        # Get the window
        win = xbmcgui.Window(10000)

        # Get required properties
        imdb_id = win.getProperty('InfoWindow.IMDB')
        db_type = win.getProperty('InfoWindow.DBType')

        # Fallback to ListItem properties if InfoWindow properties not set
        if not imdb_id:
            imdb_id = xbmc.getInfoLabel('ListItem.IMDBNumber')
        if not db_type:
            db_type = xbmc.getInfoLabel('ListItem.DBType')
        if not imdb_id:
            imdb_id = xbmc.getInfoLabel('ListItem.Property(id)')

        # Map DBType to media_type
        media_type = db_type
        if db_type in ['tvshow', 'season', 'episode']:
            media_type = 'show'
        elif db_type == 'movie':
            media_type = 'movie'

        log(f'Action: {action}, IMDB: {imdb_id}, DBType: {db_type}, MediaType: {media_type}')

        if not imdb_id:
            log('No IMDb ID found - cannot perform Trakt action')
            return

        # Build the plugin URL
        plugin_action_map = {
            'add_watchlist': 'trakt_add_watchlist',
            'remove_watchlist': 'trakt_remove_watchlist',
            'mark_watched': 'trakt_mark_watched',
            'mark_unwatched': 'trakt_mark_unwatched'
        }

        plugin_action = plugin_action_map.get(action)
        if not plugin_action:
            log(f'Unknown action: {action}')
            return

        # Execute the plugin action
        plugin_url = f'plugin://plugin.video.aiostreams/?action={plugin_action}&imdb_id={imdb_id}&media_type={media_type}'
        log(f'Executing: RunPlugin({plugin_url})')
        xbmc.executebuiltin(f'RunPlugin({plugin_url})')

        # Wait a moment for the action to complete
        xbmc.sleep(500)

        # Refresh widgets based on action type
        if action in ['add_watchlist', 'remove_watchlist']:
            log('Refreshing watchlist widgets')
            # Refresh watchlist widgets (Home widgets 1 and 2, Movie widgets, TV widgets)
            # Home Watchlist Movies (10200) and Watchlist Series (10300)
            xbmc.executebuiltin('Container(10200).Refresh')
            xbmc.executebuiltin('Container(10300).Refresh')
            # Also refresh any other watchlist-related widgets
            for widget_id in range(5100, 5300, 10):  # Movie widgets
                xbmc.executebuiltin(f'Container({widget_id}).Refresh')
            for widget_id in range(6100, 6300, 10):  # TV widgets
                xbmc.executebuiltin(f'Container({widget_id}).Refresh')

        elif action in ['mark_watched', 'mark_unwatched']:
            log('Refreshing Next Up list')
            # Refresh Next Up widget (10100)
            xbmc.executebuiltin('Container(10100).Refresh')
            # Also refresh any progress/continue watching widgets
            for widget_id in range(10100, 10400, 100):
                xbmc.executebuiltin(f'Container({widget_id}).Refresh')

    except Exception as e:
        log(f'Error performing Trakt action: {e}')
        import traceback
        log(traceback.format_exc())


if __name__ == '__main__':
    # Parse arguments
    if len(sys.argv) > 1:
        args = sys.argv[1].split(',')
        action_arg = [arg for arg in args if arg.startswith('action=')]
        if action_arg:
            action = action_arg[0].split('=')[1]
            perform_action(action)
