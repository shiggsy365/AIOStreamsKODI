import xbmc
import time

# Dummy service to force Kodi to check for dependencies on startup
if __name__ == '__main__':
    monitor = xbmc.Monitor()
    xbmc.log("[Onboarding] Service started to monitor dependencies", xbmc.LOGINFO)
    
    # Stay alive until Kodi shuts down
    while not monitor.abortRequested():
        if monitor.waitForAbort(10):
            break
            
    xbmc.log("[Onboarding] Service stopped", xbmc.LOGINFO)
