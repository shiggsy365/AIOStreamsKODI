# -*- coding: utf-8 -*-
"""
Multi-line source selection dialog with emoji support.

Uses custom XML skin that renders multi-line content with proper
line break handling and emoji display (when emoji fonts are available).
"""
import os
import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs


# Control IDs matching the XML skin
CONTROL_STREAM_LIST = 5000
CONTROL_SCROLLBAR = 5001

# Simple ASCII symbol mappings - using only standard ASCII characters
# All replacements are wrapped in red color tags for visibility
UNICODE_SYMBOLS = {
    # Status indicators
    '🔒': '[COLOR red]+[/COLOR]',              # Proxied
    '🔓': '[COLOR red]-[/COLOR]',              # Not proxied
    '⚡': '[COLOR red]*[/COLOR]',              # Cached
    '❌': '[COLOR red]x[/COLOR]',              # Uncached
    '⏳': '[COLOR red]-[/COLOR]',              # Uncached

    # Video/Media
    '🎥': '[COLOR red]>[/COLOR]',              # Video type -> play arrow
    '🎞️': '[COLOR red]#[/COLOR]',             # Video format -> hash
    '🎞': '[COLOR red]#[/COLOR]',              # Video format (no variation selector)
    '📺': '[COLOR red]=[/COLOR]',              # Video encoding -> equals

    # Audio
    '🎧': '[COLOR red]~[/COLOR]',              # Audio stream -> tilde
    '🔊': '[COLOR red]~~[/COLOR]',             # Audio channels -> double tilde

    # File info
    '📦': '[COLOR red]@[/COLOR]',              # File size -> at sign
    '💾': '[COLOR red]@[/COLOR]',              # File size (alt)

    # Stats & metadata
    '⏱️': '[COLOR red]T[/COLOR]',             # Duration -> T
    '⏱': '[COLOR red]T[/COLOR]',              # Duration (no variation selector)
    '👥': '[COLOR red]^[/COLOR]',              # Seeders -> caret
    '🌱': '[COLOR red]^[/COLOR]',              # Seeders (alt)
    '👤': '[COLOR red]^[/COLOR]',              # Seeders (alt)
    '📅': '[COLOR red]D[/COLOR]',              # Age -> D
    '🔍': '[COLOR red]o[/COLOR]',              # Release group -> lowercase o
    '📡': '[COLOR red]o[/COLOR]',              # Release group (alt)
    '⚙️': '[COLOR red]o[/COLOR]',             # Release group (alt)
    '⚙': '[COLOR red]o[/COLOR]',              # Release group (no variation selector)

    # Identifiers
    '🏷️': '[COLOR red]:[/COLOR]',             # Label -> colon
    '🏷': '[COLOR red]:[/COLOR]',              # Label (no variation selector)
    '🌎': '[COLOR red]L[/COLOR]',              # Language -> L
    '🌐': '[COLOR red]L[/COLOR]',              # Language (alt)
    '🗣️': '[COLOR red]L[/COLOR]',             # Language (alt)
    '🗣': '[COLOR red]L[/COLOR]',              # Language (no variation selector)

    # Actions
    '🔥': '[COLOR red]![/COLOR]',              # Remove -> exclamation
    '☁️': '[COLOR red]C[/COLOR]',             # Library -> C
    '☁': '[COLOR red]C[/COLOR]',              # Library (no variation selector)
    '📌': '[COLOR red]P[/COLOR]',              # Library (alt) -> P

    # Info
    '📁': '[COLOR red]>[/COLOR]',              # Filename -> right arrow
    '🎬': '[COLOR red]>[/COLOR]',              # Filename (alt)
    'ℹ️': '[COLOR red]i[/COLOR]',             # Message -> i
    'ℹ': '[COLOR red]i[/COLOR]',              # Message (no variation selector)

    # Common emoji variants
    '🕵️': '[COLOR red]+[/COLOR]',             # Proxied detective
    '🕵': '[COLOR red]+[/COLOR]',              # Proxied detective (no variation selector)
}

# No need for EMOJI_TO_PIPE or EMOJI_TO_REMOVE - catch-all handles the rest

import re

