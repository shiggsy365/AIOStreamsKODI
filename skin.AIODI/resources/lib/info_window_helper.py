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
    xbmc.log(f'[AIOStreams] [InfoWindowHelper] {msg}', level)


def populate_cast_properties(content_type=None):
    """
    Query database directly for cast data using current ListItem's IMDb ID.
    """
    try:
        log('Starting cast property population')

        # Check if this is a custom info window (opened from plugin action)
        is_custom = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.IsCustom)') == 'true'

        if is_custom:
            # Use Window Properties set by plugin
            log('Custom info window detected - using Window Properties for cast')
            imdb_id = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.IMDB)')
            if not content_type:
                content_type = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.DBType)')
            log(f'Custom cast fetch - IMDB: {imdb_id}, Type: {content_type}')
        else:
            # Get current item's IMDb ID - try multiple methods
            imdb_id = xbmc.getInfoLabel('ListItem.IMDBNumber')

            # Debug: log all available info
            log(f'ListItem.Title: {xbmc.getInfoLabel("ListItem.Title")}')
            log(f'ListItem.Label: {xbmc.getInfoLabel("ListItem.Label")}')
            log(f'ListItem.Year: {xbmc.getInfoLabel("ListItem.Year")}')
            log(f'ListItem.IMDBNumber: {xbmc.getInfoLabel("ListItem.IMDBNumber")}')
            log(f'ListItem.Property(imdb_id): {xbmc.getInfoLabel("ListItem.Property(imdb_id)")}')
            log(f'ListItem.UniqueID(imdb): {xbmc.getInfoLabel("ListItem.UniqueID(imdb)")}')
            log(f'ListItem.Filenameandpath: {xbmc.getInfoLabel("ListItem.Filenameandpath")}')
            log(f'ListItem.Path: {xbmc.getInfoLabel("ListItem.Path")}')

            # If that's empty, try getting from custom property
            if not imdb_id:
                imdb_id = xbmc.getInfoLabel('ListItem.Property(imdb_id)')

            # If still empty, try from unique IDs
            if not imdb_id:
                imdb_id = xbmc.getInfoLabel('ListItem.UniqueID(imdb)')

            if not imdb_id:
                path = xbmc.getInfoLabel('ListItem.Filenameandpath')
                # Check for imdb_id or meta_id
                import re
                match = re.search(r'(?:imdb_id|meta_id)=([^&]+)', path)
                if match:
                    imdb_id = match.group(1)
                    log(f'Extracted IMDb ID from Filenameandpath: {imdb_id}')
                elif 'tt' in path:
                    # Fallback for just finding a tt ID in the path
                    match_tt = re.search(r'tt\d{7,}', path)
                    if match_tt:
                        imdb_id = match_tt.group(0)
                        log(f'Extracted IMDb ID from pattern match: {imdb_id}')

                        log(f'Extracted IMDb ID from Filenameandpath: {imdb_id}')

            if not content_type:
                content_type = xbmc.getInfoLabel('ListItem.DBType')  # 'movie' or 'tvshow'
        
        if not imdb_id:
            log(f'No IMDb ID found for current item. Tried: IMDBNumber, Property(imdb_id), UniqueID(imdb), Path extraction', xbmc.LOGWARNING)
            return None
        
        log(f'Fetching cast for {content_type}: {imdb_id}')
        
        # Import standalone API fetcher
        try:
            from fetch_cast import fetch_cast_from_api
            log('Successfully imported fetch_cast_from_api')
        except Exception as e:
            log(f'Failed to import fetch_cast_from_api: {e}', xbmc.LOGERROR)
            return
        
        # Determine content type from path or default to movie
        if not content_type:
            content_type = 'movie' if 'content_type=movie' in xbmc.getInfoLabel('ListItem.Filenameandpath') else 'tvshow'
        
        log(f'Fetching cast from API for {content_type}: {imdb_id}')
        
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
                log(f'Set InfoWindow.Trailer: {trailer_url}')
            else:
                home_window.clearProperty('InfoWindow.Trailer')
            
            # Set Cast properties
            if cast_list:
                log(f'Found {len(cast_list)} cast members from API')
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
                        log(f'Set cast {i}: Name="{name}", Role="{role}", Thumb="{thumb}"')
            
            # SET ADDITIONAL METADATA PROPERTIES
            director = meta_data.get('director', '')
            rating = meta_data.get('rating', '')
            premiered = meta_data.get('premiered', '')
            runtime = meta_data.get('runtime', '')
            
            if director:
                home_window.setProperty('InfoWindow.Director', director)
                log(f'Set InfoWindow.Director: {director}')
            
            if rating:
                home_window.setProperty('InfoWindow.Rating', rating)
                log(f'Set InfoWindow.Rating: {rating}')
            
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
                    log(f'Set InfoWindow.Premiered: {formatted_date}')
                except Exception as e:
                    # Fallback to original if formatting fails
                    home_window.setProperty('InfoWindow.Premiered', premiered)
                    log(f'Set InfoWindow.Premiered (fallback): {premiered}')
            
            if runtime:
                # Format: "125 min" or "2h 5m"
                home_window.setProperty('InfoWindow.Duration', runtime)
                log(f'Set InfoWindow.Duration: {runtime}')

            log(f'Cast and metadata properties populated successfully for {imdb_id}')
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

    xbmc.log('[info_window_helper] All properties reset. AsyncLoading=true', xbmc.LOGINFO)

def populate_all():
    """Populates all info window data asynchronously."""
    # Reset immediately to show loading state
    reset_info_properties()

    # Check if this is a custom info window (opened from plugin action)
    is_custom = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.IsCustom)') == 'true'

    if is_custom:
        # Use Window Properties set by plugin
        log('Custom info window detected - using Window Properties')
        db_type = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.DBType)')
        title = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.Title)')
        imdb_id = xbmc.getInfoLabel('Window(Home).Property(InfoWindow.IMDB)')
        tmdb_id = ''  # Plugin uses IMDb ID primarily
        season = ''
        episode = ''
        log(f'Custom info - DBType: {db_type}, Title: {title}, IMDB: {imdb_id}')
    else:
        # Extract IDs from ListItem (normal flow)
        log('Normal info window - using ListItem properties')
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
                    log(f'Imported populate_related_properties. Attempting fetch for {content_type}: {final_id}')
                    count = populate_related_properties(final_id, content_type)
                    log(f'populate_related_properties returned count: {count}')
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
        # For cached check, we might need to ensure cache is initialized or use direct check
        is_watchlist = trakt.is_in_watchlist(content_type, imdb_id)
        win.setProperty('InfoWindow.IsWatchlist', 'true' if is_watchlist else 'false')
        log(f'Set InfoWindow.IsWatchlist: {is_watchlist}')
        
        # Check Watched
        # For movies, easy. For shows, check if fully watched? Or just check if watched in general?
        # User asked for "Watched" button.
        is_watched = trakt.is_watched(content_type, imdb_id)
        win.setProperty('InfoWindow.IsWatched', 'true' if is_watched else 'false')
        log(f'Set InfoWindow.IsWatched: {is_watched}')
        
    except Exception as e:
        log(f'Error checking Trakt status: {e}', xbmc.LOGERROR)



if __name__ == '__main__':
    populate_all()
