"""Durable, profile-local state for searches and local favorites.

This database deliberately has no dependency on the disposable cache or the
Trakt sync database.  It is safe for the plug-in and background service to use
at the same time because each operation opens a short-lived SQLite connection.
"""
from __future__ import annotations

from contextlib import contextmanager
import os
import sqlite3
import threading
import time
from typing import Iterator, Mapping, Optional, Union

from .media import MediaRef, normalize_content_type


SCHEMA_VERSION = 1
DEFAULT_HISTORY_LIMIT = 20
DATABASE_FILENAME = 'user_state.db'


class UserStateError(RuntimeError):
    """Raised when durable user state cannot be read or written safely."""


def _log(level, message):
    """Log in Kodi when available without making this module Kodi-dependent."""
    try:
        import xbmc
        xbmc.log('[AIOStreams UserState] {}'.format(message), level)
    except ImportError:
        pass


def _text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _search_scope(content_type):
    value = (_text(content_type) or 'all').lower()
    aliases = {
        'all': 'all', 'both': 'all',
        'movie': 'movies', 'movies': 'movies',
        'series': 'shows', 'show': 'shows', 'shows': 'shows',
        'tvshow': 'shows', 'tvshows': 'shows',
    }
    try:
        return aliases[value]
    except KeyError:
        raise ValueError('Unsupported search scope: {}'.format(content_type))


def _normalized_query(query):
    query = _text(query)
    return ' '.join(query.split()).casefold() if query else None


def _as_media_ref(media):
    if isinstance(media, MediaRef):
        return media
    if isinstance(media, Mapping):
        return MediaRef.from_meta(media, media.get('content_type') or media.get('type'))
    raise TypeError('A MediaRef or metadata mapping is required')


def favorite_key(media: Union[MediaRef, Mapping]) -> str:
    """Return the configuration-safe, stable key for a movie or show favorite."""
    media = _as_media_ref(media)
    content_type = normalize_content_type(media.content_type)
    if content_type not in ('movie', 'series'):
        raise ValueError('Only movies and shows can be local favorites')
    if media.imdb_id:
        return '{}:imdb:{}'.format(content_type, media.imdb_id.casefold())
    if media.tmdb_id:
        return '{}:tmdb:{}'.format(content_type, media.tmdb_id)
    if not media.origin_fingerprint or not media.metadata_id:
        raise ValueError(
            'An opaque favorite requires both an origin fingerprint and metadata ID'
        )
    return '{}:origin:{}:{}'.format(
        content_type, media.origin_fingerprint, media.metadata_id,
    )


def default_database_path():
    """Resolve the add-on profile database location only when Kodi is present."""
    import xbmcaddon
    import xbmcvfs

    profile_path = xbmcvfs.translatePath(xbmcaddon.Addon().getAddonInfo('profile'))
    return os.path.join(profile_path, DATABASE_FILENAME)


