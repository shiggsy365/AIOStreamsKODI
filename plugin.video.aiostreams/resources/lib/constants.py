# -*- coding: utf-8 -*-
"""Constants for AIOStreams addon"""

# Quality rankings (higher is better)
QUALITY_RANKS = {
    '4k': 400,
    '2160p': 400,
    'uhd': 400,
    '1080p': 300,
    'fhd': 300,
    '720p': 200,
    'hd': 200,
    '480p': 100,
    'sd': 50,
    '360p': 30,
    '240p': 10
}

# Quality display names
QUALITY_LABELS = {
    '4k': '[4K]',
    '2160p': '[4K]',
    'uhd': '[4K]',
    '1080p': '[1080p]',
    'fhd': '[1080p]',
    '720p': '[720p]',
    'hd': '[720p]',
    '480p': '[480p]',
    'sd': '[SD]',
    '360p': '[360p]',
    '240p': '[240p]'
}

# Color codes for Kodi
COLOR_WATCHED = 'dodgerblue'
COLOR_IN_PROGRESS = 'gold'
COLOR_UNWATCHED = 'white'
COLOR_QUALITY_4K = 'magenta'
COLOR_QUALITY_1080P = 'lime'
COLOR_QUALITY_720P = 'cyan'
COLOR_QUALITY_SD = 'silver'

# Stream reliability thresholds
RELIABILITY_EXCELLENT = 90  # 90%+
RELIABILITY_GOOD = 70       # 70-89%
RELIABILITY_FAIR = 50       # 50-69%
RELIABILITY_POOR = 50       # Below 50%

# Cache durations (in seconds)
CACHE_METADATA = 86400      # 24 hours
CACHE_WATCHLIST = 3600      # 1 hour
CACHE_WATCHED = 3600        # 1 hour
CACHE_STREAMS = 300         # 5 minutes

# Settings defaults
DEFAULT_QUALITY_PREFERENCE = 'any'
DEFAULT_MIN_QUALITY = '480p'
DEFAULT_AUTO_RESUME = True
DEFAULT_RESUME_THRESHOLD = 90  # Mark watched at 90%
DEFAULT_STREAM_TIMEOUT = 5
DEFAULT_LEARN_PREFERENCES = True
DEFAULT_SHOW_PROGRESS_BARS = True
DEFAULT_COLOR_CODE_ITEMS = True
