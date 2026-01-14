"""
Helper script for custom information window.
Copies cast properties from plugin to info window namespace.
"""
import xbmc
import xbmcgui


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f'[AIOStreams] [InfoWindowHelper] {msg}', level)


def populate_cast_properties():
    """
    Copy cast properties from AIOStreams namespace to InfoWindow namespace.
    Set on both home window and dialog window for maximum compatibility.
    """
    try:
        log('Starting cast property population')
        
        # Get both windows
        home_window = xbmcgui.Window(10000)
        
        # Copy cast properties from AIOStreams to InfoWindow namespace
        cast_found = False
        for i in range(1, 6):
            name = home_window.getProperty(f'AIOStreams.Cast.{i}.Name')
            role = home_window.getProperty(f'AIOStreams.Cast.{i}.Role')
            thumb = home_window.getProperty(f'AIOStreams.Cast.{i}.Thumb')
            
            if name:
                # Set on home window so XML can access with simple Window.Property()
                home_window.setProperty(f'InfoWindow.Cast.{i}.Name', name)
                home_window.setProperty(f'InfoWindow.Cast.{i}.Role', role)
                home_window.setProperty(f'InfoWindow.Cast.{i}.Thumb', thumb)
                log(f'Set cast {i}: {name} as {role}')
                cast_found = True
            else:
                home_window.clearProperty(f'InfoWindow.Cast.{i}.Name')
                home_window.clearProperty(f'InfoWindow.Cast.{i}.Role')
                home_window.clearProperty(f'InfoWindow.Cast.{i}.Thumb')
        
        if cast_found:
            log('Cast properties populated successfully')
        else:
            log('No cast properties found in AIOStreams namespace', xbmc.LOGWARNING)
        
    except Exception as e:
        log(f'Error populating cast properties: {e}', xbmc.LOGERROR)
        import traceback
        log(traceback.format_exc(), xbmc.LOGERROR)


if __name__ == '__main__':
    populate_cast_properties()
