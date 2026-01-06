"""
Custom source select window for AIOStreams.
Programmatic dialog that works with all skins.
"""

import xbmc
import xbmcgui
from resources.lib.formatters import get_formatter_from_settings


class SourceSelect(xbmcgui.WindowDialog):
    """
    Custom dialog window for stream selection.
    Creates controls programmatically - works with ALL skins.
    """

    # Control IDs
    CONTROL_BACKGROUND = 1001
    CONTROL_TITLE = 1002
    CONTROL_LIST = 2000
    CONTROL_INSTRUCTIONS = 1003

    def __init__(self, **kwargs):
        """
        Initialize the source select window.

        Args:
            streams: List of stream dictionaries
            metadata: Dict with title, fanart, clearlogo
        """
        super(SourceSelect, self).__init__()

        self.streams = kwargs.get('streams', [])
        self.metadata = kwargs.get('metadata', {})
        self.selected_index = None
        self.formatter = get_formatter_from_settings()

        xbmc.log(f'[AIOStreams] SourceSelect initialized with {len(self.streams)} streams', xbmc.LOGDEBUG)

        # Create controls
        self._create_controls()

    def _create_controls(self):
        """Create all dialog controls programmatically."""
        try:
            # Get screen dimensions
            screen_width = 1920
            screen_height = 1080

            # Dialog dimensions (centered, 80% of screen)
            dialog_width = int(screen_width * 0.8)
            dialog_height = int(screen_height * 0.8)
            dialog_x = int((screen_width - dialog_width) / 2)
            dialog_y = int((screen_height - dialog_height) / 2)

            # Background (semi-transparent black)
            self.background = xbmcgui.ControlImage(
                dialog_x, dialog_y, dialog_width, dialog_height,
                '', colorDiffuse='DD000000'
            )
            self.addControl(self.background)

            # Title label
            title = self.metadata.get('title', 'Select Stream')
            title_height = 60
            self.title_label = xbmcgui.ControlLabel(
                dialog_x + 40, dialog_y + 20, dialog_width - 80, title_height,
                title, font='font30', textColor='0xFFFFFFFF', alignment=0x00000006  # Center
            )
            self.addControl(self.title_label)

            # Stream count label
            stream_count_text = f'{len(self.streams)} streams available'
            self.count_label = xbmcgui.ControlLabel(
                dialog_x + 40, dialog_y + title_height + 20, dialog_width - 80, 30,
                stream_count_text, font='font12', textColor='0x88FFFFFF'
            )
            self.addControl(self.count_label)

            # List control for streams
            list_y = dialog_y + title_height + 70
            list_height = dialog_height - title_height - 140
            self.list_control = xbmcgui.ControlList(
                dialog_x + 40, list_y, dialog_width - 80, list_height,
                font='font13', textColor='0xFFFFFFFF',
                buttonTexture='', buttonFocusTexture='',
                selectedColor='0xFF1E90FF',
                imageWidth=20, imageHeight=20, itemTextXOffset=10,
                alignmentY=0x00000004, space=2
            )
            self.addControl(self.list_control)

            # Populate the list with formatted stream names
            for idx, stream in enumerate(self.streams):
                stream_name = stream.get('name', stream.get('title', ''))

                # Format the stream name using selected formatter
                try:
                    formatted_name = self.formatter.format(stream_name)
                except Exception as e:
                    xbmc.log(f'[AIOStreams] Error formatting stream: {e}', xbmc.LOGWARNING)
                    formatted_name = stream_name

                # Create list item
                list_item = xbmcgui.ListItem(label=formatted_name)
                self.list_control.addItem(list_item)

            # Instructions label at bottom
            instructions = 'Select a stream to play | Press Back to cancel'
            self.instructions_label = xbmcgui.ControlLabel(
                dialog_x + 40, dialog_y + dialog_height - 50, dialog_width - 80, 40,
                instructions, font='font12', textColor='0x88FFFFFF', alignment=0x00000006  # Center
            )
            self.addControl(self.instructions_label)

            # Set focus to the list
            self.setFocus(self.list_control)

            xbmc.log(f'[AIOStreams] Controls created, list populated with {len(self.streams)} items', xbmc.LOGDEBUG)

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error creating controls: {e}', xbmc.LOGERROR)
            import traceback
            xbmc.log(f'[AIOStreams] Traceback: {traceback.format_exc()}', xbmc.LOGERROR)

    def onControl(self, control):
        """
        Handle control activation (Enter/Select pressed).

        Args:
            control: Control that was activated
        """
        if control == self.list_control:
            # Get selected position
            try:
                self.selected_index = self.list_control.getSelectedPosition()
                xbmc.log(f'[AIOStreams] Stream selected: index {self.selected_index}', xbmc.LOGDEBUG)
                self.close()
            except Exception as e:
                xbmc.log(f'[AIOStreams] Error getting selected item: {e}', xbmc.LOGERROR)
    
    def onAction(self, action):
        """
        Handle action events.
        
        Args:
            action: Action that was performed
        """
        # Close dialog on back/escape
        if action.getId() in (xbmcgui.ACTION_NAV_BACK, 
                              xbmcgui.ACTION_PREVIOUS_MENU,
                              xbmcgui.ACTION_STOP):
            xbmc.log('[AIOStreams] Source select cancelled by user', xbmc.LOGDEBUG)
            self.selected_index = None
            self.close()
