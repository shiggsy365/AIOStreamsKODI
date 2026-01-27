# -*- coding: utf-8 -*-
"""Stream management for AIOStreams addon"""
import re
import json
import time
import xbmc
import xbmcvfs
from . import constants
from . import settings_helpers


class StreamManager:
    """Manages stream quality detection, reliability tracking, and preferences."""

    def __init__(self):
        self.stats_file = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.aiostreams/stream_stats.json')
        self.prefs_file = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.aiostreams/stream_prefs.json')
        self.stats = self._load_stats()
        self.prefs = self._load_prefs()

    def _ensure_data_dir(self):
        """Ensure addon_data directory exists."""
        data_dir = xbmcvfs.translatePath('special://profile/addon_data/plugin.video.aiostreams/')
        if not xbmcvfs.exists(data_dir):
            xbmcvfs.mkdirs(data_dir)

    def _load_stats(self):
        """Load stream reliability statistics."""
        if xbmcvfs.exists(self.stats_file):
            try:
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_stats(self):
        """Save stream reliability statistics."""
        self._ensure_data_dir()
        try:
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Failed to save stream stats: {e}', xbmc.LOGERROR)

    def _load_prefs(self):
        """Load user stream preferences."""
        if xbmcvfs.exists(self.prefs_file):
            try:
                with open(self.prefs_file, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save_prefs(self):
        """Save user stream preferences."""
        self._ensure_data_dir()
        try:
            with open(self.prefs_file, 'w') as f:
                json.dump(self.prefs, f)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Failed to save stream preferences: {e}', xbmc.LOGERROR)

    def detect_quality(self, stream_name):
        """
        Detect quality from stream name.
        Returns tuple: (quality_key, quality_rank, quality_label)
        """
        name_lower = stream_name.lower()

        # Check for quality indicators
        for quality_key, rank in sorted(constants.QUALITY_RANKS.items(), key=lambda x: x[1], reverse=True):
            if quality_key in name_lower:
                label = constants.QUALITY_LABELS.get(quality_key, f'[{quality_key.upper()}]')
                return quality_key, rank, label

        # Default to SD if no quality found
        return 'sd', constants.QUALITY_RANKS['sd'], constants.QUALITY_LABELS['sd']

    def get_quality_color(self, quality_rank):
        """Get color code based on quality rank."""
        if quality_rank >= constants.QUALITY_RANKS['1080p']:
            return constants.COLOR_QUALITY_1080P
        elif quality_rank >= constants.QUALITY_RANKS['720p']:
            return constants.COLOR_QUALITY_720P
        elif quality_rank >= constants.QUALITY_RANKS['4k']:
            return constants.COLOR_QUALITY_4K
        else:
            return constants.COLOR_QUALITY_SD

    def filter_by_quality(self, streams):
        """Filter streams based on quality preferences."""
        min_quality = settings_helpers.get_min_quality()
        filter_low = settings_helpers.get_filter_low_quality()

        if not filter_low:
            return streams

        min_rank = constants.QUALITY_RANKS.get(min_quality, 0)
        filtered = []

        for stream in streams:
            stream_name = stream.get('name', stream.get('title', ''))
            _, quality_rank, _ = self.detect_quality(stream_name)

            # Filter by minimum quality
            if quality_rank < min_rank:
                continue

            filtered.append(stream)

        return filtered

    def sort_streams(self, streams):
        """
        Sort streams.
        (DISABLED: Returns original JSON order at user request)
        """
        return streams

    def get_best_stream_fast(self, streams, quality_threshold='1080p', reliability_threshold=80):
        """Get best stream with original ordering logic removed.

        Args:
            streams: List of stream dicts
            quality_threshold: Ignored (reserved for compatibility)
            reliability_threshold: Ignored

        Returns:
            First stream from the list (original JSON order)
        """
        if not streams:
            return None

        # Filter streams by quality preference if applicable (handled by caller)
        # But we return the first available after filtering
        xbmc.log('[AIOStreams] Fast path active - returning first available stream in JSON order', xbmc.LOGDEBUG)
        return streams[0]

    def get_reliability_score(self, stream_url):
        """
        Get reliability score for a stream (0-100).
        Based on success/failure history.
        """
        if stream_url not in self.stats:
            return 50  # Neutral score for unknown streams

        stat = self.stats[stream_url]
        total = stat.get('success', 0) + stat.get('failure', 0)

        if total == 0:
            return 50

        success_rate = (stat.get('success', 0) / total) * 100
        return min(100, success_rate)

    def record_stream_result(self, stream_url, success):
        """Record whether a stream played successfully."""
        if stream_url not in self.stats:
            self.stats[stream_url] = {'success': 0, 'failure': 0, 'last_used': 0}

        if success:
            self.stats[stream_url]['success'] += 1
        else:
            self.stats[stream_url]['failure'] += 1

        self.stats[stream_url]['last_used'] = int(time.time())
        self._save_stats()

        xbmc.log(f'[AIOStreams] Stream result recorded: {stream_url[:50]}... = {success}', xbmc.LOGINFO)

    def get_preference_score(self, stream_name):
        """Get preference score based on user's selection history."""
        if not settings_helpers.get_learn_preferences():
            return 0

        # Extract provider/source from stream name
        provider = self._extract_provider(stream_name)

        if provider and provider in self.prefs:
            return min(100, self.prefs[provider])

        return 0

    def record_stream_selection(self, stream_name):
        """Record user's stream selection to learn preferences."""
        if not settings_helpers.get_learn_preferences():
            return

        provider = self._extract_provider(stream_name)

        if provider:
            if provider not in self.prefs:
                self.prefs[provider] = 0

            self.prefs[provider] += 1
            self._save_prefs()

            xbmc.log(f'[AIOStreams] Stream preference recorded: {provider}', xbmc.LOGINFO)

    def _extract_provider(self, stream_name):
        """Extract provider/source name from stream title."""
        # Common patterns: "Provider - Quality", "[Provider] Title", etc.
        patterns = [
            r'^([^\-\[\]]+)(?:\s*[\-\[])',  # Text before - or [
            r'^\[([^\]]+)\]',                # Text in brackets
            r'^([A-Za-z0-9]+)\s',            # First word
        ]

        for pattern in patterns:
            match = re.search(pattern, stream_name)
            if match:
                return match.group(1).strip().lower()

        return None

    def get_reliability_icon(self, reliability_score):
        """Get icon/indicator for reliability score."""
        if reliability_score >= constants.RELIABILITY_EXCELLENT:
            return '★★★'  # Excellent
        elif reliability_score >= constants.RELIABILITY_GOOD:
            return '★★☆'  # Good
        elif reliability_score >= constants.RELIABILITY_FAIR:
            return '★☆☆'  # Fair
        else:
            return '☆☆☆'  # Poor

    def format_stream_title(self, stream):
        """Format stream title with quality badge."""
        stream_name = stream.get('name', stream.get('title', 'Unknown Stream'))

        # Detect quality
        _, quality_rank, quality_label = self.detect_quality(stream_name)
        quality_color = self.get_quality_color(quality_rank)

        # Format title - Remove reliability icons for a cleaner presentation
        if settings_helpers.get_show_quality_badges():
            formatted = f"[COLOR {quality_color}]{quality_label}[/COLOR] {stream_name}"
        else:
            formatted = stream_name

        # Add description if available
        if stream.get('description'):
            formatted += f" - {stream['description']}"

        return formatted

    def clear_stats(self):
        """Clear all stream statistics."""
        self.stats = {}
        self._save_stats()
        xbmc.log('[AIOStreams] Stream statistics cleared', xbmc.LOGINFO)

    def clear_preferences(self):
        """Clear all learned preferences."""
        self.prefs = {}
        self._save_prefs()
        xbmc.log('[AIOStreams] Stream preferences cleared', xbmc.LOGINFO)


# Global instance
_stream_manager = None


def get_stream_manager():
    """Get global StreamManager instance."""
    global _stream_manager
    if _stream_manager is None:
        _stream_manager = StreamManager()
    return _stream_manager
