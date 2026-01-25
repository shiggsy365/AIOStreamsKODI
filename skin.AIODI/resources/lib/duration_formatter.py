#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Duration formatter for AIODI skin.
Removes non-numeric characters except colons from duration strings.
"""

import xbmc
import xbmcgui
import re


def format_duration(duration_str):
    """
    Clean duration string to only contain numbers and colons.

    Args:
        duration_str: Duration string from Kodi (e.g., "120 min", "1:45:00")

    Returns:
        Cleaned duration string with only numbers and colons
    """
    if not duration_str:
        return ''

    # Remove everything except digits and colons
    cleaned = re.sub(r'[^\d:]', '', duration_str)

    return cleaned


def set_duration_property():
    """Get duration from active widget and set cleaned property."""
    try:
        # Get the active widget ID
        active_widget = xbmc.getInfoLabel('Skin.String(ActiveWidgetID)')
        if not active_widget:
            return

        # Get duration from the focused item
        duration = xbmc.getInfoLabel(f'Container({active_widget}).ListItem.Duration')

        # Clean the duration
        cleaned_duration = format_duration(duration)

        # Set the property
        win = xbmcgui.Window(10000)
        win.setProperty('Widget.CleanDuration', cleaned_duration)

    except Exception as e:
        xbmc.log(f'AIODI Duration Formatter Error: {str(e)}', xbmc.LOGERROR)


if __name__ == '__main__':
    set_duration_property()