def replace_emojis(text):
    """Replace emojis with Unicode symbols for better compatibility."""
    if not text:
        return text

    # Apply specific Unicode symbol replacements first
    for emoji, symbol in UNICODE_SYMBOLS.items():
        text = text.replace(emoji, symbol)

    # Replace any remaining unmapped emojis with red star (catch-all)
    # This regex matches most emoji characters including flags
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F700-\U0001F77F"  # alchemical symbols
        "\U0001F780-\U0001F7FF"  # geometric shapes
        "\U0001F800-\U0001F8FF"  # supplemental arrows
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # chess symbols
        "\U0001FA70-\U0001FAFF"  # symbols extended
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed characters
        "\U0001F1E0-\U0001F1FF"  # flags (regional indicators)
        "\uFE0F"                  # variation selector
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub('[COLOR red]*[/COLOR]', text)  # Red star for unmapped emojis

    # Clean up any double spaces that might result
    while '  ' in text:
        text = text.replace('  ', ' ')

    # Preserve line breaks (\n) - don't strip them from lines
    # Only strip leading/trailing whitespace from each line
    lines = text.split('\n')
    lines = [line.strip() for line in lines]
    text = '\n'.join(lines)

    return text.strip()


class MultiLineSourceSelect(xbmcgui.WindowXML):
    """
    Custom dialog for stream selection with multi-line support.

    Displays streams with full content from formatters, including:
    - Emojis (when system/bundled fonts support them)
    - Multi-line descriptions (1-10 lines per stream)
    - Proper line break rendering

    Usage:
        dialog = MultiLineSourceSelect(
            'aiostreams-source-select.xml',
            addon_path,
            'Default',
            '1080i',
            streams=streams_list,
            title='Movie Title (2023)',
            fanart='path/to/fanart.jpg',
            clearlogo='path/to/logo.png'
        )
        dialog.doModal()
        selected = dialog.get_selected_index()
        del dialog
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the source select dialog.

        Kwargs:
            streams: List of stream dictionaries
            title: Media title to display
            fanart: Optional fanart image path
            clearlogo: Optional clearlogo image path
        """
        self.streams = kwargs.pop('streams', [])
        self.title = kwargs.pop('title', 'Select Stream')
        self.fanart = kwargs.pop('fanart', '')
        self.clearlogo = kwargs.pop('clearlogo', '')

        self.selected_index = -1
        self._list_control = None

        xbmc.log(f'[AIOStreams] MultiLineSourceSelect init with {len(self.streams)} streams', xbmc.LOGDEBUG)

    def onInit(self):
        """Called when dialog is initialized. Set up controls and populate list."""
        try:
            # Set window properties for the skin
            self.setProperty('title', self.title)
            self.setProperty('stream_count', str(len(self.streams)))

            if self.fanart:
                self.setProperty('fanart', self.fanart)
            if self.clearlogo:
                self.setProperty('clearlogo', self.clearlogo)

            # Get list control
            self._list_control = self.getControl(CONTROL_STREAM_LIST)

            if self._list_control:
                self._populate_list()
                self.setFocusId(CONTROL_STREAM_LIST)
            else:
                xbmc.log('[AIOStreams] Could not find stream list control', xbmc.LOGERROR)

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error in onInit: {e}', xbmc.LOGERROR)

    def _populate_list(self):
        """Populate the list control with formatted streams."""
        try:
            self._list_control.reset()

            for idx, stream in enumerate(self.streams):
                # Get stream name and description
                name = stream.get('name', stream.get('title', ''))
                description = stream.get('description', '')

                # Replace emojis with text equivalents for compatibility
                name = replace_emojis(name)
                description = replace_emojis(description)

                # Build multi-line label
                # The XML textbox will render \n as line breaks
                if description:
                    # Combine name and description with line break
                    full_label = f"{name}\n{description}"
                else:
                    full_label = name

                # Create list item
                list_item = xbmcgui.ListItem(label=full_label)

                # Store original index for retrieval
                list_item.setProperty('stream_index', str(idx))

                # Add any additional properties the skin might want
                list_item.setProperty('stream_name', name)
                if description:
                    list_item.setProperty('stream_description', description)

                self._list_control.addItem(list_item)

            xbmc.log(f'[AIOStreams] Populated list with {len(self.streams)} items', xbmc.LOGDEBUG)

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error populating list: {e}', xbmc.LOGERROR)

    def onClick(self, control_id):
        """Handle click events."""
        if control_id == CONTROL_STREAM_LIST:
            try:
                selected_item = self._list_control.getSelectedItem()
                if selected_item:
                    self.selected_index = int(selected_item.getProperty('stream_index'))
                    xbmc.log(f'[AIOStreams] Stream selected: index {self.selected_index}', xbmc.LOGDEBUG)
                    self.close()
            except Exception as e:
                xbmc.log(f'[AIOStreams] Error getting selection: {e}', xbmc.LOGERROR)

    def onAction(self, action):
        """Handle action events."""
        action_id = action.getId()

        # Back/Escape actions
        if action_id in (xbmcgui.ACTION_NAV_BACK,
                         xbmcgui.ACTION_PREVIOUS_MENU,
                         xbmcgui.ACTION_STOP,
                         92):  # BACKSPACE
            xbmc.log('[AIOStreams] Source select cancelled by user', xbmc.LOGDEBUG)
            self.selected_index = -1
            self.close()

        # Select action (Enter/OK)
        elif action_id in (xbmcgui.ACTION_SELECT_ITEM,
                           xbmcgui.ACTION_MOUSE_LEFT_CLICK,
                           7):  # ENTER
            self.onClick(self.getFocusId())

    def get_selected_index(self):
        """
        Get the index of the selected stream.

        Returns:
            int: Index of selected stream, or -1 if cancelled
        """
        return self.selected_index

    def get_selected_stream(self):
        """
        Get the selected stream dictionary.

        Returns:
            dict: Selected stream data, or None if cancelled
        """
        if 0 <= self.selected_index < len(self.streams):
            return self.streams[self.selected_index]
        return None


