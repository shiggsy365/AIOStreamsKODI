"""
Stream name formatters for AIOStreams.

Based on formatters from: https://github.com/Viren070/AIOStreams
Each formatter parses the pipe-delimited stream name format:
"PROVIDER|QUALITY|SIZE|INDEXER|CACHE_STATUS"

Example: "RD|FHD|4.39 GB|Knaben|Cached"
"""

import re
import xbmcaddon


class BaseFormatter:
    """Base class for stream formatters."""
    
    def format(self, stream_name):
        """
        Format a stream name according to the formatter's style.
        
        Args:
            stream_name: Pipe-delimited string (PROVIDER|QUALITY|SIZE|INDEXER|CACHE_STATUS)
            
        Returns:
            Formatted string with Kodi color codes
        """
        # Parse the stream name
        parts = stream_name.split('|')
        if len(parts) < 5:
            return stream_name  # Return original if format doesn't match
        
        provider = parts[0].strip()
        quality = parts[1].strip()
        size = parts[2].strip()
        indexer = parts[3].strip()
        cache_status = parts[4].strip()
        
        # Subclasses implement format_parsed
        return self.format_parsed(provider, quality, size, indexer, cache_status)
    
    def format_parsed(self, provider, quality, size, indexer, cache_status):
        """
        Format parsed stream components. Override in subclasses.
        
        Args:
            provider: Service provider (e.g., "RD", "TB")
            quality: Quality string (e.g., "FHD", "4K", "720p")
            size: Size string (e.g., "4.39 GB")
            indexer: Indexer/source name (e.g., "Knaben", "StremThru")
            cache_status: Cache status (e.g., "Cached", "Uncached")
            
        Returns:
            Formatted string
        """
        raise NotImplementedError


class TorrentioFormatter(BaseFormatter):
    """Torrentio-style formatter: [Provider] Quality • Size • Indexer"""
    
    def format_parsed(self, provider, quality, size, indexer, cache_status):
        # Provider in brackets with color
        provider_colored = f"[COLOR dodgerblue][{provider}][/COLOR]"
        
        # Quality (no color)
        quality_part = quality
        
        # Size in green
        size_colored = f"[COLOR green]{size}[/COLOR]"
        
        # Indexer (no color)
        indexer_part = indexer
        
        # Combine with bullet separators
        return f"{provider_colored} {quality_part} • {size_colored} • {indexer_part}"


class TorboxFormatter(BaseFormatter):
    """Torbox-style formatter: Provider (Instant/Download) (Quality) - Size - Indexer"""
    
    def format_parsed(self, provider, quality, size, indexer, cache_status):
        # Check if cached
        is_cached = cache_status.lower() == 'cached'
        
        # Provider name
        provider_text = provider
        
        # Cache status
        if is_cached:
            cache_text = " (Instant"
        else:
            cache_text = " ("
        
        # Service short name
        cache_text += f" {provider})"
        
        # Quality in parentheses
        quality_part = f" ({quality})" if quality else ""
        
        # Format full line
        parts = []
        parts.append(f"{provider_text}{cache_text}{quality_part}")
        
        # Add size and indexer
        if size:
            parts.append(f"[COLOR yellow]{size}[/COLOR]")
        if indexer:
            parts.append(f"Source: {indexer}")
        
        return " - ".join(parts)


class GDriveFormatter(BaseFormatter):
    """Google Drive (Full) formatter: [Provider*] Quality (Indexer) - Size - Source"""
    
    def format_parsed(self, provider, quality, size, indexer, cache_status):
        # Check if cached
        is_cached = cache_status.lower() == 'cached'
        
        # Provider with cache indicator
        if is_cached:
            provider_part = f"[COLOR cyan][{provider}*][/COLOR]"
        else:
            provider_part = f"[COLOR orange][{provider}][/COLOR]"
        
        # Quality
        quality_part = f" {quality}" if quality else ""
        
        # Indexer in parentheses
        indexer_part = f" ({indexer})" if indexer else ""
        
        # Size with label
        size_part = f"[COLOR lime]{size}[/COLOR]" if size else ""
        
        # Source with label
        source_part = indexer if indexer else ""
        
        # Combine
        line1 = f"{provider_part}{quality_part}{indexer_part}"
        parts = [line1]
        if size_part:
            parts.append(size_part)
        
        return " - ".join(parts)


