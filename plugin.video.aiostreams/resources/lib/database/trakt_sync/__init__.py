# -*- coding: utf-8 -*-
"""
Trakt sync database for persistent caching of Trakt data.
Stores shows, episodes, movies, and watchlist data with pickle BLOB serialization.

Note: Pickle is used for metadata serialization following Seren's approach.
The metadata comes from Trakt API responses processed by this addon,
not from external untrusted sources. All data is self-generated.
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
        watched_episodes INTEGER DEFAULT 0,
        unwatched_episodes INTEGER DEFAULT 0,
        episode_count INTEGER DEFAULT 0,
        metadata BLOB,
        last_updated TEXT DEFAULT (datetime('now'))
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
        watched INTEGER DEFAULT 0,
        collected INTEGER DEFAULT 0,
        last_watched_at TEXT,
        collected_at TEXT,
        air_date TEXT,
        metadata BLOB,
        last_updated TEXT DEFAULT (datetime('now')),
        UNIQUE(show_trakt_id, season, episode)
    """

    MOVIES_SCHEMA = """
        trakt_id INTEGER PRIMARY KEY,
        imdb_id TEXT,
        tmdb_id INTEGER,
        slug TEXT,
        title TEXT,
        watched INTEGER DEFAULT 0,
        collected INTEGER DEFAULT 0,
        last_watched_at TEXT,
        collected_at TEXT,
        metadata BLOB,
        last_updated TEXT DEFAULT (datetime('now'))
    """

    WATCHLIST_SCHEMA = """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trakt_id INTEGER,
        mediatype TEXT,
        imdb_id TEXT,
        listed_at TEXT,
        last_updated TEXT DEFAULT (datetime('now')),
        UNIQUE(trakt_id, mediatype)
    """

    ACTIVITIES_SCHEMA = """
        sync_id INTEGER PRIMARY KEY DEFAULT 1,
        trakt_username TEXT,
        movies_watched_at TEXT,
        movies_collected_at TEXT,
        movies_watchlist_at TEXT,
        episodes_watched_at TEXT,
        episodes_collected_at TEXT,
        shows_watchlist_at TEXT,
        last_activities_call INTEGER DEFAULT 0,
        all_activities TEXT,
        CHECK (sync_id = 1)
    """

    BOOKMARKS_SCHEMA = """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trakt_id INTEGER,
        type TEXT,
        resume_time REAL,
        percent_played REAL,
        paused_at TEXT,
        last_updated TEXT DEFAULT (datetime('now')),
        UNIQUE(trakt_id, type)
    """

    HIDDEN_SCHEMA = """
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trakt_id INTEGER,
        mediatype TEXT,
        section TEXT,
        last_updated TEXT DEFAULT (datetime('now')),
        UNIQUE(trakt_id, mediatype, section)
    """

    def __init__(self):
        """Initialize Trakt sync database."""
        super().__init__('trakt_sync.db')
        self._initialize_tables()
        self._run_migrations()

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
            self.create_table('activities', self.ACTIVITIES_SCHEMA)
            self.create_table('bookmarks', self.BOOKMARKS_SCHEMA)
            self.create_table('hidden', self.HIDDEN_SCHEMA)
            self.commit()
            xbmc.log('[AIOStreams] Trakt sync database tables initialized', xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error initializing Trakt sync tables: {e}', xbmc.LOGERROR)
            self.rollback()
        finally:
            self.disconnect()

    def _run_migrations(self):
        """Run database schema migrations for existing databases."""
        if not self.connect():
            return

        try:
            # Migration: Add air_date column to episodes table (v3.1.0)
            # Check if column exists first to avoid error logging
            cursor = self.execute("PRAGMA table_info(episodes)")
            if cursor:
                columns = [row[1] for row in cursor.fetchall()]

                if 'air_date' not in columns:
                    self.execute("ALTER TABLE episodes ADD COLUMN air_date TEXT")
                    self.commit()
                    xbmc.log('[AIOStreams] Added air_date column to episodes table', xbmc.LOGINFO)
                else:
                    xbmc.log('[AIOStreams] air_date column already exists, skipping migration', xbmc.LOGDEBUG)

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error running migrations: {e}', xbmc.LOGERROR)
        finally:
            self.disconnect()

    def get_next_up_episodes(self):
        """Get next unwatched episode for each show with watch history.

        Pure SQL calculation inspired by Seren - no API calls needed.
        Returns one episode per show that should be watched next.

        Returns:
            list: List of dicts with show and episode data
        """
        import datetime

        now = datetime.datetime.utcnow().isoformat()

        query = f"""
            WITH max_watched AS (
                -- Find the maximum watched season and episode number for each show
                SELECT
                    show_trakt_id,
                    MAX(season) as max_season,
                    MAX(CASE WHEN season = (SELECT MAX(season) FROM episodes e2 WHERE e2.show_trakt_id = e.show_trakt_id AND e2.watched = 1)
                        THEN episode ELSE 0 END) as max_episode,
                    MAX(last_watched_at) as last_watched_at
                FROM episodes e
                WHERE watched = 1 AND season > 0
                GROUP BY show_trakt_id
            ),
            next_episode_candidate AS (
                -- Find the next unwatched episode after the last watched one
                SELECT
                    e.show_trakt_id,
                    MIN(e.season) as next_season,
                    MIN(e.episode) as next_episode
                FROM episodes e
                INNER JOIN max_watched mw ON e.show_trakt_id = mw.show_trakt_id
                WHERE e.season > 0
                    AND e.watched = 0
                    AND (
                        -- Next episode in the same season
                        (e.season = mw.max_season AND e.episode > mw.max_episode)
                        -- OR first episode of next season
                        OR (e.season > mw.max_season)
                    )
                    -- Only aired episodes
                    AND datetime(e.air_date) < datetime('{now}')
                GROUP BY e.show_trakt_id
            )
            SELECT
                s.trakt_id as show_trakt_id,
                s.imdb_id as show_imdb_id,
                s.title as show_title,
                e.trakt_id as episode_trakt_id,
                e.season,
                e.episode,
                e.air_date,
                e.imdb_id as episode_imdb_id,
                mw.last_watched_at
            FROM next_episode_candidate nec
            INNER JOIN episodes e
                ON e.show_trakt_id = nec.show_trakt_id
                AND e.season = nec.next_season
                AND e.episode = nec.next_episode
            INNER JOIN shows s ON s.trakt_id = e.show_trakt_id
            INNER JOIN max_watched mw ON mw.show_trakt_id = e.show_trakt_id
            WHERE e.show_trakt_id NOT IN (
                SELECT trakt_id FROM hidden WHERE section = 'progress_watched'
            )
            ORDER BY mw.last_watched_at DESC
        """

        try:
            if not self.connect():
                return []

            cursor = self.execute(query)
            if not cursor:
                return []

            results = []
            for row in cursor.fetchall():
                results.append(dict(row))

            self.disconnect()
            return results

        except Exception as e:
            xbmc.log(f'[AIOStreams] Error getting next up episodes: {e}', xbmc.LOGERROR)
            if self.connection:
                self.disconnect()
            return []

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

    def add_hidden_item(self, trakt_id, mediatype, section):
        """
        Add an item to the hidden table.

        Args:
            trakt_id: Trakt ID of the item to hide
            mediatype: Media type ('movie', 'show', 'series')
            section: Hidden section ('progress_watched', 'calendar', 'recommendations')

        Returns:
            bool: True if successful, False otherwise
        """
        # Normalize mediatype
        if mediatype in ['series', 'shows']:
            mediatype = 'show'
        elif mediatype == 'movies':
            mediatype = 'movie'

        if not self.connect():
            return False

        try:
            sql = """
                INSERT OR IGNORE INTO hidden (trakt_id, mediatype, section)
                VALUES (?, ?, ?)
            """
            self.execute(sql, (trakt_id, mediatype, section))
            self.commit()
            xbmc.log(f'[AIOStreams] Added {mediatype} {trakt_id} to hidden/{section}', xbmc.LOGDEBUG)
            return True
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error adding hidden item {trakt_id}: {e}', xbmc.LOGERROR)
            return False
        finally:
            self.disconnect()

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
                'trakt_id': row['trakt_id'],
                'mediatype': row['mediatype'],
                'imdb_id': row['imdb_id'],
                'listed_at': row['listed_at'],
                'last_updated': row['last_updated']
            }
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error unpacking watchlist row: {e}', xbmc.LOGERROR)
            return None

    def execute_sql(self, sql, params=None):
        """Execute SQL with connection management for activities sync.
        
        Args:
            sql: SQL statement to execute
            params: Optional tuple of parameters
        
        Returns:
            bool: True if successful, False otherwise
        """
        connected = False
        if not self.connection:
            if not self.connect():
                return False
            connected = True
        
        try:
            cursor = self.execute(sql, params)
            if cursor is not None:
                self.commit()
                return True
            return False
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error executing SQL: {e}', xbmc.LOGERROR)
            self.rollback()
            return False
        finally:
            if connected:
                self.disconnect()

    def fetchone(self, sql, params=None):
        """Fetch one row with connection management.
        
        Args:
            sql: SQL query
            params: Optional tuple of parameters
        
        Returns:
            dict: Row as dictionary, or None
        """
        connected = False
        if not self.connection:
            if not self.connect():
                return None
            connected = True
        
        try:
            row = self.fetch_one(sql, params)
            if row:
                # Convert sqlite3.Row to dict
                return dict(row)
            return None
        finally:
            if connected:
                self.disconnect()

    def fetchall(self, sql, params=None):
        """Fetch all rows with connection management.
        
        Args:
            sql: SQL query
            params: Optional tuple of parameters
        
        Returns:
            list: List of rows as dictionaries
        """
        connected = False
        if not self.connection:
            if not self.connect():
                return []
            connected = True
        
        try:
            rows = self.fetch_all(sql, params)
            # Convert sqlite3.Row objects to dicts
            return [dict(row) for row in rows]
        finally:
            if connected:
                self.disconnect()
