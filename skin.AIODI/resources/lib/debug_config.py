import xbmc
import xbmcvfs
import os
import json

def log(msg):
    xbmc.log(f'[DEBUG_CONFIG] {msg}', xbmc.LOGINFO)

CONFIG_PATH = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.aiostreams/widget_config.json')
OUTPUT_PATH = xbmcvfs.translatePath('special://home/debug_widget_config.txt')

try:
    log(f"Reading config from: {CONFIG_PATH}")
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            content = f.read()
        
        log(f"Content length: {len(content)}")
        
        with open(OUTPUT_PATH, 'w') as f:
            f.write(f"PATH: {CONFIG_PATH}\n")
            f.write("-" * 20 + "\n")
            f.write(content)
            
        log(f"Dumped to: {OUTPUT_PATH}")
        xbmc.executebuiltin(f'Notification(Debug, Config Dumped, 2000)')
    else:
        log("Config file does not exist!")
        with open(OUTPUT_PATH, 'w') as f:
            f.write("Config file not found")

except Exception as e:
    log(f"Error: {e}")
