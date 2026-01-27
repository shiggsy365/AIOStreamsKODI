# -*- coding: utf-8 -*-
"""
Trakt sync database for persistent caching of Trakt data.
Stores shows, episodes, movies, and watchlist data with pickle BLOB serialization.

Note: Pickle is used for metadata serialization following Seren's approach.
The metadata comes from Trakt API responses processed by this addon,
not from external untrusted sources. All data is self-generated.
"""
import pickle
import time
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
        metadata BLOB,
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
        tvdb_id INTEGER,
        tmdb_id INTEGER,
        imdb_id TEXT,
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

    METAS_SCHEMA = """
        id TEXT PRIMARY KEY,
        content_type TEXT,
        metadata BLOB,
        expires INTEGER
    """

    CATALOGS_SCHEMA = """
        id TEXT PRIMARY KEY,
        content_type TEXT,
        catalog_id TEXT,
        genre TEXT,
        skip INTEGER,
        data BLOB,
        expires INTEGER
    """

    def clear_all_trakt_data(self):
        """Truncate all Trakt-related tables for a fresh sync."""
        if not self.connection and not self.connect():
            return False
            
        tables = ['shows', 'episodes', 'movies', 'bookmarks', 'activities', 'watchlist']
        try:
            for table in tables:
                self.execute(f"DELETE FROM {table}")
            self.connection.commit()
            xbmc.log('[AIOStreams] All Trakt sync tables cleared successfully', xbmc.LOGDEBUG)
            return True
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error clearing Trakt tables: {e}', xbmc.LOGERROR)
            return False

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
            self.create_table('metas', self.METAS_SCHEMA)
            self.create_table('catalogs', self.CATALOGS_SCHEMA)
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
            # Migration: Add tvdb_id, tmdb_id, imdb_id to bookmarks table
            # Check if columns exist
            cursor = self.execute("PRAGMA table_info(bookmarks)")
            if cursor:
                columns = [row[1] for row in cursor.fetchall()]
                
                if 'tvdb_id' not in columns:
                    xbmc.log('[AIOStreams] Migrating bookmarks table: adding tvdb_id column', xbmc.LOGDEBUG)
                    self.execute("ALTER TABLE bookmarks ADD COLUMN tvdb_id INTEGER")
                
                if 'tmdb_id' not in columns:
                    xbmc.log('[AIOStreams] Migrating bookmarks table: adding tmdb_id column', xbmc.LOGDEBUG)
                    self.execute("ALTER TABLE bookmarks ADD COLUMN tmdb_id INTEGER")
                
                if 'imdb_id' not in columns:
                    xbmc.log('[AIOStreams] Migrating bookmarks table: adding imdb_id column', xbmc.LOGDEBUG)
                    self.execute("ALTER TABLE bookmarks ADD COLUMN imdb_id TEXT")
                
                self.commit()

            # Migration: Add air_date column to episodes table (v3.1.0)
            # Check if column exists first to avoid error logging
            cursor = self.execute("PRAGMA table_info(episodes)")
            if cursor:
                columns = [row[1] for row in cursor.fetchall()]

                if 'air_date' not in columns:
                    self.execute("ALTER TABLE episodes ADD COLUMN air_date TEXT")
                    self.commit()
                    xbmc.log('[AIOStreams] Added air_date column to episodes table', xbmc.LOGDEBUG)
                else:
                    xbmc.log('[AIOStreams] air_date column already exists, skipping migration', xbmc.LOGDEBUG)

                # Migration: Add metadata column to watchlist table
                cursor = self.execute("PRAGMA table_info(watchlist)")
                if cursor:
                    columns = [row[1] for row in cursor.fetchall()]
                    if 'metadata' not in columns:
                        self.execute("ALTER TABLE watchlist ADD COLUMN metadata BLOB")
                        self.commit()
                        xbmc.log('[AIOStreams] Added metadata column to watchlist table', xbmc.LOGDEBUG)

                # Migration: Add metas and catalogs tables if they don't exist (v3.2.0)
                self.create_table('metas', self.METAS_SCHEMA)
                self.create_table('catalogs', self.CATALOGS_SCHEMA)
                self.commit()

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
                -- Uses ROW_NUMBER to correctly get the first episode by season+episode order
                SELECT
                    show_trakt_id,
                    season as next_season,
                    episode as next_episode
                FROM (
                    SELECT
                        e.show_trakt_id,
                        e.season,
                        e.episode,
                        ROW_NUMBER() OVER (PARTITION BY e.show_trakt_id ORDER BY e.season, e.episode) as rn
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
                )
                WHERE rn = 1
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
                e.metadata as episode_metadata,
                mw.last_watched_at,
                s.metadata as show_metadata,
                b.percent_played,
                b.resume_time
            FROM next_episode_candidate nec
            INNER JOIN episodes e
                ON e.show_trakt_id = nec.show_trakt_id
                AND e.season = nec.next_season
                AND e.episode = nec.next_episode
            INNER JOIN shows s ON s.trakt_id = e.show_trakt_id
            INNER JOIN max_watched mw ON mw.show_trakt_id = e.show_trakt_id
            LEFT JOIN bookmarks b ON (
                (b.trakt_id = e.trakt_id OR 
                 (b.tvdb_id IS NOT NULL AND b.tvdb_id = e.tvdb_id) OR 
                 (b.tmdb_id IS NOT NULL AND b.tmdb_id = e.tmdb_id) OR 
                 (b.imdb_id IS NOT NULL AND b.imdb_id = e.imdb_id))
                AND b.type = 'episode'
            )
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
                row_dict = dict(row)
                # Unpickle show metadata
                if row_dict.get('show_metadata'):
                    try:
                        row_dict['show_metadata'] = pickle.loads(row_dict['show_metadata'])
                    except:
                        row_dict['show_metadata'] = None
                # Unpickle episode metadata
                if row_dict.get('episode_metadata'):
                    try:
                        row_dict['episode_metadata'] = pickle.loads(row_dict['episode_metadata'])
                    except:
                        row_dict['episode_metadata'] = None
                results.append(row_dict)

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
            if isinstance(trakt_id, str) and trakt_id.startswith('tt'):
                sql = "SELECT * FROM shows WHERE imdb_id = ?"
            else:
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
            if isinstance(trakt_id, str) and trakt_id.startswith('tt'):
                sql = "SELECT * FROM movies WHERE imdb_id = ?"
            else:
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
                sql = "SELECT * FROM watchlist WHERE mediatype = ? ORDER BY listed_at DESC"
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
                'metadata': pickle.loads(row['metadata']) if row['metadata'] else {},
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
                'metadata': pickle.loads(row['metadata']) if row['metadata'] else {},
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
                'last_updated': row['last_updated'],
                'metadata': pickle.loads(row['metadata']) if ('metadata' in row.keys() and row['metadata']) else None
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

    def execute_sql_batch(self, sql, params_list):
        """Execute batch SQL with connection management.
        
        Args:
            sql: SQL statement to execute
            params_list: List of parameter tuples
        
        Returns:
            bool: True if successful, False otherwise
        """
        connected = False
        if not self.connection:
            if not self.connect():
                return False
            connected = True
        
        try:
            cursor = self.executemany(sql, params_list)
            if cursor is not None:
                self.commit()
                return True
            return False
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error executing batch SQL: {e}', xbmc.LOGERROR)
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
            
            # Debug: Check if JOIN is working and if percent_played is populated
            if rows:
                xbmc.log(f'[AIOStreams] fetchall: Retrieved {len(rows)} results for query: {sql}', xbmc.LOGDEBUG)
                # Check first result for bookmark data if relevant columns exist
                first = rows[0]
                if 'show_trakt_id' in first and 'episode_trakt_id' in first and 'percent_played' in first:
                    xbmc.log(f'[AIOStreams] First result: show_trakt_id={first.get("show_trakt_id")}, episode_trakt_id={first.get("episode_trakt_id")}, percent_played={first.get("percent_played")}, resume_time={first.get("resume_time")}', xbmc.LOGDEBUG)
                    
                    # Check if ANY results have bookmark data
                    with_progress = [r for r in rows if r.get('percent_played') is not None]
                    xbmc.log(f'[AIOStreams] Results with progress: {len(with_progress)} out of {len(rows)}', xbmc.LOGDEBUG)
                    
                    # Query bookmarks table directly to verify data exists
                    # This assumes 'fetchall' is being called in a context where episode bookmarks are relevant.
                    # If this is a generic fetchall, this specific check might be too narrow.
                    # For now, keeping it as per instruction, assuming it's for a specific use case.
                    all_bookmarks = self.fetch_all("SELECT trakt_id, tvdb_id, tmdb_id, imdb_id, percent_played FROM bookmarks WHERE type='episode'")
                    xbmc.log(f'[AIOStreams] Total episode bookmarks in DB: {len(all_bookmarks) if all_bookmarks else 0}', xbmc.LOGDEBUG)
                    if all_bookmarks and len(all_bookmarks) > 0:
                        xbmc.log(f'[AIOStreams] Sample bookmark: {all_bookmarks[0]}', xbmc.LOGDEBUG)
            
            # Convert sqlite3.Row objects to dicts
            return [dict(row) for row in rows]
        finally:
            if connected:
                self.disconnect()

    def get_meta(self, content_type, meta_id):
        """Get metadata from the SQL cache."""
        if not self.connection and not self.connect():
            return None
        try:
            sql = "SELECT metadata FROM metas WHERE id=? AND content_type=? AND expires > ?"
            row = self.fetch_one(sql, (meta_id, content_type, int(time.time())))
            if row and row['metadata']:
                return pickle.loads(row['metadata'])
            return None
        except Exception as e:
            xbmc.log(f'[AIOStreams] DB error getting meta: {e}', xbmc.LOGWARNING)
            return None

    def set_meta(self, content_type, meta_id, metadata, ttl_seconds):
        """Store metadata in the SQL cache."""
        if not self.connection and not self.connect():
            return False
        try:
            expires = int(time.time()) + ttl_seconds
            pickled_metadata = pickle.dumps(metadata)
            sql = "INSERT OR REPLACE INTO metas (id, content_type, metadata, expires) VALUES (?, ?, ?, ?)"
            self.execute(sql, (meta_id, content_type, pickled_metadata, expires))
            self.commit()
            return True
        except Exception as e:
            xbmc.log(f'[AIOStreams] DB error setting meta: {e}', xbmc.LOGWARNING)
            return False

    def get_catalog(self, content_type, catalog_id, genre=None, skip=0):
        """Get catalog data from the SQL cache."""
        if not self.connection and not self.connect():
            return None
        try:
            sql = "SELECT data FROM catalogs WHERE catalog_id=? AND content_type=? AND (genre=? OR (genre IS NULL AND ? IS NULL)) AND skip=? AND expires > ?"
            row = self.fetch_one(sql, (catalog_id, content_type, genre, genre, skip, int(time.time())))
            if row and row['data']:
                return pickle.loads(row['data'])
            return None
        except Exception as e:
            xbmc.log(f'[AIOStreams] DB error getting catalog: {e}', xbmc.LOGWARNING)
            return None

    def set_catalog(self, content_type, catalog_id, genre, skip, data, ttl_seconds):
        """Store catalog data in the SQL cache."""
        if not self.connection and not self.connect():
            return False
        try:
            expires = int(time.time()) + ttl_seconds
            pickled_data = pickle.dumps(data)
            # Use unique key for catalogs: content_type:catalog_id:genre:skip
            cache_id = f"{content_type}:{catalog_id}:{genre or 'none'}:{skip}"
            sql = "INSERT OR REPLACE INTO catalogs (id, content_type, catalog_id, genre, skip, data, expires) VALUES (?, ?, ?, ?, ?, ?, ?)"
            self.execute(sql, (cache_id, content_type, catalog_id, genre, skip, pickled_data, expires))
            self.commit()
            return True
        except Exception as e:
            xbmc.log(f'[AIOStreams] DB error setting catalog: {e}', xbmc.LOGWARNING)
            return False

    def cleanup_cached_data(self):
        """Remove expired metadata and catalog entries from the database."""
        if not self.connection and not self.connect():
            return False
        try:
            now = int(time.time())
            
            # Delete expired metas
            cursor_meta = self.execute("DELETE FROM metas WHERE expires < ?", (now,))
            meta_count = cursor_meta.rowcount if cursor_meta else 0
            
            # Delete expired catalogs
            cursor_catalog = self.execute("DELETE FROM catalogs WHERE expires < ?", (now,))
            catalog_count = cursor_catalog.rowcount if cursor_catalog else 0
            
            self.commit()
            
            if meta_count > 0 or catalog_count > 0:
                xbmc.log(f'[AIOStreams] SQL Cache cleanup: removed {meta_count} metas and {catalog_count} catalogs', xbmc.LOGDEBUG)
            return True
        except Exception as e:
            xbmc.log(f'[AIOStreams] DB error during cache cleanup: {e}', xbmc.LOGWARNING)
            return False
    def get_trakt_id_for_item(self, imdb_id, mediatype):
        """Retrieve Trakt ID for an item by its IMDB ID."""
        if not self.connection and not self.connect():
            return None
        try:
            table = 'movies' if mediatype == 'movie' else 'shows'
            sql = f"SELECT trakt_id FROM {table} WHERE imdb_id = ?"
            # Use safe wrapper that handles connection/disconnection
            row = self.fetchone(sql, (imdb_id,))
            return row['trakt_id'] if row else None
        except Exception as e:
            xbmc.log(f'[AIOStreams] DB error getting trakt_id: {e}', xbmc.LOGWARNING)
            return None

    def get_bookmark(self, trakt_id=None, tvdb_id=None, tmdb_id=None, imdb_id=None):
        """Retrieve playback bookmark for an item using any available ID."""
        if not self.connection and not self.connect():
            return None
        try:
            # Try matching on any available ID
            sql_parts = []
            params = []
            
            if trakt_id:
                sql_parts.append("trakt_id = ?")
                params.append(trakt_id)
            if tvdb_id:
                sql_parts.append("tvdb_id = ?")
                params.append(tvdb_id)
            if tmdb_id:
                sql_parts.append("tmdb_id = ?")
                params.append(tmdb_id)
            if imdb_id:
                sql_parts.append("imdb_id = ?")
                params.append(imdb_id)
            
            if not sql_parts:
                return None
            
            sql = f"SELECT resume_time, percent_played FROM bookmarks WHERE ({' OR '.join(sql_parts)})"
            # Use safe wrapper that handles connection/disconnection
            return self.fetchone(sql, tuple(params))
        except Exception as e:
            xbmc.log(f'[AIOStreams] DB error getting bookmark: {e}', xbmc.LOGWARNING)
            return None

    def is_item_watched(self, trakt_id, mediatype, season=None, episode=None):
        """Check if an item is marked as watched."""
    def is_item_watched(self, trakt_id, mediatype, season=None, episode=None):
        """Check if an item is marked as watched."""
        if not self.connection and not self.connect():
            return False
        try:
            if mediatype == 'movie':
                sql = "SELECT watched FROM movies WHERE trakt_id = ?"
                # Use safe wrapper that handles connection/disconnection
                row = self.fetchone(sql, (trakt_id,))
                return bool(row and row['watched'])
            elif mediatype == 'episode':
                sql = "SELECT watched FROM episodes WHERE show_trakt_id = ? AND season = ? AND episode = ?"
                row = self.fetchone(sql, (trakt_id, season, episode))
                return bool(row and row['watched'])
            elif mediatype in ['series', 'tvshow']:
                # Use refined show statistics from the shows table
                # These are updated in activities.py and account for all aired episodes via metadata
                sql = "SELECT watched_episodes, unwatched_episodes FROM shows WHERE trakt_id = ?"
                row = self.fetchone(sql, (trakt_id,))
                # Considered watched if we have at least one watched episode and NO unwatched ones
                return bool(row and row['watched_episodes'] > 0 and row['unwatched_episodes'] == 0)
            elif mediatype == 'season':
                if season == 0: return False # Specials are optional
                # Check episodes for this specific season
                sql = "SELECT COUNT(*) as unwatched FROM episodes WHERE show_trakt_id = ? AND season = ? AND watched = 0"
                row = self.fetchone(sql, (trakt_id, season))
                if not row or row['unwatched'] > 0:
                    return False
                # Ensure there's actually at least one watched episode (to avoid empty seasons)
                sql = "SELECT COUNT(*) as watched FROM episodes WHERE show_trakt_id = ? AND season = ? AND watched = 1"
                row = self.fetchone(sql, (trakt_id, season))
                return bool(row and row['watched'] > 0)
            return False
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error checking IMDb watched status: {e}', xbmc.LOGERROR)
            return False

    def is_imdb_watched(self, imdb_id, mediatype):
        """Check if item is watched by IMDB ID directly from local DB."""
        if not imdb_id:
            return False
            
        try:
            # Ensure connection
            if not self.connection:
                if not self.connect():
                    return False

            if mediatype == 'movie':
                # Check movies table
                # Use safe wrapper that handles connection/disconnection
                row = self.fetchone("SELECT watched FROM movies WHERE imdb_id = ?", (imdb_id,))
                is_watched = bool(row and row['watched'])
                # xbmc.log(f'[AIOStreams] DB Check Movie {imdb_id}: {is_watched}', xbmc.LOGDEBUG)
                return is_watched
                
            elif mediatype in ['show', 'series', 'tvshow']:
                # For shows, we need to check if all aired episodes are watched
                # First get the show's Trakt ID
                row = self.fetchone("SELECT trakt_id FROM shows WHERE imdb_id = ?", (imdb_id,))
                if not row:
                    # xbmc.log(f'[AIOStreams] DB Check Show {imdb_id}: Show not found in DB', xbmc.LOGDEBUG)
                    return False
                
                trakt_id = row['trakt_id']
                
                # Count total and watched episodes
                stats = self.fetchone("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN watched = 1 THEN 1 ELSE 0 END) as watched_count
                    FROM episodes 
                    WHERE show_trakt_id = ? AND air_date <= datetime('now')
                """, (trakt_id,))
                
                if not stats or stats['total'] == 0:
                    # xbmc.log(f'[AIOStreams] DB Check Show {imdb_id}: No episodes found', xbmc.LOGDEBUG)
                    return False
                    
                is_watched = stats['watched_count'] >= stats['total']
                # xbmc.log(f'[AIOStreams] DB Check Show {imdb_id}: {stats["watched_count"]}/{stats["total"]} episodes watched -> {is_watched}', xbmc.LOGDEBUG)
                return is_watched
                
            elif mediatype == 'episode':
                # Check specific episode
                row = self.fetchone("SELECT watched FROM episodes WHERE imdb_id = ?", (imdb_id,))
                is_watched = bool(row and row['watched'])
                # xbmc.log(f'[AIOStreams] DB Check Episode {imdb_id}: {is_watched}', xbmc.LOGDEBUG)
                return is_watched
                
            return False
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error checking IMDb watched status: {e}', xbmc.LOGERROR)
            return False

    def get_imdb_show_progress(self, imdb_id):
        """Get show progress (aired, completed) by IMDB ID directly from local DB."""
        if not imdb_id:
            return None
            
        try:
            # Ensure connection
            if not self.connection:
                if not self.connect():
                    return None

            # First get the show's Trakt ID
            # Use safe wrapper that handles connection/disconnection
            row = self.fetchone("SELECT trakt_id FROM shows WHERE imdb_id = ?", (imdb_id,))
            if not row:
                return None
            
            trakt_id = row['trakt_id']
            
            # Count total and watched episodes (only aired ones)
            stats = self.fetchone("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN watched = 1 THEN 1 ELSE 0 END) as watched_count
                FROM episodes 
                WHERE show_trakt_id = ? AND air_date <= datetime('now')
            """, (trakt_id,))
            
            if not stats:
                return {'aired': 0, 'completed': 0}
                
            return {
                'aired': stats['total'],
                'completed': stats['watched_count'] or 0
            }
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error getting IMDb show progress: {e}', xbmc.LOGERROR)
            return None

    def is_imdb_in_watchlist(self, imdb_id, mediatype):
        """Check if item is in watchlist by IMDB ID directly from local DB."""
        if not imdb_id:
            return False
            
        try:
            # Ensure connection
            if not self.connection:
                if not self.connect():
                    return False

            # 1. Get Trakt ID from local movies/shows table
            trakt_id = self.get_trakt_id_for_item(imdb_id, mediatype)
            if not trakt_id:
                return False

            # 2. Check watchlist table
            # mediatype in watchlist is usually 'movie' or 'show' (singular)
            # Normalize mediatype
            formatted_type = 'movie' if mediatype == 'movie' else 'show'
            
            sql = "SELECT 1 FROM watchlist WHERE trakt_id = ? AND mediatype = ?"
            # Use safe wrapper that handles connection/disconnection
            row = self.fetchone(sql, (trakt_id, formatted_type))
            return bool(row)
            
        except Exception as e:
            xbmc.log(f'[AIOStreams] Error checking IMDb watchlist status: {e}', xbmc.LOGERROR)
            return False
