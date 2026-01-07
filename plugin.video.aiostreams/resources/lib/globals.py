# -*- coding: utf-8 -*-
"""
Global state manager for AIOStreams addon.
Provides centralized access to addon settings, paths, and state.
Based on Seren's globals pattern for cleaner architecture.
"""
import sys
import xbmc
import xbmcaddon
import xbmcvfs
from urllib.parse import parse_qsl


class Globals:
    """
    Singleton global state manager.
    Centralizes addon configuration, settings, paths, and request handling.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def init(self, argv=None):
        """
        Initialize global state from command-line arguments.

        Args:
            argv: sys.argv from Kodi plugin call
        """
        if argv is None:
            argv = sys.argv

        self._addon = xbmcaddon.Addon()
        self._addon_id = self._addon.getAddonInfo('id')
        self._addon_name = self._addon.getAddonInfo('name')
        self._addon_version = self._addon.getAddonInfo('version')

        # Handle will be -1 for service.py calls
        try:
            self._handle = int(argv[1]) if len(argv) > 1 else -1
        except (ValueError, IndexError):
            self._handle = -1

        # Parse request parameters
        try:
            self._params = dict(parse_qsl(argv[2][1:])) if len(argv) > 2 else {}
        except (IndexError, TypeError):
            self._params = {}

        # Initialize paths lazily
        self._paths_initialized = False
        self._addon_path = None
        self._profile_path = None
        self._cache_path = None
        self._database_path = None

        # Settings cache for performance
        self._settings_cache = {}
        self._runtime_settings = {}

        # Cache instance (set later to avoid circular imports)
        self._cache = None

        self._initialized = True

    def _init_paths(self):
        """Lazily initialize file paths."""
        if self._paths_initialized:
            return

        self._addon_path = xbmcvfs.translatePath(self._addon.getAddonInfo('path'))
        self._profile_path = xbmcvfs.translatePath(self._addon.getAddonInfo('profile'))
        self._cache_path = xbmcvfs.translatePath(f'{self._profile_path}cache/')
        self._database_path = xbmcvfs.translatePath(f'{self._profile_path}')

        # Ensure directories exist
        for path in [self._profile_path, self._cache_path]:
            if not xbmcvfs.exists(path):
                xbmcvfs.mkdirs(path)

        self._paths_initialized = True

    @property
    def ADDON(self):
        """Get addon instance."""
        return self._addon

    @property
    def ADDON_ID(self):
        """Get addon ID."""
        return self._addon_id

    @property
    def ADDON_NAME(self):
        """Get addon name."""
        return self._addon_name

    @property
    def ADDON_VERSION(self):
        """Get addon version."""
        return self._addon_version

    @property
    def HANDLE(self):
        """Get plugin handle for directory operations."""
        return self._handle

    @property
    def PARAMS(self):
        """Get request parameters."""
        return self._params

    @property
    def ADDON_PATH(self):
        """Get addon installation path."""
        self._init_paths()
        return self._addon_path

    @property
    def PROFILE_PATH(self):
        """Get user profile/data path."""
        self._init_paths()
        return self._profile_path

    @property
    def CACHE_PATH(self):
        """Get cache directory path."""
        self._init_paths()
        return self._cache_path

    @property
    def DATABASE_PATH(self):
        """Get database directory path."""
        self._init_paths()
        return self._database_path

    def get_setting(self, key, default=None):
        """
        Get addon setting as string.

        Args:
            key: Setting ID
            default: Default value if setting is empty

        Returns:
            Setting value as string, or default
        """
        if key in self._settings_cache:
            value = self._settings_cache[key]
            return value if value else default

        value = self._addon.getSetting(key)
        self._settings_cache[key] = value
        return value if value else default

    def get_bool_setting(self, key, default=False):
        """
        Get addon setting as boolean.

        Args:
            key: Setting ID
            default: Default value if setting is empty

        Returns:
            Setting value as boolean
        """
        value = self.get_setting(key)
        if value is None or value == '':
            return default
        return value.lower() == 'true'

    def get_int_setting(self, key, default=0):
        """
        Get addon setting as integer.

        Args:
            key: Setting ID
            default: Default value if setting is empty or invalid

        Returns:
            Setting value as integer
        """
        value = self.get_setting(key)
        if value is None or value == '':
            return default
        try:
            return int(value)
        except ValueError:
            return default

    def get_float_setting(self, key, default=0.0):
        """
        Get addon setting as float.

        Args:
            key: Setting ID
            default: Default value if setting is empty or invalid

        Returns:
            Setting value as float
        """
        value = self.get_setting(key)
        if value is None or value == '':
            return default
        try:
            return float(value)
        except ValueError:
            return default

    def set_setting(self, key, value):
        """
        Set addon setting.

        Args:
            key: Setting ID
            value: Value to set (will be converted to string)
        """
        str_value = str(value) if not isinstance(value, bool) else str(value).lower()
        self._addon.setSetting(key, str_value)
        self._settings_cache[key] = str_value

    def get_runtime_setting(self, key, default=None):
        """
        Get runtime-only setting (not persisted).

        Args:
            key: Setting key
            default: Default value

        Returns:
            Runtime setting value
        """
        return self._runtime_settings.get(key, default)

    def set_runtime_setting(self, key, value):
        """
        Set runtime-only setting (not persisted).

        Args:
            key: Setting key
            value: Value to set
        """
        self._runtime_settings[key] = value

    def clear_settings_cache(self):
        """Clear the settings cache to force re-read from disk."""
        self._settings_cache.clear()

    def clear_runtime_settings(self):
        """Clear all runtime settings."""
        self._runtime_settings.clear()

    def get_base_url(self):
        """
        Get the base URL from settings with manifest.json stripped.

        Returns:
            Base URL string
        """
        url = self.get_setting('base_url', '')
        if url.endswith('/manifest.json'):
            url = url[:-14]
        return url

    def get_timeout(self):
        """
        Get request timeout from settings.

        Returns:
            Timeout in seconds
        """
        return self.get_int_setting('timeout', 10)

    def get_url(self, **kwargs):
        """
        Create a URL for calling the plugin recursively.

        Args:
            **kwargs: URL parameters

        Returns:
            Plugin URL string
        """
        from urllib.parse import urlencode
        return f'{sys.argv[0]}?{urlencode(kwargs)}'

    def log(self, message, level=xbmc.LOGDEBUG):
        """
        Log message with addon prefix.

        Args:
            message: Message to log
            level: Log level (xbmc.LOGDEBUG, xbmc.LOGINFO, etc.)
        """
        xbmc.log(f'[{self._addon_name}] {message}', level)

    def log_debug(self, message):
        """Log debug message."""
        self.log(message, xbmc.LOGDEBUG)

    def log_info(self, message):
        """Log info message."""
        self.log(message, xbmc.LOGINFO)

    def log_warning(self, message):
        """Log warning message."""
        self.log(message, xbmc.LOGWARNING)

    def log_error(self, message):
        """Log error message."""
        self.log(message, xbmc.LOGERROR)

    def deinit(self):
        """
        Cleanup on addon exit.
        Called at the end of plugin execution.
        """
        # Clear runtime settings
        self._runtime_settings.clear()

        # Flush any pending cache writes if cache is initialized
        if self._cache is not None:
            try:
                self._cache.flush()
            except:
                pass

    @property
    def is_initialized(self):
        """Check if globals have been initialized."""
        return self._initialized


# Global singleton instance
g = Globals()
