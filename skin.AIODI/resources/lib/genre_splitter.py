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
        # Get genre string from the currently focused list item
        # When called from onfocus, ListItem refers to the focused item
        genre_string = xbmc.getInfoLabel('ListItem.Genre')

        win = xbmcgui.Window(10000)

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
