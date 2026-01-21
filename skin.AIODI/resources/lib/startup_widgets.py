import xbmc
import xbmcgui
import xbmcvfs
import json
import os

# Use the plugin's data directory where widget_config.json is stored
ADDON_DATA_DIR = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.aiostreams/')
CONFIG_FILE = os.path.join(ADDON_DATA_DIR, 'widget_config.json')

def load_and_apply():
    # Use Window property as a session-level guard to prevent concurrent/redundant execution
    win = xbmcgui.Window(10000)
    if win.getProperty('AIOStreams.StartupWidgetsEnsured') == 'true':
        return

    if not os.path.exists(CONFIG_FILE):
        xbmc.log('[AIODI] Startup: Widget config not found.', xbmc.LOGDEBUG)
        win.setProperty('AIOStreams.StartupWidgetsEnsured', 'true')
        return

    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except Exception as e:
        xbmc.log(f'[AIODI] Startup: Error loading widget config: {e}', xbmc.LOGERROR)
        return

    # Property formats matching Home.xml and widget_manager.py
    page_properties = {
        'home': 'WidgetLabel_Home_{}',
        'movies': 'movie_catalog_{}_name',
        'tvshows': 'series_catalog_{}_name'
    }

    xbmc.log('[AIODI] Startup: Applying widget headers...', xbmc.LOGDEBUG)

    for page, fmt in page_properties.items():
        widgets = config.get(page, [])
        for i, widget in enumerate(widgets):
            label = widget.get('label', '')
            prop_name = fmt.format(i)
            # Set the header property
            win.setProperty(prop_name, label)
            # Set the old-style property for compatibility
            win.setProperty(f'{page}_widget_{i}_name', label)
            xbmc.log(f'[AIODI] Startup: Catalog {i} for {page} is "{label}" (Property: {prop_name})', xbmc.LOGINFO)
        
        # Clear any remaining properties to prevent ghost headers from old configs
        for j in range(len(widgets), 20):
            win.clearProperty(fmt.format(j))
            win.clearProperty(f'{page}_widget_{j}_name')

        # Set count properties for skin optimization using persistent Skin strings and Window Properties
        count_prop = f'AIOStreams.{page.capitalize()}_Widget_Count'
        if page == 'tvshows':
            count_prop = 'AIOStreams.TV_Widget_Count'
        xbmc.executebuiltin(f'Skin.SetString({count_prop},{len(widgets)})')
        win.setProperty(count_prop, str(len(widgets)))
        xbmc.log(f'[AIODI] Startup: {len(widgets)} catalogs recognised for {page}', xbmc.LOGINFO)
        xbmc.log(f'[AIODI] Startup: Set Skin.String({count_prop}) and Window.Property({count_prop}) = {len(widgets)}', xbmc.LOGDEBUG)
    
    # Mark as ensured
    win.setProperty('AIOStreams.StartupWidgetsEnsured', 'true')

    # Trigger widget content reload by updating the token
    import time
    token = str(int(time.time()))
    xbmc.executebuiltin(f'Skin.SetString(WidgetReloadToken,{token})')
    xbmc.log(f'[AIODI] Startup: Set WidgetReloadToken = {token}', xbmc.LOGDEBUG)

if __name__ == '__main__':
    load_and_apply()

