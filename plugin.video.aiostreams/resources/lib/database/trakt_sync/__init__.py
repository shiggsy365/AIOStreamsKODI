# -*- coding: utf-8 -*-
"""
Trakt sync database for persistent caching of Trakt data.
Stores shows, episodes, movies, and watchlist data with pickle BLOB serialization.
"""
import pickle
import xbmc
from .. import Database


class TraktSyncDatabase(Database):
    """Database for Trakt sync data with pickle BLOB storage."""

    # Table schemas
    SHOWS_SCHEMA = """
        trakt_id INTEGER PRIMARY KEY,
        imdb_id TEXT,
        tvdb_id INTEGER,
        tmdb_id INTEGER,
        slug TEXT,
        title TEXT,
        metadata BLOB,
        last_updated INTEGER
    """

    EPISODES_SCHEMA = """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        show_trakt_id INTEGER,
        season INTEGER,
        episode INTEGER,
        trakt_id INTEGER,
        imdb_id TEXT,
        tmdb_id INTEGER,
        tvdb_id INTEGER,
        metadata BLOB,
        last_updated INTEGER,
        UNIQUE(show_trakt_id, season, episode)
    """

    MOVIES_SCHEMA = """
        trakt_id INTEGER PRIMARY KEY,
        imdb_id TEXT,
        tmdb_id INTEGER,
        slug TEXT,
        title TEXT,
        metadata BLOB,
        last_updated INTEGER
    """

    WATCHLIST_SCHEMA = """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        content_type TEXT,
        trakt_id INTEGER,
        listed_at INTEGER,
        metadata BLOB,
        last_updated INTEGER,
        UNIQUE(content_type, trakt_id)
    """

    def __init__(self):
        """Initialize Trakt sync database."""
        super().__init__('trakt_sync.db')
        self._initialize_tables()

    def _initialize_tables(self):
        """Create all required tables if they don't exist."""
        if not self.connect():
            xbmc.log('[AIOStreams] Failed to connect to Trakt sync database', xbmc.LOGERROR)
            return

        try:
            self.create_table('shows', self.SHOWS_SCHEMA)
            self.create_table('episodes', self.EPISODES_SCHEMA)
            self.create_table('movies', self.MOVIES_SCHEMA)
            self.create_table('watchlist', self.WATCHLIST_SCHEMA)
            self.commit()
            xbmc.log('[AIOStreams] Trakt sync database tables initialized', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error initializing Trakt sync tables: {e}', xbmc.LOGERROR)
            self.rollback()
        finally:
            self.disconnect()

    def insert_show(self, trakt_id, imdb_id, tvdb_id, tmdb_id, slug, title, metadata, last_updated):
        """
        Insert or replace a show in the database.

        Args:
            trakt_id: Trakt ID (primary key)
            imdb_id: IMDB ID
            tvdb_id: TVDB ID
            tmdb_id: TMDB ID
            slug: Trakt slug
            title: Show title
            metadata: Dictionary of show metadata (will be pickled)
            last_updated: Unix timestamp of last update

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connection:
            if not self.connect():
                return False

        try:
            pickled_metadata = pickle.dumps(metadata)
            sql = """
                INSERT OR REPLACE INTO shows 
                (trakt_id, imdb_id, tvdb_id, tmdb_id, slug, title, metadata, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            self.execute(sql, (trakt_id, imdb_id, tvdb_id, tmdb_id, slug, title, pickled_metadata, last_updated))
            return True
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error inserting show {trakt_id}: {e}', xbmc.LOGERROR)
            return False

    def get_show(self, trakt_id):
        """
        Retrieve a show by Trakt ID.

        Args:
            trakt_id: Trakt ID of the show

        Returns:
            dict: Show data with unpickled metadata, or None if not found
        """
        if not self.connection:
            if not self.connect():
                return None

        try:
            sql = "SELECT * FROM shows WHERE trakt_id = ?"
            row = self.fetch_one(sql, (trakt_id,))
            if row:
                return self._unpack_show_row(row)
            return None
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error retrieving show {trakt_id}: {e}', xbmc.LOGERROR)
            return None

    def get_shows(self, limit=None):
        """
        Retrieve all shows or a limited number.

        Args:
            limit: Optional maximum number of shows to retrieve

        Returns:
            list: List of show dictionaries with unpickled metadata
        """
        if not self.connection:
            if not self.connect():
                return []

        try:
            sql = "SELECT * FROM shows ORDER BY last_updated DESC"
            params = None
            if limit:
                sql += " LIMIT ?"
                params = (limit,)
            rows = self.fetch_all(sql, params)
            return [self._unpack_show_row(row) for row in rows]
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error retrieving shows: {e}', xbmc.LOGERROR)
            return []

    def insert_episode(self, show_trakt_id, season, episode, trakt_id, imdb_id, tmdb_id, tvdb_id, metadata, last_updated):
        """
        Insert or replace an episode in the database.

        Args:
            show_trakt_id: Trakt ID of the parent show
            season: Season number
            episode: Episode number
            trakt_id: Episode Trakt ID
            imdb_id: IMDB ID
            tmdb_id: TMDB ID
            tvdb_id: TVDB ID
            metadata: Dictionary of episode metadata (will be pickled)
            last_updated: Unix timestamp of last update

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connection:
            if not self.connect():
                return False

        try:
            pickled_metadata = pickle.dumps(metadata)
            sql = """
                INSERT OR REPLACE INTO episodes 
                (show_trakt_id, season, episode, trakt_id, imdb_id, tmdb_id, tvdb_id, metadata, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            self.execute(sql, (show_trakt_id, season, episode, trakt_id, imdb_id, tmdb_id, tvdb_id, pickled_metadata, last_updated))
            return True
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error inserting episode {show_trakt_id} S{season}E{episode}: {e}', xbmc.LOGERROR)
            return False

    def get_episode(self, show_trakt_id, season, episode):
        """
        Retrieve an episode by show ID, season, and episode number.

        Args:
            show_trakt_id: Trakt ID of the parent show
            season: Season number
            episode: Episode number

        Returns:
            dict: Episode data with unpickled metadata, or None if not found
        """
        if not self.connection:
            if not self.connect():
                return None

        try:
            sql = "SELECT * FROM episodes WHERE show_trakt_id = ? AND season = ? AND episode = ?"
            row = self.fetch_one(sql, (show_trakt_id, season, episode))
            if row:
                return self._unpack_episode_row(row)
            return None
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error retrieving episode {show_trakt_id} S{season}E{episode}: {e}', xbmc.LOGERROR)
            return None

    def get_episodes_for_show(self, show_trakt_id):
        """
        Retrieve all episodes for a show.

        Args:
            show_trakt_id: Trakt ID of the show

        Returns:
            list: List of episode dictionaries with unpickled metadata
        """
        if not self.connection:
            if not self.connect():
                return []

        try:
            sql = "SELECT * FROM episodes WHERE show_trakt_id = ? ORDER BY season, episode"
            rows = self.fetch_all(sql, (show_trakt_id,))
            return [self._unpack_episode_row(row) for row in rows]
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error retrieving episodes for show {show_trakt_id}: {e}', xbmc.LOGERROR)
            return []

    def insert_movie(self, trakt_id, imdb_id, tmdb_id, slug, title, metadata, last_updated):
        """
        Insert or replace a movie in the database.

        Args:
            trakt_id: Trakt ID (primary key)
            imdb_id: IMDB ID
            tmdb_id: TMDB ID
            slug: Trakt slug
            title: Movie title
            metadata: Dictionary of movie metadata (will be pickled)
            last_updated: Unix timestamp of last update

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connection:
            if not self.connect():
                return False

        try:
            pickled_metadata = pickle.dumps(metadata)
            sql = """
                INSERT OR REPLACE INTO movies 
                (trakt_id, imdb_id, tmdb_id, slug, title, metadata, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """
            self.execute(sql, (trakt_id, imdb_id, tmdb_id, slug, title, pickled_metadata, last_updated))
            return True
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error inserting movie {trakt_id}: {e}', xbmc.LOGERROR)
            return False

    def get_movie(self, trakt_id):
        """
        Retrieve a movie by Trakt ID.

        Args:
            trakt_id: Trakt ID of the movie

        Returns:
            dict: Movie data with unpickled metadata, or None if not found
        """
        if not self.connection:
            if not self.connect():
                return None

        try:
            sql = "SELECT * FROM movies WHERE trakt_id = ?"
            row = self.fetch_one(sql, (trakt_id,))
            if row:
                return self._unpack_movie_row(row)
            return None
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error retrieving movie {trakt_id}: {e}', xbmc.LOGERROR)
            return None

    def get_movies(self, limit=None):
        """
        Retrieve all movies or a limited number.

        Args:
            limit: Optional maximum number of movies to retrieve

        Returns:
            list: List of movie dictionaries with unpickled metadata
        """
        if not self.connection:
            if not self.connect():
                return []

        try:
            sql = "SELECT * FROM movies ORDER BY last_updated DESC"
            params = None
            if limit:
                sql += " LIMIT ?"
                params = (limit,)
            rows = self.fetch_all(sql, params)
            return [self._unpack_movie_row(row) for row in rows]
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error retrieving movies: {e}', xbmc.LOGERROR)
            return []

    def insert_watchlist_item(self, content_type, trakt_id, listed_at, metadata, last_updated):
        """
        Insert or replace a watchlist item in the database.

        Args:
            content_type: Type of content ('show' or 'movie')
            trakt_id: Trakt ID of the item
            listed_at: Unix timestamp when item was added to watchlist
            metadata: Dictionary of item metadata (will be pickled)
            last_updated: Unix timestamp of last update

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connection:
            if not self.connect():
                return False

        try:
            pickled_metadata = pickle.dumps(metadata)
            sql = """
                INSERT OR REPLACE INTO watchlist 
                (content_type, trakt_id, listed_at, metadata, last_updated)
                VALUES (?, ?, ?, ?, ?)
            """
            self.execute(sql, (content_type, trakt_id, listed_at, pickled_metadata, last_updated))
            return True
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error inserting watchlist item {content_type}/{trakt_id}: {e}', xbmc.LOGERROR)
            return False

    def get_watchlist_items(self, content_type=None):
        """
        Retrieve watchlist items, optionally filtered by content type.

        Args:
            content_type: Optional content type filter ('show' or 'movie')

        Returns:
            list: List of watchlist item dictionaries with unpickled metadata
        """
        if not self.connection:
            if not self.connect():
                return []

        try:
            if content_type:
                sql = "SELECT * FROM watchlist WHERE content_type = ? ORDER BY listed_at DESC"
                rows = self.fetch_all(sql, (content_type,))
            else:
                sql = "SELECT * FROM watchlist ORDER BY listed_at DESC"
                rows = self.fetch_all(sql)
            return [self._unpack_watchlist_row(row) for row in rows]
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error retrieving watchlist items: {e}', xbmc.LOGERROR)
            return []

    def _unpack_show_row(self, row):
        """Unpack a show database row, deserializing the metadata BLOB."""
        try:
            return {
                'trakt_id': row['trakt_id'],
                'imdb_id': row['imdb_id'],
                'tvdb_id': row['tvdb_id'],
                'tmdb_id': row['tmdb_id'],
                'slug': row['slug'],
                'title': row['title'],
                'metadata': pickle.loads(row['metadata']),
                'last_updated': row['last_updated']
            }
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error unpacking show row: {e}', xbmc.LOGERROR)
            return None

    def _unpack_episode_row(self, row):
        """Unpack an episode database row, deserializing the metadata BLOB."""
        try:
            return {
                'id': row['id'],
                'show_trakt_id': row['show_trakt_id'],
                'season': row['season'],
                'episode': row['episode'],
                'trakt_id': row['trakt_id'],
                'imdb_id': row['imdb_id'],
                'tmdb_id': row['tmdb_id'],
                'tvdb_id': row['tvdb_id'],
                'metadata': pickle.loads(row['metadata']),
                'last_updated': row['last_updated']
            }
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error unpacking episode row: {e}', xbmc.LOGERROR)
            return None

    def _unpack_movie_row(self, row):
        """Unpack a movie database row, deserializing the metadata BLOB."""
        try:
            return {
                'trakt_id': row['trakt_id'],
                'imdb_id': row['imdb_id'],
                'tmdb_id': row['tmdb_id'],
                'slug': row['slug'],
                'title': row['title'],
                'metadata': pickle.loads(row['metadata']),
                'last_updated': row['last_updated']
            }
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error unpacking movie row: {e}', xbmc.LOGERROR)
            return None

    def _unpack_watchlist_row(self, row):
        """Unpack a watchlist database row, deserializing the metadata BLOB."""
        try:
            return {
                'id': row['id'],
                'content_type': row['content_type'],
                'trakt_id': row['trakt_id'],
                'listed_at': row['listed_at'],
                'metadata': pickle.loads(row['metadata']),
                'last_updated': row['last_updated']
            }
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error unpacking watchlist row: {e}', xbmc.LOGERROR)
            return None
