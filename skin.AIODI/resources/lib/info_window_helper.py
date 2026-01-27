"""
Helper script for custom information window.
Queries plugin's get_meta function for cast data, fetching from API if needed.
"""
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import sys
import os
import time


def log(msg, level=xbmc.LOGINFO):
    if level in [xbmc.LOGERROR, xbmc.LOGWARNING]:
        xbmc.log(f'[info_window_helper] {msg}', level)


def populate_cast_properties(content_type=None):
    """
    Query database directly for cast data using current ListItem's IMDb ID.
    """
    try:
        # Check if this is a custom info window (opened from plugin action)
        is_custom = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.IsCustom)') == 'true'

        if is_custom:
            # Use Window Properties set by plugin
            imdb_id = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.IMDB)')
            if not content_type:
                content_type = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.DBType)')
        else:
            # Get current item's IMDb ID - try multiple methods
            # PRIORITY: Check if this is a Next Up episode (needs show IMDb for cast, not episode IMDb)
            imdb_id = xbmc.getInfoLabel('ListItem.Property(NextUpShowIMDb)')
            if imdb_id:
                if not content_type:
                    content_type = 'tvshow'
            else:
                imdb_id = xbmc.getInfoLabel('ListItem.IMDBNumber')

            # If that's empty, try getting from custom property (standardized)
            if not imdb_id:
                imdb_id = xbmc.getInfoLabel('ListItem.Property(imdb_id)')
            
            if not imdb_id:
                imdb_id = xbmc.getInfoLabel('ListItem.Property(meta_id)')
            
            if not imdb_id:
                imdb_id = xbmc.getInfoLabel('ListItem.Property(id)')

            # If still empty, try from unique IDs
            if not imdb_id:
                imdb_id = xbmc.getInfoLabel('ListItem.UniqueID(imdb)')

            if not imdb_id:
                path = xbmc.getInfoLabel('ListItem.Filenameandpath') or xbmc.getInfoLabel('ListItem.Path')
                # Check for imdb_id or meta_id in URL/Path
                import re
                match = re.search(r'(?:imdb_id|meta_id)=([^&]+)', path)
                if match:
                    imdb_id = match.group(1)
                elif 'tt' in path:
                    # Fallback for just finding a tt ID in the path
                    match_tt = re.search(r'tt\d{7,}', path)
                    if match_tt:
                        imdb_id = match_tt.group(0)

            if not content_type:
                content_type = xbmc.getInfoLabel('ListItem.DBType')  # 'movie' or 'tvshow'
        
        if not imdb_id:
            # Last resort fallback: Check Window properties (in case dialog opened without ListItem context)
            imdb_id = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.IMDB)')
            if imdb_id:
                if not content_type:
                    content_type = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.DBType)') or 'movie'
            else:
                log(f'No IMDb ID found for current item. Tried: IMDBNumber, Property(imdb_id), UniqueID(imdb), Path extraction, Window properties', xbmc.LOGWARNING)
                return None

        # Import standalone API fetcher
        try:
            from fetch_cast import fetch_cast_from_api
        except Exception as e:
            log(f'Failed to import fetch_cast_from_api: {e}', xbmc.LOGERROR)
            return

        # Determine content type from path or default to movie
        if not content_type:
            content_type = 'movie' if 'content_type=movie' in xbmc.getInfoLabel('ListItem.Filenameandpath') else 'tvshow'
        
        # Get home window and clear old cast properties
        home_window = xbmcgui.Window(10000)
        for i in range(1, 6):
            home_window.clearProperty(f'InfoWindow.Cast.{i}.Name')
            home_window.clearProperty(f'InfoWindow.Cast.{i}.Role')
            home_window.clearProperty(f'InfoWindow.Cast.{i}.Thumb')
        
        # Fetch cast and metadata from API
        try:
            meta_data = fetch_cast_from_api(imdb_id, content_type)
            if not meta_data:
                log(f'No data returned from API for {imdb_id}', xbmc.LOGWARNING)
                return imdb_id

            cast_list = meta_data.get('cast', [])
            trailer_url = meta_data.get('trailer_url')
            
            # Set Trailer Property
            if trailer_url:
                home_window.setProperty('InfoWindow.Trailer', trailer_url)
            else:
                home_window.clearProperty('InfoWindow.Trailer')

            # Set Cast properties
            if cast_list:
                # Set properties for up to 5 cast members
                for i in range(1, 6):
                    if i <= len(cast_list):
                        cast_member = cast_list[i-1]
                        name = cast_member.get('name', '')
                        role = cast_member.get('character', '')
                        thumb = cast_member.get('photo', '')

                        home_window.setProperty(f'InfoWindow.Cast.{i}.Name', name)
                        home_window.setProperty(f'InfoWindow.Cast.{i}.Role', role)
                        home_window.setProperty(f'InfoWindow.Cast.{i}.Thumb', thumb)

            # SET ADDITIONAL METADATA PROPERTIES
            director = meta_data.get('director', '')
            rating = meta_data.get('rating', '')
            premiered = meta_data.get('premiered', '')
            runtime = meta_data.get('runtime', '')

            if director:
                home_window.setProperty('InfoWindow.Director', director)

            if rating:
                home_window.setProperty('InfoWindow.Rating', rating)

            if premiered:
                # Format: "2008-01-20T12:00:00.000Z" -> user's date format
                if 'T' in premiered:
                    premiered = premiered.split('T')[0]

                # Convert to Kodi's default date format
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(premiered, '%Y-%m-%d')
                    # Use Kodi's regional date format
                    date_format = xbmc.getRegion('dateshort')
                    # Convert Python strftime format: %d/%m/%Y -> dd/mm/yyyy
                    formatted_date = date_obj.strftime(date_format)
                    home_window.setProperty('InfoWindow.Premiered', formatted_date)
                except Exception:
                    # Fallback to original if formatting fails
                    home_window.setProperty('InfoWindow.Premiered', premiered)

            if runtime:
                # Format: "125 min" or "2h 5m"
                home_window.setProperty('InfoWindow.Duration', runtime)
        except Exception as e:
            log(f'Error fetching data from API: {e}', xbmc.LOGERROR)
            import traceback
            log(traceback.format_exc(), xbmc.LOGERROR)
        
        return imdb_id
        
    except Exception as e:
        log(f'Error populating cast properties: {e}', xbmc.LOGERROR)
        import traceback
        log(traceback.format_exc(), xbmc.LOGERROR)
        return None


