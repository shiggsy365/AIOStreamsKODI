"""Canonical media identity helpers for navigation, playback, and persistence."""
from dataclasses import dataclass
from typing import Optional
import re


MOVIE_TYPES = frozenset(('movie', 'movies'))
SERIES_TYPES = frozenset(('series', 'show', 'shows', 'tvshow', 'tvshows'))


def _text(value):
    """Return a non-empty stripped string, or ``None``."""
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _first(*values):
    for value in values:
        value = _text(value)
        if value:
            return value
    return None


def normalize_content_type(content_type, fallback='movie'):
    """Map Kodi, Trakt, and Stremio spellings to the media contract."""
    value = (_text(content_type) or fallback).lower()
    if value in MOVIE_TYPES:
        return 'movie'
    if value in SERIES_TYPES:
        return 'series'
    return value


def _ids(meta):
    values = meta.get('ids') or {}
    return values if isinstance(values, dict) else {}


def _imdb_id(meta, metadata_id):
    ids = _ids(meta)
    candidate = _first(meta.get('imdb_id'), meta.get('imdbId'), ids.get('imdb'))
    if candidate:
        return candidate
    return metadata_id if metadata_id and re.fullmatch(r'tt\d+', metadata_id, re.IGNORECASE) else None


def _tmdb_id(meta, metadata_id):
    ids = _ids(meta)
    candidate = _first(meta.get('tmdb_id'), meta.get('tmdbId'), ids.get('tmdb'))
    if candidate:
        return candidate
    if metadata_id and metadata_id.lower().startswith('tmdb:'):
        return metadata_id.split(':', 1)[1]
    return None


@dataclass(frozen=True)
class MediaRef:
    """The explicitly normalized identities for one movie, show, or episode."""

    content_type: str
    metadata_id: str
    playable_id: Optional[str]
    imdb_id: Optional[str]
    tmdb_id: Optional[str]
    title: str
    year: Optional[int]
    poster: Optional[str]
    fanart: Optional[str]
    origin_fingerprint: Optional[str]

    @property
    def navigation_id(self):
        """ID used to reopen catalog metadata/navigation."""
        return self.metadata_id

    @property
    def playback_id(self):
        """The safest known playback identifier, in deliberate priority order."""
        return self.playable_id or self.imdb_id or self.metadata_id

    @classmethod
    def from_meta(cls, meta, content_type=None, origin_fingerprint=None):
        """Build a reference without treating an opaque Stremio ID as IMDb data."""
        meta = meta or {}
        ids = _ids(meta)
        metadata_id = _first(
            meta.get('metadata_id'), meta.get('meta_id'), meta.get('id'),
            meta.get('imdb_id'), meta.get('imdbId'), ids.get('imdb'),
            meta.get('tmdb_id'), meta.get('tmdbId'), ids.get('tmdb'),
        ) or ''
        year = meta.get('year')
        try:
            year = int(str(year)[:4]) if year else None
        except (TypeError, ValueError):
            year = None
        return cls(
            content_type=normalize_content_type(content_type or meta.get('type')),
            metadata_id=metadata_id,
            playable_id=_first(
                meta.get('playable_id'), meta.get('playableId'),
                meta.get('stream_id'), meta.get('streamId'), meta.get('video_id'),
            ),
            imdb_id=_imdb_id(meta, metadata_id),
            tmdb_id=_tmdb_id(meta, metadata_id),
            title=_first(meta.get('name'), meta.get('title')) or 'Unknown Title',
            year=year,
            poster=_first(meta.get('poster'), meta.get('poster_url')),
            fanart=_first(meta.get('background'), meta.get('fanart')),
            origin_fingerprint=_text(origin_fingerprint or meta.get('origin_fingerprint')),
        )

    @classmethod
    def episode(cls, show, video, season, episode, origin_fingerprint=None):
        """Derive an episode reference while preserving an exact Stremio video ID."""
        show_ref = show if isinstance(show, cls) else cls.from_meta(show, 'series', origin_fingerprint)
        video = video or {}
        exact_id = _first(video.get('id'), video.get('playable_id'))
        fallback_id = f'{show_ref.navigation_id}:{season}:{episode}'
        metadata_id = _first(video.get('metadata_id'), exact_id, fallback_id) or fallback_id
        return cls(
            content_type='episode',
            metadata_id=metadata_id,
            playable_id=exact_id or fallback_id,
            imdb_id=_imdb_id(video, metadata_id),
            tmdb_id=_tmdb_id(video, metadata_id),
            title=_first(video.get('title'), video.get('name')) or f'S{season}E{episode}',
            year=show_ref.year,
            poster=_first(video.get('thumbnail'), video.get('poster'), show_ref.poster),
            fanart=_first(video.get('background'), show_ref.fanart),
            origin_fingerprint=_text(origin_fingerprint) or show_ref.origin_fingerprint,
        )
