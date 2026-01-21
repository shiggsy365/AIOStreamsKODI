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
    youtube_available = xbmc.getCondVisibility('System.HasAddon(plugin.video.youtube)')
    xbmc.log(f'[AIOStreams GlobalSearch] Search query: {query}', xbmc.LOGINFO)
    
    # Import the main addon module
    try:
        # Import search functions from main addon
        import addon
        
        # Set mixed content type for global search
        xbmcplugin.setContent(HANDLE, 'videos')
        xbmcplugin.setPluginCategory(HANDLE, f'AIOStreams: {query}')
        
        # Search movies
        xbmc.log(f'[AIOStreams GlobalSearch] Searching movies for: {query}', xbmc.LOGDEBUG)
        movie_results = addon.search_catalog(query, 'movie', skip=0)
        
        # Search TV shows
        xbmc.log(f'[AIOStreams GlobalSearch] Searching TV shows for: {query}', xbmc.LOGDEBUG)
        series_results = addon.search_catalog(query, 'series', skip=0)
        
        # Search YouTube (only if available)
        youtube_results = {'metas': []}
        if youtube_available:
            xbmc.log(f'[AIOStreams GlobalSearch] Searching YouTube for: {query}', xbmc.LOGDEBUG)
            youtube_results = addon.search_catalog(query, 'video', skip=0)
        
        # Add movie results
        if movie_results and 'metas' in movie_results:
            for meta in movie_results['metas'][:10]:  # Limit to 10 results
                item_id = meta.get('id')
                title = meta.get('name', 'Unknown')
                poster = meta.get('poster', '')
                fanart = meta.get('background', '')
                clearlogo = meta.get('logo', '')
                
                url = addon.get_url(action='play', content_type='movie', imdb_id=item_id, 
                                   title=title, poster=poster, fanart=fanart, clearlogo=clearlogo)
                list_item = addon.create_listitem_with_context(meta, 'movie', url)
                list_item.setProperty('IsPlayable', 'true')
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, False)
        
        # Add TV show results
        if series_results and 'metas' in series_results:
            for meta in series_results['metas'][:10]:  # Limit to 10 results
                item_id = meta.get('id')
                url = addon.get_url(action='show_seasons', meta_id=item_id)
                list_item = addon.create_listitem_with_context(meta, 'series', url)
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, True)

        # Add YouTube results
        if youtube_available and youtube_results and 'metas' in youtube_results:
            for meta in youtube_results['metas'][:5]:  # Limit to 5 results
                item_id = meta.get('id')
                title = meta.get('name', 'Unknown')
                url = addon.get_url(action='play', content_type='video', imdb_id=item_id, title=title)
                list_item = addon.create_listitem_with_context(meta, 'video', url)
                list_item.setProperty('IsPlayable', 'true')
                xbmcplugin.addDirectoryItem(HANDLE, url, list_item, False)
        
        # End the directory listing
        xbmcplugin.endOfDirectory(HANDLE, succeeded=True)
        
        movie_count = len(movie_results.get('metas', [])) if movie_results else 0
        series_count = len(series_results.get('metas', [])) if series_results else 0
        youtube_count = len(youtube_results.get('metas', [])) if youtube_results else 0
        xbmc.log(f'[AIOStreams GlobalSearch] Found {movie_count} movies, {series_count} TV shows, {youtube_count} YouTube for: {query}', xbmc.LOGINFO)
        
    except Exception as e:
        xbmc.log(f'[AIOStreams GlobalSearch] Error: {e}', xbmc.LOGERROR)
        import traceback
        xbmc.log(f'[AIOStreams GlobalSearch] Traceback: {traceback.format_exc()}', xbmc.LOGERROR)
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
