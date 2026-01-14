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


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'[AIOStreams] [InfoWindowHelper] {msg}', level)


def populate_cast_properties():
    """
    Query database directly for cast data using current ListItem's IMDb ID.
    """
    try:
        log('Starting cast property population')
        
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
        
        # Try to extract from Filenameandpath if it contains imdb_id parameter
        if not imdb_id:
            path = xbmc.getInfoLabel('ListItem.Filenameandpath')
            if 'imdb_id=' in path:
                import re
                match = re.search(r'imdb_id=([^&]+)', path)
                if match:
                    imdb_id = match.group(1)
                    log(f'Extracted IMDb ID from Filenameandpath: {imdb_id}')
        
        content_type = xbmc.getInfoLabel('ListItem.DBType')  # 'movie' or 'tvshow'
        
        if not imdb_id:
            log(f'No IMDb ID found for current item. Tried: IMDBNumber, Property(imdb_id), UniqueID(imdb), Path extraction', xbmc.LOGWARNING)
            return
        
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
        
        # Fetch cast from API
        try:
            cast_list = fetch_cast_from_api(imdb_id, content_type)
            
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
                        log(f'Set cast {i}: {name} as {role}')
                
                log(f'Cast properties populated successfully: {len(cast_list)} members')
            else:
                log(f'No cast data returned from API for {imdb_id}', xbmc.LOGWARNING)
        except Exception as e:
            log(f'Error fetching cast from API: {e}', xbmc.LOGERROR)
            import traceback
            log(traceback.format_exc(), xbmc.LOGERROR)
        
    except Exception as e:
        log(f'Error populating cast properties: {e}', xbmc.LOGERROR)
        import traceback
        log(traceback.format_exc(), xbmc.LOGERROR)


if __name__ == '__main__':
    populate_cast_properties()