def reset_info_properties():
    """Resets all info window properties to trigger loading state and clear previous data."""
    win = xbmcgui.Window(10000)
    win.setProperty('AsyncLoading', 'true')

    # Clear Metadata
    win.clearProperty('InfoWindow.Director')
    win.clearProperty('InfoWindow.Rating')
    win.clearProperty('InfoWindow.Premiered')
    win.clearProperty('InfoWindow.Duration')
    win.clearProperty('InfoWindow.Trailer')

    # Clear Cast properties (1-5)
    for i in range(1, 6):
        win.clearProperty(f'InfoWindow.Cast.{i}.Name')
        win.clearProperty(f'InfoWindow.Cast.{i}.Role')
        win.clearProperty(f'InfoWindow.Cast.{i}.Thumb')

    # Clear Related Content properties (1-10)
    for i in range(1, 11):
        win.clearProperty(f'InfoWindow.Related.{i}.Title')
        win.clearProperty(f'InfoWindow.Related.{i}.Thumb')
        win.clearProperty(f'InfoWindow.Related.{i}.Year')
        win.clearProperty(f'InfoWindow.Related.{i}.IMDB')

    # Clear Trakt status properties
    win.clearProperty('InfoWindow.IsWatchlist')
    win.clearProperty('InfoWindow.IsWatched')

    # Restricted logging for reset

