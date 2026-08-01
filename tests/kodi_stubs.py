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
    sys.modules.update({'xbmc': xbmc, 'xbmcplugin': xbmcplugin})
    return xbmc, xbmcplugin
