# -*- coding: utf-8 -*-
"""
Base database infrastructure for AIOStreams.
Provides SQLite connection management, schema-based table creation, and transaction support.
"""
import os
import sqlite3
import xbmc
import xbmcvfs


class Database:
    """Base class for SQLite database operations with Kodi integration."""

    def __init__(self, db_name):
        """
        Initialize database connection.

        Args:
            db_name: Name of the database file (e.g., 'trakt_sync.db')
        """
        self.db_name = db_name
        self.db_path = self._get_db_path()
        self.connection = None
        self._ensure_db_directory()

    def _get_db_path(self):
        """Get the full path to the database file in the addon profile directory."""
        profile_path = xbmcvfs.translatePath(
            'special://profile/addon_data/plugin.video.aiostreams/'
        )
        return os.path.join(profile_path, self.db_name)

    def _ensure_db_directory(self):
        """Ensure the addon_data directory exists."""
        db_dir = os.path.dirname(self.db_path)
        if not xbmcvfs.exists(db_dir):
            xbmcvfs.mkdirs(db_dir)
            xbmc.log(f'[AIOStreams] Created database directory: {db_dir}', xbmc.LOGDEBUG)

    def connect(self):
        """
        Establish connection to the SQLite database with WAL mode for concurrent access.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Connect with timeout to handle concurrent access
            self.connection = sqlite3.connect(
                self.db_path,
                timeout=10.0,  # 10 second timeout for lock contention
                check_same_thread=False  # Allow multi-threaded access
            )
            self.connection.row_factory = sqlite3.Row  # Enable dict-like row access

            # Enable WAL mode for concurrent read/write support
            # This prevents "database is locked" errors when service + UI access simultaneously
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.execute("PRAGMA synchronous=NORMAL")  # Faster than FULL, safe with WAL
            self.connection.execute("PRAGMA cache_size=-64000")   # 64MB cache for better performance
            self.connection.execute("PRAGMA temp_store=MEMORY")   # Store temp tables in memory

            xbmc.log(f'[AIOStreams] Connected to database (WAL mode): {self.db_path}', xbmc.LOGDEBUG)
            return True
        except sqlite3.Error as e:
            xbmc.log(f'[AIOStreams] Database connection error: {e}', xbmc.LOGERROR)
            return False

    def disconnect(self):
        """Close the database connection."""
        if self.connection:
            try:
                self.connection.close()
                self.connection = None
                xbmc.log(f'[AIOStreams] Disconnected from database: {self.db_path}', xbmc.LOGDEBUG)
            except sqlite3.Error as e:
                xbmc.log(f'[AIOStreams] Error closing database: {e}', xbmc.LOGERROR)

    def create_table(self, table_name, schema):
        """
        Create a table if it doesn't exist.

        Args:
            table_name: Name of the table
            schema: SQL schema definition (without CREATE TABLE part)

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connection:
            xbmc.log('[AIOStreams] No database connection', xbmc.LOGERROR)
            return False

        try:
            sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({schema})"
            self.connection.execute(sql)
            xbmc.log(f'[AIOStreams] Table created/verified: {table_name}', xbmc.LOGDEBUG)
            return True
        except sqlite3.Error as e:
            xbmc.log(f'[AIOStreams] Error creating table {table_name}: {e}', xbmc.LOGERROR)
            return False

    def execute(self, sql, params=None):
        """
        Execute a SQL statement.

        Args:
            sql: SQL statement to execute
            params: Optional tuple/dict of parameters for the SQL statement

        Returns:
            sqlite3.Cursor or None: Cursor object if successful, None otherwise
        """
        if not self.connection:
            xbmc.log('[AIOStreams] No database connection', xbmc.LOGERROR)
            return None

        try:
            if params:
                cursor = self.connection.execute(sql, params)
            else:
                cursor = self.connection.execute(sql)
            return cursor
        except sqlite3.Error as e:
            xbmc.log(f'[AIOStreams] SQL execution error: {e}', xbmc.LOGERROR)
            xbmc.log(f'[AIOStreams] SQL: {sql}', xbmc.LOGDEBUG)
            if params:
                xbmc.log(f'[AIOStreams] Params: {params}', xbmc.LOGDEBUG)
            return None

    def executemany(self, sql, params_list):
        """
        Execute a SQL statement against multiple parameter sets.

        Args:
            sql: SQL statement to execute
            params_list: List of tuples/dicts parameters

        Returns:
            sqlite3.Cursor or None: Cursor object if successful, None otherwise
        """
        if not self.connection:
            xbmc.log('[AIOStreams] No database connection', xbmc.LOGERROR)
            return None

        try:
            cursor = self.connection.executemany(sql, params_list)
            return cursor
        except sqlite3.Error as e:
            xbmc.log(f'[AIOStreams] SQL batch execution error: {e}', xbmc.LOGERROR)
            xbmc.log(f'[AIOStreams] SQL: {sql}', xbmc.LOGDEBUG)
            return None

    def fetch_one(self, sql, params=None):
        """
        Execute a SQL query and fetch one result.

        Args:
            sql: SQL query to execute
            params: Optional tuple/dict of parameters

        Returns:
            sqlite3.Row or None: Single result row or None
        """
        cursor = self.execute(sql, params)
        if cursor:
            return cursor.fetchone()
        return None

    def fetch_all(self, sql, params=None):
        """
        Execute a SQL query and fetch all results.

        Args:
            sql: SQL query to execute
            params: Optional tuple/dict of parameters

        Returns:
            list: List of sqlite3.Row objects, empty list on error
        """
        cursor = self.execute(sql, params)
        if cursor:
            return cursor.fetchall()
        return []

    def commit(self):
        """
        Commit the current transaction.

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connection:
            xbmc.log('[AIOStreams] No database connection', xbmc.LOGERROR)
            return False

        try:
            self.connection.commit()
            return True
        except sqlite3.Error as e:
            xbmc.log(f'[AIOStreams] Commit error: {e}', xbmc.LOGERROR)
            return False

    def rollback(self):
        """
        Rollback the current transaction.

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.connection:
            xbmc.log('[AIOStreams] No database connection', xbmc.LOGERROR)
            return False

        try:
            self.connection.rollback()
            xbmc.log('[AIOStreams] Transaction rolled back', xbmc.LOGDEBUG)
            return True
        except sqlite3.Error as e:
            xbmc.log(f'[AIOStreams] Rollback error: {e}', xbmc.LOGERROR)
            return False

    def __enter__(self):
        """Context manager entry - establish connection."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - handle transaction and close connection."""
        if exc_type is not None:
            # Exception occurred, rollback
            self.rollback()
        else:
            # No exception, commit
            self.commit()
        self.disconnect()
        return False  # Don't suppress exceptions