class UserState:
    """SQLite-backed local favorites, recent searches, and preferences."""

    _initialized_paths = set()
    _initialization_lock = threading.Lock()

    def __init__(
        self,
        database_path: Optional[str] = None,
        history_limit: int = DEFAULT_HISTORY_LIMIT,
        clock=None,
        busy_timeout_ms: int = 5000,
    ):
        if history_limit < 1:
            raise ValueError('history_limit must be at least one')
        self.database_path = os.path.abspath(database_path or default_database_path())
        self.history_limit = history_limit
        self._clock = clock or time.time
        self._busy_timeout_ms = busy_timeout_ms
        self._last_timestamp = 0

    def _timestamp(self):
        """Return increasing millisecond timestamps for deterministic ordering."""
        timestamp = int(self._clock() * 1000)
        self._last_timestamp = max(timestamp, self._last_timestamp + 1)
        return self._last_timestamp

    def _connect(self):
        try:
            connection = sqlite3.connect(
                self.database_path,
                timeout=self._busy_timeout_ms / 1000.0,
            )
            connection.row_factory = sqlite3.Row
            connection.execute('PRAGMA foreign_keys = ON')
            connection.execute('PRAGMA busy_timeout = {}'.format(self._busy_timeout_ms))
            return connection
        except (OSError, sqlite3.Error) as error:
            self._raise_database_error('open', error)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self._ensure_initialized()
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except sqlite3.Error as error:
            connection.rollback()
            self._raise_database_error('access', error)
        finally:
            connection.close()

    def _ensure_initialized(self):
        if self.database_path in self._initialized_paths:
            return
        with self._initialization_lock:
            if self.database_path in self._initialized_paths:
                return
            directory = os.path.dirname(self.database_path)
            try:
                if directory:
                    os.makedirs(directory, exist_ok=True)
                with self._connect() as connection:
                    try:
                        # WAL permits a reader to coexist with a writer.  Some
                        # Kodi SQLite builds cannot enable it, so retaining the
                        # default journal mode is an intentional fallback.
                        connection.execute('PRAGMA journal_mode = WAL')
                    except sqlite3.DatabaseError:
                        _log(2, 'WAL unavailable; using SQLite default journal mode')
                    connection.execute('BEGIN IMMEDIATE')
                    self._migrate(connection)
                    connection.commit()
            except (OSError, sqlite3.Error) as error:
                self._raise_database_error('initialize', error)
            self._initialized_paths.add(self.database_path)

    @staticmethod
    def _migrate(connection):
        connection.execute(
            'CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)'
        )
        row = connection.execute('SELECT version FROM schema_version LIMIT 1').fetchone()
        version = row['version'] if row else 0
        if version > SCHEMA_VERSION:
            raise UserStateError('User-state database uses a newer schema version')
        if version < 1:
            connection.execute('''
                CREATE TABLE IF NOT EXISTS search_history (
                    normalized_query TEXT NOT NULL,
                    query TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    last_used_at INTEGER NOT NULL,
                    PRIMARY KEY(normalized_query, content_type)
                )
            ''')
            connection.execute('''
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ''')
            connection.execute('''
                CREATE TABLE IF NOT EXISTS favorites (
                    favorite_key TEXT PRIMARY KEY,
                    content_type TEXT NOT NULL,
                    metadata_id TEXT NOT NULL,
                    playable_id TEXT,
                    imdb_id TEXT,
                    tmdb_id TEXT,
                    title TEXT NOT NULL,
                    year INTEGER,
                    poster TEXT,
                    fanart TEXT,
                    origin_fingerprint TEXT,
                    added_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')
            if row:
                connection.execute('UPDATE schema_version SET version = ?', (1,))
            else:
                connection.execute('INSERT INTO schema_version(version) VALUES (1)')

    def _raise_database_error(self, operation, error):
        _log(3, '{} failed: {}'.format(operation, type(error).__name__))
        raise UserStateError(
            'Could not {} the local user-state database'.format(operation)
        ) from error

    def record_search(self, query, content_type='all'):
        """Record a submitted query, deduplicating it within its search scope."""
        normalized = _normalized_query(query)
        if not normalized:
            return False
        scope = _search_scope(content_type)
        display_query = ' '.join(str(query).strip().split())
        with self._connection() as connection:
            connection.execute('''
                INSERT INTO search_history(normalized_query, query, content_type, last_used_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(normalized_query, content_type) DO UPDATE SET
                    query = excluded.query,
                    last_used_at = excluded.last_used_at
            ''', (normalized, display_query, scope, self._timestamp()))
            connection.execute('''
                DELETE FROM search_history
                WHERE rowid IN (
                    SELECT rowid FROM search_history
                    ORDER BY last_used_at DESC, rowid DESC
                    LIMIT -1 OFFSET ?
                )
            ''', (self.history_limit,))
        return True

    def list_searches(self, limit=None):
        """Return recent searches newest first."""
        if limit is not None and limit < 0:
            raise ValueError('limit cannot be negative')
        query = (
            'SELECT normalized_query, query, content_type, last_used_at '
            'FROM search_history ORDER BY last_used_at DESC, rowid DESC'
        )
        arguments = ()
        if limit is not None:
            query += ' LIMIT ?'
            arguments = (limit,)
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(query, arguments)]

    def remove_search(self, query, content_type='all'):
        """Remove one historical query; return whether a row existed."""
        normalized = _normalized_query(query)
        if not normalized:
            return False
        with self._connection() as connection:
            cursor = connection.execute(
                'DELETE FROM search_history WHERE normalized_query = ? AND content_type = ?',
                (normalized, _search_scope(content_type)),
            )
            return cursor.rowcount > 0

    def clear_searches(self):
        """Clear all search history without affecting favorites or preferences."""
        with self._connection() as connection:
            connection.execute('DELETE FROM search_history')

    def get_last_search_scope(self, default='all'):
        """Return the persisted search scope, or the caller's normalized default."""
        default = _search_scope(default)
        with self._connection() as connection:
            row = connection.execute(
                "SELECT value FROM preferences WHERE key = 'last_search_scope'"
            ).fetchone()
        return _search_scope(row['value']) if row else default

    def set_last_search_scope(self, content_type):
        """Persist the scope selected in the search interface."""
        scope = _search_scope(content_type)
        with self._connection() as connection:
            connection.execute('''
                INSERT INTO preferences(key, value) VALUES ('last_search_scope', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            ''', (scope,))
        return scope

    def add_favorite(self, media: Union[MediaRef, Mapping]):
        """Add or refresh one movie/show snapshot and return its stable key."""
        media = _as_media_ref(media)
        key = favorite_key(media)
        timestamp = self._timestamp()
        with self._connection() as connection:
            connection.execute('''
                INSERT INTO favorites(
                    favorite_key, content_type, metadata_id, playable_id, imdb_id, tmdb_id,
                    title, year, poster, fanart, origin_fingerprint, added_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(favorite_key) DO UPDATE SET
                    content_type = excluded.content_type,
                    metadata_id = excluded.metadata_id,
                    playable_id = excluded.playable_id,
                    imdb_id = excluded.imdb_id,
                    tmdb_id = excluded.tmdb_id,
                    title = excluded.title,
                    year = excluded.year,
                    poster = excluded.poster,
                    fanart = excluded.fanart,
                    origin_fingerprint = excluded.origin_fingerprint,
                    updated_at = excluded.updated_at
            ''', (
                key, normalize_content_type(media.content_type), media.metadata_id,
                media.playable_id, media.imdb_id, media.tmdb_id, media.title, media.year,
                media.poster, media.fanart, media.origin_fingerprint, timestamp, timestamp,
            ))
        return key

    def list_favorites(self, content_type=None):
        """Return favorite snapshots, newest additions first, optionally by type."""
        query = 'SELECT * FROM favorites'
        arguments = ()
        if content_type is not None:
            normalized_type = normalize_content_type(content_type)
            if normalized_type not in ('movie', 'series'):
                raise ValueError('Favorites can only be filtered by movie or series')
            query += ' WHERE content_type = ?'
            arguments = (normalized_type,)
        query += ' ORDER BY added_at DESC, favorite_key ASC'
        with self._connection() as connection:
            return [dict(row) for row in connection.execute(query, arguments)]

    def get_favorite(self, key):
        """Return one stored favorite snapshot, or ``None`` when it is absent."""
        with self._connection() as connection:
            row = connection.execute(
                'SELECT * FROM favorites WHERE favorite_key = ?', (str(key),)
            ).fetchone()
        return dict(row) if row else None

    def is_favorite(self, media_or_key):
        """Check favorite membership by a MediaRef/metadata mapping or stable key."""
        key = (
            favorite_key(media_or_key)
            if isinstance(media_or_key, (MediaRef, Mapping)) else str(media_or_key)
        )
        return self.get_favorite(key) is not None

    def remove_favorite(self, media_or_key):
        """Remove one favorite; return whether a row existed."""
        key = (
            favorite_key(media_or_key)
            if isinstance(media_or_key, (MediaRef, Mapping)) else str(media_or_key)
        )
        with self._connection() as connection:
            cursor = connection.execute('DELETE FROM favorites WHERE favorite_key = ?', (key,))
            return cursor.rowcount > 0

    def clear_favorites(self):
        """Clear favorites without touching history, preferences, cache, or Trakt data."""
        with self._connection() as connection:
            connection.execute('DELETE FROM favorites')
