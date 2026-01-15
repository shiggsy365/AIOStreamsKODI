import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

class OnboardingWizard:
    def __init__(self):
        self.dialog = xbmcgui.Dialog()
        self.skin_addon = xbmcaddon.Addon('skin.AIODI')
        self.aiostreams = xbmcaddon.Addon('plugin.video.aiostreams')
        self.imvdb = xbmcaddon.Addon('plugin.video.imvdb')
        
    def run(self):
        # 1. Welcome Screen
        if not self.dialog.yesno(
            "Welcome to AIODI",
            "This wizard will help you configure the AIODI skin and required plugins.\n\n"
            "You will need:\n"
            "- AIOStreams credentials\n"
            "- YouTube API Key/ID/Secret\n"
            "- Trakt Client ID/Secret\n"
            "- IMVDb API Key\n"
            "- IPTV M3U/EPG URLs\n\n"
            "Ready to start?",
            yeslabel="Let's Go",
            nolabel="Cancel"
        ):
            return

        # 2. AIOStreams Config
        if self.dialog.yesno("AIOStreams", "Do you want to configure AIOStreams now?"):
            # 1. Host URL
            host = self.dialog.input("AIOStreams Host URL (e.g. https://aiostreams.elfhosted.com)", 
                                   defaultt=self.aiostreams.getSetting('aiostreams_host'))
            
            if host:
                self.aiostreams.setSetting('aiostreams_host', host)
                
                # 2. UUID
                uuid = self.dialog.input("AIOStreams UUID", defaultt=self.aiostreams.getSetting('aiostreams_uuid'))
                if uuid:
                    self.aiostreams.setSetting('aiostreams_uuid', uuid)
                    
                    # 3. Password (API Key)
                    # Use standard INPUT_PASSWORD (5)
                    password = self.dialog.input("Password", option=xbmcgui.INPUT_PASSWORD, 
                                               defaultt=self.aiostreams.getSetting('aiostreams_password'))
                    
                    if password:
                        self.aiostreams.setSetting('aiostreams_password', password)
                        
                        # Only trigger if we have everything
                        self.dialog.notification("AIODI Wizard", "Retrieving Manifest...", xbmcgui.NOTIFICATION_INFO, 3000)
                        xbmc.executebuiltin('RunPlugin(plugin://plugin.video.aiostreams/?action=retrieve_manifest)')
                        xbmc.sleep(2000)
                        
                        # Check if manifest retrieved (base_url populated)
                        manifest_url = self.aiostreams.getSetting('base_url')
                        if not manifest_url:
                            # Wait a bit longer and try again
                             xbmc.sleep(3000)
                             manifest_url = self.aiostreams.getSetting('base_url')

                        if manifest_url:
                             self.dialog.ok("Success", f"Manifest retrieved:\n{manifest_url}")
                             
                             # Default Behavior
                             modes = ["Show Streams (Default)", "Play First Stream"]
                             sel = self.dialog.select("Preferred Default Behavior", modes)
                             if sel == 1:
                                 self.aiostreams.setSetting('default_behavior', 'play_first')
                             else:
                                 self.aiostreams.setSetting('default_behavior', 'show_streams')

                             # Subtitles
                             if self.dialog.yesno("Subtitles", "Do you want to filter subtitle languages?\n(e.g. only show English, Spanish)"):
                                 langs = self.dialog.input("Three letter country definitions, comma separated, eg eng, spa", 
                                                         defaultt=self.aiostreams.getSetting('subtitle_languages'))
                                 if langs:
                                     self.aiostreams.setSetting('subtitle_languages', langs)

                             # UpNext
                             if self.dialog.yesno("UpNext", "Enable UpNext Integration?\n(Shows 'Next Episode' popup at end of playback)"):
                                 self.aiostreams.setSetting('autoplay_next_episode', 'true')
                             else:
                                 self.aiostreams.setSetting('autoplay_next_episode', 'false')
                        else:
                             self.dialog.ok("Warning", "Manifest not retrieved yet.\nPlease check settings later.")

        # 3. YouTube Config
        if self.dialog.yesno("YouTube", "Do you want to configure YouTube API keys?"):
            try:
                youtube = xbmcaddon.Addon('plugin.video.youtube')
                api_key = self.dialog.input("API Key", defaultt=youtube.getSetting('youtube.api.key'))
                if api_key: youtube.setSetting('youtube.api.key', api_key)
                
                client_id = self.dialog.input("Client ID", defaultt=youtube.getSetting('youtube.api.id'))
                if client_id: youtube.setSetting('youtube.api.id', client_id)
                
                client_secret = self.dialog.input("Client Secret", defaultt=youtube.getSetting('youtube.api.secret'))
                if client_secret: youtube.setSetting('youtube.api.secret', client_secret)
                
                if self.dialog.yesno("YouTube Sign In", "Launch YouTube Sign In now?"):
                    # Use specific sign-in path provided by user
                    xbmc.executebuiltin('RunPlugin(plugin://plugin.video.youtube/kodion/route/sign/)')
            except Exception as e:
                self.dialog.ok("Error", f"YouTube plugin not found or error: {str(e)}")

        # 4. Trakt Config
        if self.dialog.yesno("Trakt", "Do you want to configure Trakt?"):
            client_id = self.dialog.input("Trakt Client ID", defaultt=self.aiostreams.getSetting('trakt_client_id'))
            if client_id: self.aiostreams.setSetting('trakt_client_id', client_id)
            
            client_secret = self.dialog.input("Trakt Client Secret", defaultt=self.aiostreams.getSetting('trakt_client_secret'))
            if client_secret: self.aiostreams.setSetting('trakt_client_secret', client_secret)
            
            if self.dialog.yesno("Trakt Auth", "Authenticate Trakt now?"):
                xbmc.executebuiltin('RunPlugin(plugin://plugin.video.aiostreams/?action=trakt_auth)')

        # 5. IMVDb Config
        if self.dialog.yesno("IMVDb", "Do you want to configure IMVDb (Music Videos)?"):
            api_key = self.dialog.input("IMVDb API Key", defaultt=self.imvdb.getSetting('imvdb_api_key'))
            if api_key:
                self.imvdb.setSetting('imvdb_api_key', api_key)

        # 6. IPTV Simple Client Config
        if self.dialog.yesno("IPTV", "Do you want to configure IPTV Simple Client?"):
            try:
                iptv = xbmcaddon.Addon('pvr.iptvsimple')
                
                # Try getting existing value from new or old keys
                curr_m3u = iptv.getSetting('m3u_url') or iptv.getSetting('m3uPath')
                m3u = self.dialog.input("M3U Playlist URL", defaultt=curr_m3u)
                
                if m3u: 
                    # Set both new and old keys to ensure compatibility with "Migrated" instances
                    iptv.setSetting('m3u_url', m3u)
                    iptv.setSetting('m3uPath', m3u)
                
                curr_epg = iptv.getSetting('epg_url') or iptv.getSetting('epgPath')
                epg = self.dialog.input("EPG URL", defaultt=curr_epg)
                
                if epg: 
                    iptv.setSetting('epg_url', epg)
                    iptv.setSetting('epgPath', epg)
                    
            except Exception as e:
                self.dialog.ok("Error", f"IPTV Simple Client not found: {str(e)}")

        # 7. Completion
        self.dialog.ok("Setup Complete", "All configurations have been saved!\nEnjoy your AIODI experience.")
        self.skin_addon.setSetting('first_run', 'false')
        # Vital: Set the Skin string that Home.xml checks
        xbmc.executebuiltin('Skin.SetString(first_run, done)')

if __name__ == '__main__':
    OnboardingWizard().run()
