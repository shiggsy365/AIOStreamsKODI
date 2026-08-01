"""Small Kodi API stubs used by unit tests outside Kodi."""
import sys
import types


def install():
    """Install just enough of the Kodi module surface for focused tests."""
    xbmc = types.ModuleType('xbmc')
    xbmc.LOGDEBUG = 0
    xbmc.LOGINFO = 1
    xbmc.LOGWARNING = 2
    xbmc.LOGERROR = 3
    xbmc.log = lambda *args, **kwargs: None

    xbmcplugin = types.ModuleType('xbmcplugin')
    xbmcgui = types.ModuleType('xbmcgui')
    xbmcgui.NOTIFICATION_ERROR = 0
    xbmcgui.NOTIFICATION_INFO = 1
    xbmcgui.NOTIFICATION_WARNING = 2
    xbmcvfs = types.ModuleType('xbmcvfs')
    xbmcaddon = types.ModuleType('xbmcaddon')
    xbmcvfs.translatePath = lambda path: path
    xbmcvfs.exists = lambda path: False
    xbmcvfs.mkdirs = lambda path: None

    class Addon:
        def getSetting(self, _setting_id):
            return ''

        def setSetting(self, _setting_id, _value):
            return None

        def getSettingBool(self, _setting_id):
            return False

        def getAddonInfo(self, key):
            return {'path': '', 'profile': '', 'version': '0.0.0'}.get(key, '')

    xbmcaddon.Addon = Addon

    class InfoTagVideo:
        def __init__(self):
            self.values = {}

        def __getattr__(self, name):
            if name.startswith('set'):
                return lambda *values: self.values.__setitem__(name[3:], values[0] if len(values) == 1 else values)
            raise AttributeError(name)

    class ListItem:
        def __init__(self, label='', path=''):
            self.label = label
            self.path = path
            self.properties = {}
            self.art = {}
            self.info_tag = InfoTagVideo()

        def getVideoInfoTag(self):
            return self.info_tag

        def setProperty(self, key, value):
            self.properties[key] = value

        def setArt(self, art):
            self.art.update(art)

    xbmcgui.ListItem = ListItem
    sys.modules.update({
        'xbmc': xbmc, 'xbmcgui': xbmcgui, 'xbmcplugin': xbmcplugin,
        'xbmcvfs': xbmcvfs, 'xbmcaddon': xbmcaddon,
    })
    return xbmc, xbmcplugin
