# -*- coding: utf-8 -*-
"""
Global Search Provider for AIOStreams

This module integrates AIOStreams with the Global Search addon (script.globalsearch).
When users perform a global search in Kodi, AIOStreams will be included in the results.
"""

import sys
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin

# Get addon handle
try:
    HANDLE = int(sys.argv[1])
except (IndexError, ValueError):
    HANDLE = -1

ADDON = xbmcaddon.Addon()


def search(query):
    """
    Global search entry point called by script.globalsearch.
    
    Args:
        query: Search query string from global search
    """
    xbmc.log(f'[AIOStreams GlobalSearch] Search query: {query}', xbmc.LOGINFO)
    
    # Import the main addon module
    try:
        # Import search functions from main addon
        import addon
        
        # Add a folder for Movies
        list_item_movies = xbmcgui.ListItem(label=f'[Movies] {query}')
        list_item_movies.setInfo('video', {'title': f'Movies: {query}', 'plot': 'Search results for movies'})
        url_movies = addon.get_url(action='search_by_tab', query=query, content_type='movie')
        xbmcplugin.addDirectoryItem(HANDLE, url_movies, list_item_movies, isFolder=True)
        
        # Add a folder for TV Shows
        list_item_shows = xbmcgui.ListItem(label=f'[TV Shows] {query}')
        list_item_shows.setInfo('video', {'title': f'TV Shows: {query}', 'plot': 'Search results for TV shows'})
        url_shows = addon.get_url(action='search_by_tab', query=query, content_type='series')
        xbmcplugin.addDirectoryItem(HANDLE, url_shows, list_item_shows, isFolder=True)
        
        # End the directory listing
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True)
        
        xbmc.log(f'[AIOStreams GlobalSearch] Added movie and TV show search folders for: {query}', xbmc.LOGINFO)
        
    except Exception as e:
        xbmc.log(f'[AIOStreams GlobalSearch] Error: {e}', xbmc.LOGERROR)
        # Show error to user
        xbmcgui.Dialog().notification(
            'AIOStreams Search Error',
            str(e),
            xbmcgui.NOTIFICATION_ERROR,
            3000
        )
        # End directory even on error
        xbmcplugin.endOfDirectory(HANDLE, succeeded=False)


if __name__ == '__main__':
    # Get search query from arguments
    # Global search passes the query as: plugin://plugin.video.aiostreams/globalsearch?query=<search_term>
    if len(sys.argv) > 2:
        # Parse query from URL parameters
        from urllib.parse import parse_qsl
        params = dict(parse_qsl(sys.argv[2][1:]))
        query = params.get('query', '')
        
        if query:
            search(query)
        else:
            xbmc.log('[AIOStreams GlobalSearch] No query provided', xbmc.LOGWARNING)
    else:
        xbmc.log('[AIOStreams GlobalSearch] Invalid arguments', xbmc.LOGWARNING)
