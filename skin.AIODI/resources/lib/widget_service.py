"""
Widget Configuration Service

Sets Window properties based on widget_config.json so the skin can display
dynamic widget names.
"""
import xbmc
import xbmcgui
import xbmcvfs
import json
import os
import time


def log(msg, level=xbmc.LOGDEBUG):
    """Log message with prefix"""
    xbmc.log(f'[AIODI] [WidgetService] {msg}', level)


def get_config_file_path():
    """Get the path to the widget config file"""
    addon_data_dir = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.aiostreams/')
    return os.path.join(addon_data_dir, 'widget_config.json')


def load_and_set_widget_properties():
    """Load widget config and set Window properties"""
    config_file = get_config_file_path()

    # Load config
    if not os.path.exists(config_file):
        log('Config file not found, using empty config', xbmc.LOGDEBUG)
        config = {'home': [], 'tvshows': [], 'movies': []}
    else:
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            log('Loaded widget config successfully')
        except Exception as e:
            log(f'Error loading config: {e}', xbmc.LOGERROR)
            config = {'home': [], 'tvshows': [], 'movies': []}

    # Set properties for each page in specific order: home, tvshows, movies
    window = xbmcgui.Window(10000)  # Home window

    # Load in specific order to ensure home loads first
    for page in ['home', 'tvshows', 'movies']:
        widgets = config.get(page, [])
        log(f'Setting {len(widgets)} widget properties for {page}')

        for index, widget in enumerate(widgets):
            label = widget.get('label', 'Unknown')
            # Set the property that the XML will reference
            property_name = f'{page}_widget_{index}_name'
            window.setProperty(property_name, label)
            log(f'  [{index}] {property_name} = {label}', xbmc.LOGDEBUG)


def monitor_config_changes(monitor):
    """Monitor for config file changes and reload properties"""
    config_file = get_config_file_path()
    last_modified = 0

    while not monitor.abortRequested():
        # Check if config file has been modified
        try:
            if os.path.exists(config_file):
                current_modified = os.path.getmtime(config_file)
                if current_modified != last_modified:
                    log('Config file changed, reloading widget properties')
                    load_and_set_widget_properties()
                    last_modified = current_modified
        except Exception as e:
            log(f'Error checking config file: {e}', xbmc.LOGERROR)

        # Wait for 5 seconds or until abort
        if monitor.waitForAbort(5):
            break


if __name__ == '__main__':
    log('Widget service started')

    # Initial load
    load_and_set_widget_properties()

    # Monitor for changes
    monitor = xbmc.Monitor()
    monitor_config_changes(monitor)

    log('Widget service stopped')
