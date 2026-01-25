"""
Helper script to split genre strings into individual genres (max 3).
Sets window properties for display in skin.
"""
import xbmc
import xbmcgui
import sys


def split_genres():
    """Split genre string from focused widget item into individual genres (max 3)."""
    try:
        # Get the active widget ID
        active_widget = xbmc.getInfoLabel('Skin.String(ActiveWidgetID)')

        win = xbmcgui.Window(10000)

        # Get genre string from the currently focused item in the active widget
        if active_widget:
            genre_string = xbmc.getInfoLabel(f'Container({active_widget}).ListItem.Genre')
        else:
            genre_string = xbmc.getInfoLabel('ListItem.Genre')

        # Clear previous genres
        for i in range(1, 4):
            win.clearProperty(f'Widget.Genre.{i}')

        if not genre_string:
            return

        # Split by common delimiters (/, &, comma)
        import re
        genres = re.split(r'\s*/\s*|\s*&\s*|\s*,\s*', genre_string)

        # Remove empty strings and strip whitespace
        genres = [g.strip() for g in genres if g.strip()]

        # Set up to 3 genres as properties
        for i, genre in enumerate(genres[:3], 1):
            win.setProperty(f'Widget.Genre.{i}', genre)
            xbmc.log(f'[GenreSplitter] Set Genre.{i}: {genre}', xbmc.LOGDEBUG)

    except Exception as e:
        xbmc.log(f'[GenreSplitter] Error: {e}', xbmc.LOGERROR)


if __name__ == '__main__':
    split_genres()
