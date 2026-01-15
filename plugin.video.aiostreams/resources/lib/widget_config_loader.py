"""
Widget Configuration Loader for AIOStreams

Handles loading and managing widget configurations from widget_config.json
"""
import xbmc
import xbmcvfs
import json
import os


def log(msg, level=xbmc.LOGINFO):
    """Log message with AIOStreams prefix"""
    xbmc.log(f'[AIOStreams] [WidgetConfigLoader] {msg}', level)


def get_config_file_path():
    """Get the path to the widget config file"""
    addon_data_dir = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.aiostreams/')
    return os.path.join(addon_data_dir, 'widget_config.json')


def load_widget_config():
    """Load widget configuration from JSON file"""
    config_file = get_config_file_path()

    if not os.path.exists(config_file):
        log(f'Config file not found at {config_file}, returning empty config', xbmc.LOGDEBUG)
        return {'home': [], 'tvshows': [], 'movies': []}

    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        log(f'Loaded widget config: {len(config.get("home", []))} home, {len(config.get("tvshows", []))} tvshows, {len(config.get("movies", []))} movies widgets')
        return config
    except Exception as e:
        log(f'Error loading config: {e}', xbmc.LOGERROR)
        return {'home': [], 'tvshows': [], 'movies': []}


def get_widget_at_index(page, index):
    """
    Get widget configuration at a specific index for a page

    Args:
        page: 'home', 'tvshows', or 'movies'
        index: Widget index (0, 1, 2, ...)

    Returns:
        Widget dict with 'label', 'path', 'type', 'is_trakt' or None if not found
    """
    config = load_widget_config()
    widgets = config.get(page, [])

    if index < 0 or index >= len(widgets):
        log(f'Widget index {index} out of range for page "{page}" (max: {len(widgets)-1})', xbmc.LOGDEBUG)
        return None

    widget = widgets[index]
    log(f'Retrieved widget {index} for {page}: {widget.get("label")}', xbmc.LOGDEBUG)
    return widget


def get_widget_count(page):
    """Get the number of configured widgets for a page"""
    config = load_widget_config()
    return len(config.get(page, []))
