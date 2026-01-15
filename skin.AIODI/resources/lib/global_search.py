import xbmc
import xbmcgui
import sys
try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

try:
    # Get the current active window dialog ID
    current_dialog_id = xbmcgui.getCurrentWindowDialogId()
    xbmc.log('[Global Search] Current dialog ID: %s' % current_dialog_id, xbmc.LOGINFO)
    
    # Try to get the window
    dialog = None
    try:
        dialog = xbmcgui.Window(current_dialog_id)
    except:
        pass
    
    # Get the search query from arguments, the edit control, or keyboard
    search_query = None
    if len(sys.argv) > 1:
        search_query = sys.argv[1]
        xbmc.log('[Global Search] Query provided via argument: %s' % search_query, xbmc.LOGINFO)
        # Populate the edit control so the user sees it if the dialog is open
        if current_dialog_id == 1106:
            try:
                edit_control = dialog.getControl(9000)
                edit_control.setText(search_query)
            except:
                pass
    elif current_dialog_id == 1106:
        # Get the search query from the edit control in the search dialog
        try:
            edit_control = dialog.getControl(9000)
            search_query = edit_control.getText()
        except:
            pass
    
    # If no query yet, open keyboard
    if not search_query:
        keyboard = xbmc.Keyboard('', 'Global Search')
        keyboard.doModal()
        if keyboard.isConfirmed():
            search_query = keyboard.getText()
    
    xbmc.log('[Global Search] Final Search query: %s' % search_query, xbmc.LOGINFO)
    
    if search_query:
        # Construct encoded URLs
        encoded_query = quote_plus(search_query)
        movie_url = 'plugin://plugin.video.aiostreams/?action=search&content_type=movie&query=%s' % encoded_query
        series_url = 'plugin://plugin.video.aiostreams/?action=search&content_type=series&query=%s' % encoded_query
        youtube_url = 'plugin://plugin.video.youtube/kodion/search/query/?q=%s' % encoded_query
        
        # Set properties on home window
        home_window = xbmcgui.Window(10000)
        home_window.setProperty('GlobalSearch.Query', search_query)
        # Default to movies tab if not set or verify active tab
        home_window.setProperty('GlobalSearch.ActiveTab', 'movies')
        home_window.setProperty('GlobalSearch.MoviesURL', movie_url)
        home_window.setProperty('GlobalSearch.SeriesURL', series_url)
        home_window.setProperty('GlobalSearch.YouTubeURL', youtube_url)
        
        # Log the properties
        xbmc.log('[Global Search] Construction Complete:', xbmc.LOGINFO)
        xbmc.log('[Global Search] Movies URL: %s' % movie_url, xbmc.LOGINFO)
        xbmc.log('[Global Search] Series URL: %s' % series_url, xbmc.LOGINFO)
        
        # Close search dialog if open and open results
        if current_dialog_id == 1106:
            xbmc.executebuiltin('Dialog.Close(1106)')
            
        xbmc.executebuiltin('ActivateWindow(1112)')
    else:
        # Only notify if we were expecting an argument or valid input; 
        # canceling keyboard is a valid "do nothing" action.
        if len(sys.argv) > 1:
             xbmcgui.Dialog().notification('Search', 'Please enter a search term', xbmcgui.NOTIFICATION_WARNING, 2000)
except Exception as e:
    xbmc.log('[Global Search] Error: %s' % str(e), xbmc.LOGERROR)
    xbmcgui.Dialog().notification('Search Error', str(e), xbmcgui.NOTIFICATION_ERROR, 3000)