class LightGDriveFormatter(BaseFormatter):
    """Google Drive (Light) formatter: [Provider*] Quality - Size - Source"""
    
    def format_parsed(self, provider, quality, size, indexer, cache_status):
        # Check if cached
        is_cached = cache_status.lower() == 'cached'
        
        # Provider with cache indicator
        if is_cached:
            provider_part = f"[COLOR cyan][{provider}*][/COLOR]"
        else:
            provider_part = f"[COLOR orange][{provider}][/COLOR]"
        
        # Quality
        quality_part = f" {quality}" if quality else ""
        
        # Size
        size_part = size if size else ""
        
        # Source
        source_part = indexer if indexer else ""
        
        # Combine
        parts = [f"{provider_part}{quality_part}"]
        if size_part:
            parts.append(size_part)
        if source_part:
            parts.append(source_part)
        
        return " - ".join(parts)


class PrismFormatter(BaseFormatter):
    """Prism-style formatter with quality indicators: Quality (Size, Source) [Provider*]"""
    
    def format_parsed(self, provider, quality, size, indexer, cache_status):
        # Map quality to display with indicator
        quality_map = {
            '4K': '4K UHD',
            '2160p': '4K UHD',
            'QHD': 'QHD',
            '1440p': 'QHD',
            'FHD': 'FHD',
            '1080p': 'FHD',
            'HD': 'HD',
            '720p': 'HD',
        }
        
        # Get quality display
        quality_display = quality_map.get(quality, quality)
        
        # Check if cached
        is_cached = cache_status.lower() == 'cached'
        
        # Cache status
        if is_cached:
            cache_icon = "*Ready"
        else:
            cache_icon = "Not Ready"
        
        # Provider
        provider_part = f"({provider})"
        
        # Build format
        parts = [f"[COLOR gold]{quality_display}[/COLOR]"]
        
        # Add size and source
        details = []
        if size:
            details.append(size)
        if indexer:
            details.append(indexer)
        
        if details:
            parts.append(" ".join(details))
        
        # Add provider and cache
        parts.append(f"{cache_icon} {provider_part}")
        
        return " - ".join(parts)


class MinimalisticGdriveFormatter(BaseFormatter):
    """Minimalistic formatter: Quality Size (Provider) Indexer"""
    
    def format_parsed(self, provider, quality, size, indexer, cache_status):
        # Simple format with minimal decoration
        parts = []
        
        if quality:
            parts.append(f"[B]{quality}[/B]")
        if size:
            parts.append(size)
        if provider:
            parts.append(f"[COLOR gray]({provider})[/COLOR]")
        if indexer:
            parts.append(indexer)
        
        return " ".join(parts)


def get_formatter_from_settings():
    """
    Get the appropriate formatter based on addon settings.
    
    Returns:
        Instance of a formatter class
    """
    try:
        addon = xbmcaddon.Addon()
        formatter_type = addon.getSetting('stream_formatter')
    except:
        formatter_type = 'torrentio'  # Default fallback
    
    # Map setting values to formatter classes
    formatter_map = {
        'torrentio': TorrentioFormatter,
        'torbox': TorboxFormatter,
        'gdrive': GDriveFormatter,
        'gdrive_light': LightGDriveFormatter,
        'prism': PrismFormatter,
        'gdrive_minimal': MinimalisticGdriveFormatter,
    }
    
    # Get formatter class and instantiate
    formatter_class = formatter_map.get(formatter_type, TorrentioFormatter)
    return formatter_class()