def show_source_select_dialog(streams, title='Select Stream', fanart='', clearlogo=''):
    """
    Convenience function to show the multi-line source select dialog.

    Args:
        streams: List of stream dictionaries with 'name' and 'description' keys
        title: Media title to display in header
        fanart: Optional fanart image path
        clearlogo: Optional clearlogo image path

    Returns:
        tuple: (selected_index, selected_stream) or (-1, None) if cancelled
    """
    addon = xbmcaddon.Addon()
    addon_path = xbmcvfs.translatePath(addon.getAddonInfo('path'))

    dialog = MultiLineSourceSelect(
        'aiostreams-source-select.xml',
        addon_path,
        'Default',
        '1080i',
        streams=streams,
        title=title,
        fanart=fanart,
        clearlogo=clearlogo
    )

    dialog.doModal()
    selected_index = dialog.get_selected_index()
    selected_stream = dialog.get_selected_stream()
    del dialog

    return selected_index, selected_stream


# Alternative: Programmatic dialog for systems where XML skins don't work
class ProgrammaticMultiLineSelect(xbmcgui.WindowDialog):
    """
    Fallback programmatic dialog for multi-line stream selection.

    Used when XML skins aren't available or fail to load.
    Creates all controls via Python code.
    """

    def __init__(self, **kwargs):
        super().__init__()

        self.streams = kwargs.get('streams', [])
        self.title = kwargs.get('title', 'Select Stream')
        self.selected_index = -1

        self._create_controls()

    def _create_controls(self):
        """Create dialog controls programmatically."""
        # Screen dimensions (1080p reference)
        sw, sh = 1920, 1080

        # Dialog dimensions
        dw, dh = int(sw * 0.85), int(sh * 0.9)
        dx, dy = (sw - dw) // 2, (sh - dh) // 2

        # Background
        self.addControl(xbmcgui.ControlImage(
            dx, dy, dw, dh, '', colorDiffuse='F0101020'
        ))

        # Title
        self.title_label = xbmcgui.ControlLabel(
            dx + 30, dy + 15, dw - 60, 50,
            self.title, font='font30', textColor='FFFFFFFF'
        )
        self.addControl(self.title_label)

        # Stream count
        self.count_label = xbmcgui.ControlLabel(
            dx + 30, dy + 60, dw - 60, 30,
            f'{len(self.streams)} streams', font='font12', textColor='88FFFFFF'
        )
        self.addControl(self.count_label)

        # Create list control
        list_y = dy + 100
        list_h = dh - 160

        self.list_control = xbmcgui.ControlList(
            dx + 30, list_y, dw - 60, list_h,
            font='font13', textColor='FFFFFFFF',
            selectedColor='FF00AAFF',
            itemHeight=180,  # Tall items for multi-line content
            space=8
        )
        self.addControl(self.list_control)

        # Populate list
        for stream in self.streams:
            name = stream.get('name', stream.get('title', ''))
            description = stream.get('description', '')

            # Build display text
            if description:
                label = f"{name}\n{description}"
            else:
                label = name

            # ListItem handles newlines in some Kodi versions
            item = xbmcgui.ListItem(label=label)
            self.list_control.addItem(item)

        # Instructions
        self.help_label = xbmcgui.ControlLabel(
            dx + 30, dy + dh - 45, dw - 60, 30,
            'Select stream | Back to cancel', font='font12',
            textColor='66FFFFFF', alignment=0x00000002
        )
        self.addControl(self.help_label)

        self.setFocus(self.list_control)

    def onControl(self, control):
        if control == self.list_control:
            self.selected_index = self.list_control.getSelectedPosition()
            self.close()

    def onAction(self, action):
        if action.getId() in (xbmcgui.ACTION_NAV_BACK, xbmcgui.ACTION_PREVIOUS_MENU):
            self.selected_index = -1
            self.close()

    def get_selected_index(self):
        return self.selected_index
