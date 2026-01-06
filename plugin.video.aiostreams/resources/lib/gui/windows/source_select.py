"""
Custom source select window for AIOStreams.
Emulates the Seren addon's source select screen.
"""

import xbmc
import xbmcgui
from resources.lib.formatters import get_formatter_from_settings


class SourceSelect(xbmcgui.WindowXMLDialog):
    """
    Custom dialog window for stream selection.
    Displays streams with fanart background and formatted names.
    """
    
    # Control IDs
    CONTROL_LIST = 2000
    
    def __init__(self, xml_file, resource_path, **kwargs):
        """
        Initialize the source select window.
        
        Args:
            xml_file: Name of the XML skin file
            resource_path: Path to the addon resources
            streams: List of stream dictionaries
            metadata: Dict with title, fanart, clearlogo
        """
        super(SourceSelect, self).__init__(xml_file, resource_path)
        
        self.streams = kwargs.get('streams', [])
        self.metadata = kwargs.get('metadata', {})
        self.selected_index = None
        self.formatter = get_formatter_from_settings()
        
        xbmc.log(f'[AIOStreams] SourceSelect initialized with {len(self.streams)} streams', xbmc.LOGDEBUG)
    
    def onInit(self):
        """Initialize the window and populate the stream list."""
        try:
            # Set window properties for metadata
            if self.metadata.get('fanart'):
                self.setProperty('item.art.fanart', self.metadata['fanart'])
            if self.metadata.get('clearlogo'):
                self.setProperty('item.art.clearlogo', self.metadata['clearlogo'])
            if self.metadata.get('title'):
                self.setProperty('item.info.title', self.metadata['title'])
            
            # Get the list control
            try:
                list_control = self.getControl(self.CONTROL_LIST)
            except:
                xbmc.log('[AIOStreams] Could not get list control', xbmc.LOGERROR)
                return
            
            # Clear any existing items
            list_control.reset()
            
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
                
                # Add to list
                list_control.addItem(list_item)
            
            # Set focus to the list
            self.setFocusId(self.CONTROL_LIST)
            
            xbmc.log(f'[AIOStreams] Stream list populated with {len(self.streams)} items', xbmc.LOGDEBUG)
            
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error in SourceSelect.onInit: {e}', xbmc.LOGERROR)
    
    def onClick(self, control_id):
        """
        Handle click events.
        
        Args:
            control_id: ID of the clicked control
        """
        if control_id == self.CONTROL_LIST:
            # Get selected position
            try:
                list_control = self.getControl(self.CONTROL_LIST)
                self.selected_index = list_control.getSelectedPosition()
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
