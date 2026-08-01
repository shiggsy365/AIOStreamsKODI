"""Pure helpers for Stremio stream identifiers and stream normalization."""
from collections import Counter
from urllib.parse import quote
from urllib.parse import urlsplit
import re


DIRECT_URL = 'direct_url'
SYNTHETIC_ERROR = 'synthetic_error'
SYNTHETIC_STATISTIC = 'synthetic_statistic'
EXTERNAL_URL = 'external_url'
TORRENT = 'torrent'
YOUTUBE = 'youtube'
USENET = 'usenet'
UNKNOWN = 'unknown'


def client_user_agent(version):
    """Identify Kodi as an AIOStreams-compatible Stremio API client."""
    return f'AIOStreams/Kodi-{version or "unknown"}'


def canonical_meta_id(meta):
    """Prefer the Stremio-compatible IMDb ID when metadata supplies one."""
    return meta.get('imdb_id') or meta.get('imdbId') or meta.get('id') or ''


def canonical_episode_id(video, show_id, season, episode):
    """Preserve an episode's exact Stremio video ID, with a legacy fallback."""
    return video.get('id') or f'{show_id}:{season}:{episode}'


def matching_episode_id(meta, show_id, season, episode):
    """Find and preserve the exact ID for a season/episode in full metadata."""
    try:
        wanted_season = int(season)
        wanted_episode = int(episode)
    except (TypeError, ValueError):
        return f'{show_id}:{season}:{episode}'
    for video in meta.get('videos') or []:
        try:
            if int(video.get('season')) == wanted_season and int(video.get('episode')) == wanted_episode:
                return canonical_episode_id(video, show_id, season, episode)
        except (TypeError, ValueError):
            continue
    return f'{show_id}:{season}:{episode}'


def _text(value):
    return value.strip() if isinstance(value, str) else ''


def classify_stream(stream):
    """Return the transport/synthetic class for a Stremio stream object."""
    stream_data = stream.get('streamData') or {}
    stream_type = _text(stream_data.get('type')).lower()
    if stream_type == 'error' or stream_data.get('error'):
        return SYNTHETIC_ERROR
    if stream_type in ('statistic', 'statistics'):
        return SYNTHETIC_STATISTIC
    url = _text(stream.get('url'))
    if url:
        return DIRECT_URL if urlsplit(url).scheme.lower() in ('http', 'https') else UNKNOWN
    if _text(stream.get('infoHash')):
        return TORRENT
    if _text(stream.get('ytId')):
        return YOUTUBE
    if _text(stream.get('nzbUrl')):
        return USENET
    if _text(stream.get('externalUrl')):
        return EXTERNAL_URL
    return UNKNOWN


def kodi_headers(stream):
    """Encode behaviorHints proxy request headers using Kodi URL syntax."""
    hints = stream.get('behaviorHints') or {}
    headers = (hints.get('proxyHeaders') or {}).get('request') or {}
    pairs = []
    for key, value in headers.items():
        if key and value is not None:
            pairs.append(f'{quote(str(key), safe="-")}={quote(str(value), safe="")}')
    return '&'.join(pairs)


def playable_url(stream):
    """Return a Kodi-ready direct URL; never promote externalUrl."""
    if classify_stream(stream) != DIRECT_URL:
        return ''
    url = _text(stream.get('url'))
    headers = kodi_headers(stream)
    return f'{url}|{headers}' if headers else url


def stream_search_text(stream):
    """Combine formatter fields used for labels and quality detection."""
    hints = stream.get('behaviorHints') or {}
    return '\n'.join(filter(None, (
        _text(stream.get('name')),
        _text(stream.get('title')),
        _text(stream.get('description')),
        _text(hints.get('filename')),
    )))


def display_label(stream):
    """Build a useful non-blank primary label without assuming a formatter."""
    hints = stream.get('behaviorHints') or {}
    return (_text(stream.get('name')) or _text(stream.get('title')) or
            _text(hints.get('filename')) or _text(stream.get('description')) or
            'Direct stream')


def _format_bytes(value):
    try:
        size = float(value)
    except (TypeError, ValueError):
        return ''
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size < 1024 or unit == 'TB':
            return f'{size:.2f} {unit}' if unit in ('GB', 'TB') else f'{size:.0f} {unit}'
        size /= 1024
    return ''


def stream_display_fields(stream):
    """Extract useful dialog fields from formatter text and structured data."""
    data = stream.get('streamData') or {}
    hints = stream.get('behaviorHints') or {}
    search_text = stream_search_text(stream)
    resolution_match = re.search(r'(?i)\b(4k|uhd|fhd|(?:2160|1440|1080|720|576|480|360)p)\b', search_text)
    service = data.get('service') or ''
    cached = ''
    if isinstance(service, dict):
        cached_value = service.get('cached')
        cached = 'YES' if cached_value is True else ('NO' if cached_value is False else '')
        service = service.get('name') or service.get('id') or ''
    duration = data.get('duration')
    if isinstance(duration, (int, float)) and duration > 0:
        duration = f'{int(duration) // 3600}h {(int(duration) % 3600) // 60}m'
    else:
        duration = ''
    return {
        'resolution': resolution_match.group(1).upper() if resolution_match else '',
        'service': str(service),
        'addon': str(data.get('addon') or ''),
        'size': _format_bytes(data.get('size')),
        'proxied': 'YES' if data.get('proxied') is True else ('NO' if data.get('proxied') is False else ''),
        'cached': cached,
        'in_library': 'YES' if data.get('library') is True else ('NO' if data.get('library') is False else ''),
        'duration': duration,
        'video': '',
        'audio': '',
        'indexer': str(data.get('indexer') or ''),
        'filename': str(hints.get('filename') or data.get('filename') or ''),
    }


def stream_message(stream):
    """Extract a concise synthetic error/information message."""
    stream_data = stream.get('streamData') or {}
    title = display_label(stream)
    error = stream_data.get('error')
    if isinstance(error, dict):
        error = error.get('message') or error.get('description') or error.get('name')
    detail = (_text(stream.get('description')) or _text(error))
    if detail and detail != title:
        return f'{title}: {detail}'
    return title


def normalize_streams(raw_streams):
    """Split direct playable streams from diagnostics and summarize transports."""
    raw_streams = raw_streams or []
    counts = Counter(classify_stream(stream) for stream in raw_streams)
    playable = []
    messages = []
    for stream in raw_streams:
        kind = classify_stream(stream)
        if kind == DIRECT_URL:
            normalized = dict(stream)
            normalized['_playback_url'] = playable_url(stream)
            playable.append(normalized)
        elif kind in (SYNTHETIC_ERROR, SYNTHETIC_STATISTIC):
            messages.append(stream_message(stream))
    return {'playable': playable, 'counts': dict(counts), 'messages': messages}
