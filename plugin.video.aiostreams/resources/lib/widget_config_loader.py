"""
Widget Configuration Loader for AIOStreams

Handles loading and managing widget configurations from widget_config.json
"""
import xbmc
import xbmcgui
import xbmcvfs
import json
import os


def log(msg, level=xbmc.LOGDEBUG):
    """Log message with AIOStreams prefix"""
    xbmc.log(f'[AIOStreams] [WidgetConfigLoader] {msg}', level)


def get_config_file_path():
    """Get the path to the widget config file"""
    addon_data_dir = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.aiostreams/')
    return os.path.join(addon_data_dir, 'widget_config.json')


def get_default_config():
    """
    Get default widget configuration for all users.
    Starts empty - users must add widgets via Widget Manager.
    
    Returns:
        dict: Empty configuration
    """
    return {
        'home': [],
        'tvshows': [],
        'movies': [],
        'version': 2
    }


def save_widget_config(config):
    """
    Save widget configuration to JSON file.
    
    Args:
        config: Configuration dict to save
    """
    config_file = get_config_file_path()
    try:
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        # Clear Hot Cache to force reload on next access
        xbmcgui.Window(10000).clearProperty('AIOStreams.WidgetConfig')
        log('Widget config saved successfully')
    except Exception as e:
        log(f'Error saving config: {e}', xbmc.LOGERROR)


def load_widget_config():
    """
    Load widget configuration from JSON file or Window Property cache.
    
    All users are forced to use default configuration on first load.
    Old configs (version < 2) are replaced with defaults.
    
    Returns:
        dict: Widget configuration
    """
    # Check "Hot Cache" (Window Property) first to avoid disk I/O
    win_home = xbmcgui.Window(10000)
    cached_config = win_home.getProperty('AIOStreams.WidgetConfig')
    if cached_config:
        try:
            config = json.loads(cached_config)
            # log('Loaded widget config from Hot Cache', xbmc.LOGDEBUG)
            return config
        except:
            pass

    config_file = get_config_file_path()
    default_config = get_default_config()
    
    # Check if config exists and has correct version
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                content = f.read()
                config = json.loads(content)
            
            # Check version - if old or missing, force reset to defaults
            if config.get('version') != 2:
                log('Old config version detected, resetting to defaults', xbmc.LOGINFO)
                save_widget_config(default_config)
                return default_config
            
            # Store in Window Property cache
            win_home.setProperty('AIOStreams.WidgetConfig', content)
            log(f'Loaded widget config: {len(config.get("home", []))} home, {len(config.get("tvshows", []))} tvshows, {len(config.get("movies", []))} movies widgets', xbmc.LOGDEBUG)
            return config
        except Exception as e:
            log(f'Error loading config: {e}, resetting to defaults', xbmc.LOGERROR)
            save_widget_config(default_config)
            return default_config
    
    # No config exists, create with defaults
    log('No config found, creating with defaults', xbmc.LOGINFO)
    save_widget_config(default_config)
    return default_config


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
