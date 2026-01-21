import xbmc
import xbmcgui
import time

try:
    # Get the home window for properties
    home_window = xbmcgui.Window(10000)
    
    # Log the search query and URLs
    search_query = home_window.getProperty('GlobalSearch.Query')
    active_tab = home_window.getProperty('GlobalSearch.ActiveTab')
    movies_url = home_window.getProperty('GlobalSearch.MoviesURL')
    series_url = home_window.getProperty('GlobalSearch.SeriesURL')
    youtube_url = home_window.getProperty('GlobalSearch.YouTubeURL')
    
    xbmc.log('[Search Results Debug] ========== SEARCH RESULTS DEBUG ==========', xbmc.LOGINFO)
    xbmc.log('[Search Results Debug] Search Query: %s' % search_query, xbmc.LOGINFO)
    xbmc.log('[Search Results Debug] Active Tab: %s' % active_tab, xbmc.LOGINFO)
    xbmc.log('[Search Results Debug] Movies URL Property: %s' % movies_url, xbmc.LOGINFO)
    xbmc.log('[Search Results Debug] Series URL Property: %s' % series_url, xbmc.LOGINFO)
    xbmc.log('[Search Results Debug] YouTube URL Property: %s' % youtube_url, xbmc.LOGINFO)
    
    # Get the current active window dialog
    current_dialog_id = xbmcgui.getCurrentWindowDialogId()
    xbmc.log('[Search Results Debug] Current Dialog ID: %d' % current_dialog_id, xbmc.LOGINFO)
    
    # Try to get the results window
    results_window = xbmcgui.Window(current_dialog_id)
    
    # Wait and check multiple times for results to load
    for attempt in range(10):
        time.sleep(1)  # Wait 1 second between checks
        
        xbmc.log('[Search Results Debug] --- Check #%d (after %d seconds) ---' % (attempt + 1, attempt + 1), xbmc.LOGINFO)
        
        # Check Movies container (ID 100)
        try:
            movies_container = results_window.getControl(100)
            movies_count = movies_container.size()
            xbmc.log('[Search Results Debug] Movies Container (100) - Items: %d' % movies_count, xbmc.LOGINFO)
            
            if movies_count > 0:
                # Log first few items
                for i in range(min(3, movies_count)):
                    item = movies_container.getListItem(i)
                    xbmc.log('[Search Results Debug]   Item %d: %s' % (i, item.getLabel()), xbmc.LOGINFO)
        except Exception as e:
            xbmc.log('[Search Results Debug] Movies Container (100) - Error: %s' % str(e), xbmc.LOGERROR)
        
        # Check TV Shows container (ID 101)
        try:
            series_container = results_window.getControl(101)
            series_count = series_container.size()
            xbmc.log('[Search Results Debug] TV Shows Container (101) - Items: %d' % series_count, xbmc.LOGINFO)
            
            if series_count > 0:
                # Log first few items
                for i in range(min(3, series_count)):
                    item = series_container.getListItem(i)
                    xbmc.log('[Search Results Debug]   Item %d: %s' % (i, item.getLabel()), xbmc.LOGINFO)
        except Exception as e:
            xbmc.log('[Search Results Debug] TV Shows Container (101) - Error: %s' % str(e), xbmc.LOGERROR)
        
        # Check YouTube container (ID 102)
        try:
            youtube_container = results_window.getControl(102)
            youtube_count = youtube_container.size()
            xbmc.log('[Search Results Debug] YouTube Container (102) - Items: %d' % youtube_count, xbmc.LOGINFO)
            
            if youtube_count > 0:
                # Log first few items
                for i in range(min(3, youtube_count)):
                    item = youtube_container.getListItem(i)
                    xbmc.log('[Search Results Debug]   Item %d: %s' % (i, item.getLabel()), xbmc.LOGINFO)
        except Exception as e:
            xbmc.log('[Search Results Debug] YouTube Container (102) - Error: %s' % str(e), xbmc.LOGERROR)
        
        # If any container has items, we can stop checking
        if movies_count > 0 or series_count > 0 or youtube_count > 0:
            xbmc.log('[Search Results Debug] Results found! Stopping checks.', xbmc.LOGINFO)
            break
    
    xbmc.log('[Search Results Debug] ==========================================', xbmc.LOGINFO)
    
except Exception as e:
    xbmc.log('[Search Results Debug] General Error: %s' % str(e), xbmc.LOGERROR)
    import traceback
    xbmc.log('[Search Results Debug] Traceback: %s' % traceback.format_exc(), xbmc.LOGERROR)
