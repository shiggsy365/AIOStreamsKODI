# -*- coding: utf-8 -*-
"""
Base provider abstraction for stream sources.
Based on Seren's provider system for extensibility.
"""
import xbmc
from abc import ABC, abstractmethod


class BaseProvider(ABC):
    """
    Abstract base class for stream providers.

    All provider implementations must inherit from this class
    and implement the required abstract methods.
    """

    # Provider metadata
    name = "base"
    display_name = "Base Provider"
    enabled = True
    priority = 50  # Higher = preferred (0-100)

    # Provider capabilities
    supports_movies = True
    supports_series = True
    supports_search = True
    supports_catalogs = True

    def __init__(self):
        """Initialize provider."""
        self._initialized = False

    def initialize(self):
        """
        Initialize the provider (called once before first use).
        Override in subclasses for custom initialization.
        """
        self._initialized = True
        return True

    @property
    def is_initialized(self):
        """Check if provider is initialized."""
        return self._initialized

    @abstractmethod
    def get_streams(self, content_type, media_id):
        """
        Get available streams for a media item.

        Args:
            content_type: Type of content ('movie' or 'series')
            media_id: Unique identifier (IMDB ID, etc.)

        Returns:
            dict with 'streams' key containing list of stream dicts, or None on error
            Each stream dict should have: name, url/externalUrl, description (optional)
        """
        pass

    @abstractmethod
    def search(self, query, content_type='movie'):
        """
        Search for content.

        Args:
            query: Search query string
            content_type: Type of content to search ('movie' or 'series')

        Returns:
            dict with 'metas' key containing list of meta dicts, or None on error
        """
        pass

    def get_catalogs(self):
        """
        Get available catalogs from this provider.

        Returns:
            List of catalog dicts with 'id', 'name', 'type' keys
        """
        return []

    def get_catalog(self, content_type, catalog_id, genre=None, skip=0):
        """
        Get items from a specific catalog.

        Args:
            content_type: Type of content
            catalog_id: Catalog identifier
            genre: Optional genre filter
            skip: Number of items to skip (pagination)

        Returns:
            dict with 'metas' key containing list of meta dicts
        """
        return None

    def get_meta(self, content_type, meta_id):
        """
        Get metadata for a specific item.

        Args:
            content_type: Type of content
            meta_id: Metadata identifier

        Returns:
            dict with 'meta' key containing metadata dict
        """
        return None

    def get_subtitles(self, content_type, media_id):
        """
        Get available subtitles for a media item.

        Args:
            content_type: Type of content
            media_id: Media identifier

        Returns:
            dict with 'subtitles' key containing list of subtitle dicts
        """
        return None

    def test_connection(self):
        """
        Test connection to the provider.

        Returns:
            tuple (success: bool, message: str)
        """
        return False, "Not implemented"

    def log(self, message, level=xbmc.LOGDEBUG):
        """Log message with provider prefix."""
        xbmc.log(f'[AIOStreams][{self.name}] {message}', level)


class ProviderManager:
    """
    Manages multiple providers with priority-based routing.
    """

    def __init__(self):
        """Initialize provider manager."""
        self._providers = {}
        self._provider_order = []  # Sorted by priority

    def register(self, provider):
        """
        Register a provider.

        Args:
            provider: BaseProvider instance
        """
        if not isinstance(provider, BaseProvider):
            raise TypeError("Provider must inherit from BaseProvider")

        self._providers[provider.name] = provider

        # Re-sort by priority (descending)
        self._provider_order = sorted(
            self._providers.keys(),
            key=lambda p: self._providers[p].priority,
            reverse=True
        )

        xbmc.log(f'[AIOStreams] Registered provider: {provider.name} (priority: {provider.priority})', xbmc.LOGINFO)

    def unregister(self, provider_name):
        """
        Unregister a provider.

        Args:
            provider_name: Name of provider to unregister
        """
        if provider_name in self._providers:
            del self._providers[provider_name]
            self._provider_order = [p for p in self._provider_order if p != provider_name]

    def get_provider(self, name):
        """
        Get a specific provider by name.

        Args:
            name: Provider name

        Returns:
            BaseProvider instance or None
        """
        return self._providers.get(name)

    def get_enabled_providers(self):
        """
        Get all enabled providers in priority order.

        Returns:
            List of BaseProvider instances
        """
        return [
            self._providers[name]
            for name in self._provider_order
            if self._providers[name].enabled
        ]

    def get_primary_provider(self):
        """
        Get the highest priority enabled provider.

        Returns:
            BaseProvider instance or None
        """
        enabled = self.get_enabled_providers()
        return enabled[0] if enabled else None

    def get_streams(self, content_type, media_id, provider_name=None):
        """
        Get streams from providers.

        Args:
            content_type: Type of content
            media_id: Media identifier
            provider_name: Optional specific provider to use

        Returns:
            dict with 'streams' key, or None
        """
        if provider_name:
            provider = self.get_provider(provider_name)
            if provider and provider.enabled:
                return provider.get_streams(content_type, media_id)
            return None

        # Try providers in priority order
        for provider in self.get_enabled_providers():
            try:
                result = provider.get_streams(content_type, media_id)
                if result and result.get('streams'):
                    return result
            except Exception as e:
                provider.log(f'Stream fetch error: {e}', xbmc.LOGERROR)

        return None

    def search(self, query, content_type='movie', provider_name=None):
        """
        Search for content across providers.

        Args:
            query: Search query
            content_type: Type of content to search
            provider_name: Optional specific provider to use

        Returns:
            dict with 'metas' key, or None
        """
        if provider_name:
            provider = self.get_provider(provider_name)
            if provider and provider.enabled:
                return provider.search(query, content_type)
            return None

        # Use primary provider for search
        provider = self.get_primary_provider()
        if provider:
            return provider.search(query, content_type)

        return None

    def get_all_catalogs(self):
        """
        Get catalogs from all enabled providers.

        Returns:
            List of catalog dicts with provider info
        """
        catalogs = []
        for provider in self.get_enabled_providers():
            if provider.supports_catalogs:
                try:
                    provider_catalogs = provider.get_catalogs()
                    for catalog in provider_catalogs:
                        catalog['provider'] = provider.name
                    catalogs.extend(provider_catalogs)
                except Exception as e:
                    provider.log(f'Catalog fetch error: {e}', xbmc.LOGERROR)
        return catalogs

    @property
    def provider_count(self):
        """Get number of registered providers."""
        return len(self._providers)

    @property
    def enabled_count(self):
        """Get number of enabled providers."""
        return len(self.get_enabled_providers())


# Global provider manager instance
_provider_manager = None


def get_provider_manager():
    """Get global ProviderManager instance."""
    global _provider_manager
    if _provider_manager is None:
        _provider_manager = ProviderManager()
    return _provider_manager