def populate_all():
    """Populates all info window data asynchronously."""
    # Reset immediately to show loading state
    reset_info_properties()

    # Check if this is a custom info window (opened from plugin action)
    is_custom = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.IsCustom)') == 'true'

    if is_custom:
        # Use Window Properties set by plugin
        db_type = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.DBType)')
        title = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.Title)')
        imdb_id = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.IMDB)')
        tmdb_id = ''  # Plugin uses IMDb ID primarily
        season = ''
        episode = ''
    else:
        # Extract IDs from ListItem (normal flow)
        db_type = xbmc.getInfoLabel('ListItem.DBType')
        title = xbmc.getInfoLabel('ListItem.Title')
        imdb_id = xbmc.getInfoLabel('ListItem.IMDBNumber')
        tmdb_id = xbmc.getInfoLabel('ListItem.Property(tmdb_id)')
        season = xbmc.getInfoLabel('ListItem.Season')
        episode = xbmc.getInfoLabel('ListItem.Episode')

        # Fallback ID extraction if needed
        if not imdb_id and not tmdb_id:
            path = xbmc.getInfoLabel('ListItem.Filenameandpath')
            if 'plugin.video.aiostreams' in path:
                import re
                match = re.search(r'tt\d{7,}', path)
                if match:
                    imdb_id = match.group(0)

    # Define the worker function
    def worker(worker_imdb_id, worker_tmdb_id):
        win = xbmcgui.Window(10000)
        try:
            content_type = xbmc.getInfoLabel('ListItem.DBType')
            if not content_type:
               path = xbmc.getInfoLabel('ListItem.Filenameandpath')
               content_type = 'movie' if 'content_type=movie' in path else 'tvshow'

            # 0. Fetch Trailer - now handled by populate_cast_properties using API metadata
            # Removed redundant fetch_related call

            # 1. Populate Cast (returns verified imdb_id if found)
            found_imdb_id = populate_cast_properties(content_type)
            
            # Use the best available ID
            final_id = found_imdb_id if found_imdb_id else (worker_imdb_id or worker_tmdb_id)
            
            # 2. Populate Related items
            if final_id:
                try:
                    from fetch_related import populate_related_properties
                    populate_related_properties(final_id, content_type)
                except Exception as e:
                    log(f'Failed to fetch related items: {e}', xbmc.LOGERROR)
            else:
                 xbmc.log(f'[info_window_helper] No ID found for related items search', xbmc.LOGWARNING)

            # 3. Check Trakt Status
            if final_id:
                get_trakt_status(content_type, final_id)

        except Exception as e:
            xbmc.log(f'[info_window_helper] Error in async worker: {e}', xbmc.LOGERROR)
        finally:
            # Always clear loading state
            xbmc.sleep(500) # Small buffer to smooth UI transition
            win.setProperty('AsyncLoading', '')
            xbmc.log('[info_window_helper] Async worker finished. AsyncLoading cleared.', xbmc.LOGINFO)

    # Start the worker thread
    import threading
    t = threading.Thread(target=worker, args=(imdb_id, tmdb_id))
    t.daemon = True
    t.start()

def get_trakt_status(content_type, imdb_id):
    """Check Trakt status (Watchlist/Watched) using plugin modules."""
    try:
        # Add plugin path to sys.path to access modules
        addon = xbmcaddon.Addon('plugin.video.aiostreams')
        plugin_path = xbmc.translatePath(addon.getAddonInfo('path'))
        if plugin_path not in sys.path:
            sys.path.append(plugin_path)
        
        from resources.lib import trakt
        from resources.lib.globals import g
        g.init_globals(sys.argv) # Initialize globals if needed
        
        win = xbmcgui.Window(10000)
        
        # Check Watchlist
        is_watchlist = trakt.is_in_watchlist(content_type, imdb_id)
        win.setProperty('InfoWindow.IsWatchlist', 'true' if is_watchlist else 'false')

        # Check Watched
        is_watched = trakt.is_watched(content_type, imdb_id)
        win.setProperty('InfoWindow.IsWatched', 'true' if is_watched else 'false')
        
    except Exception as e:
        log(f'Error checking Trakt status: {e}', xbmc.LOGERROR)



if __name__ == '__main__':
    populate_all()
