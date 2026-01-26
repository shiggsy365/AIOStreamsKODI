# -*- coding: utf-8 -*-
"""Settings helper functions for AIOStreams addon"""
import xbmcaddon
from . import constants

ADDON = xbmcaddon.Addon()


def get_setting(setting_id, default=None):
    """Get addon setting with default fallback."""
    value = ADDON.getSetting(setting_id)
    return value if value else default


def get_bool_setting(setting_id, default=False):
    """Get boolean setting."""
    value = ADDON.getSetting(setting_id)
    if value == '':
        return default
    return value.lower() == 'true'


def get_int_setting(setting_id, default=0):
    """Get integer setting."""
    try:
        return int(ADDON.getSetting(setting_id))
    except (ValueError, TypeError):
        return default


def get_float_setting(setting_id, default=0.0):
    """Get float setting."""
    try:
        return float(ADDON.getSetting(setting_id))
    except (ValueError, TypeError):
        return default


def set_setting(setting_id, value):
    """Set addon setting."""
    ADDON.setSetting(setting_id, str(value))


# Playback settings
def get_default_behavior():
    """Get default playback behavior."""
    return get_setting('default_behavior', 'show_streams')


def get_fallback_behavior():
    """Get fallback behavior on stream failure."""
    return get_setting('fallback_behavior', 'show_streams')


def get_min_quality():
    """Get minimum quality setting."""
    return get_setting('min_quality', constants.DEFAULT_MIN_QUALITY)


def get_filter_low_quality():
    """Check if low quality streams should be filtered."""
    return get_bool_setting('filter_low_quality', False)


# Resume settings
def get_auto_resume():
    """Check if auto-resume is enabled."""
    return get_bool_setting('auto_resume', constants.DEFAULT_AUTO_RESUME)


def get_resume_threshold():
    """Get percentage threshold for marking as watched."""
    return get_int_setting('auto_mark_watched_percent', constants.DEFAULT_RESUME_THRESHOLD)


# Advanced settings
def get_stream_timeout():
    """Get stream test timeout."""
    return get_int_setting('stream_test_timeout', constants.DEFAULT_STREAM_TIMEOUT)


def get_show_progress_bars():
    """Check if progress bars should be shown."""
    return get_bool_setting('show_progress_bars', constants.DEFAULT_SHOW_PROGRESS_BARS)


def get_show_quality_badges():
    """Check if quality badges should be shown."""
    return get_bool_setting('show_quality_badges', True)


def get_cache_expiry_hours():
    """Get cache expiry in hours."""
    return get_int_setting('cache_expiry_hours', 24)


def get_max_streams():
    """Get maximum streams to display."""
    return get_int_setting('max_streams_to_show', 20)


def get_debug_logging():
    """Check if debug logging is enabled."""
    return get_bool_setting('debug_logging', False)


# Profile settings
def get_current_profile():
    """Get current Kodi profile name."""
    import xbmc
    return xbmc.getInfoLabel('System.ProfileName')


def get_profile_setting(setting_id, default=None):
    """Get profile-specific setting."""
    profile = get_current_profile()
    profile_key = f"{setting_id}_{profile}"
    value = get_setting(profile_key, None)
    if value is None:
        # Fallback to global setting
        return get_setting(setting_id, default)
    return value


def set_profile_setting(setting_id, value):
    """Set profile-specific setting."""
    profile = get_current_profile()
    profile_key = f"{setting_id}_{profile}"
    set_setting(profile_key, value)
