import xbmc
import xbmcgui
import xbmcaddon
import os

ADDON = xbmcaddon.Addon()
ADDON_PATH = ADDON.getAddonInfo('path')

class OnboardingWindow(xbmcgui.WindowXMLDialog):
    def __init__(self, *args, **kwargs):
        super(OnboardingWindow, self).__init__(*args, **kwargs)
        self.confirmed = False

    def onInit(self):
        pass
        
    def onClick(self, controlId):
        if controlId == 9000: # Install Selected
            xbmcgui.Dialog().ok("AIODI Onboarding", "Installation logic will be implemented in the next step.")
            self.confirmed = True
            self.close()

    def onAction(self, action):
        if action.getId() in [xbmcgui.ACTION_PREVIOUS_MENU, xbmcgui.ACTION_NAV_BACK]:
            self.close()

def run():
    # Use WindowXMLDialog to load our custom UI
    # Parameters: xmlFilename, scriptPath, defaultSkin, defaultRes
    ui = OnboardingWindow('onboarding.xml', ADDON_PATH, 'Default', '1080i')
    ui.doModal()
    del ui

if __name__ == '__main__':
    run()
