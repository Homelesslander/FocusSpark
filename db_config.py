"""
SQLite Database Configuration for PythonAnywhere
SQLite is free and works perfectly on PythonAnywhere free accounts
"""
import sqlite3
import os
import threading
import time

# Thread-local storage for database connections
_local = threading.local()

def get_db_conn():
    """Get a SQLite database connection with proper locking handling"""
    try:
        # Try multiple possible database paths
        # PRIORITY: Local paths first, then PythonAnywhere
        possible_paths = [
            os.path.join(os.path.dirname(__file__), 'adhd_app.db'),  # Current directory (local)
            'adhd_app.db',                                      # Root fallback (local)
            os.path.expanduser('~/adhd_app.db'),               # Home directory (local)
            '/home/Liam1234/focusspark-app/adhd_app.db',          # PythonAnywhere (last)
        ]
        
        # Try each path until one works
        for db_path in possible_paths:
            try:
                # Enable WAL mode and set timeout for better concurrency
                conn = sqlite3.connect(db_path, timeout=60.0, check_same_thread=False)
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA synchronous=NORMAL')
                conn.execute('PRAGMA cache_size=10000')
                conn.execute('PRAGMA temp_store=MEMORY')
                conn.execute('PRAGMA busy_timeout=60000')  # 60 second busy timeout
                print(f"Connected to database: {db_path}")
                return conn
            except Exception as e:
                # Only print if it's not the "unable to open" error for PythonAnywhere path
                if '/home/Liam1234/' not in db_path or 'unable to open' not in str(e):
                    print(f"Failed to connect to {db_path}: {e}")
                continue
                
        # If all paths fail, raise error
        raise Exception("Could not connect to database from any location")
        
    except Exception as e:
        print(f"Error connecting to SQLite: {e}")
        raise

def dict_cursor_factory(cursor):
    """Convert SQLite cursor results to return dictionaries like MySQL"""
    description = cursor.description
    def make_dict(row):
        return {description[idx][0]: value for idx, value in enumerate(row)}
    return make_dict

class SQLiteCursor:
    """Wrapper to make SQLite cursor behave like MySQL cursor"""
    def __init__(self, cursor):
        self.cursor = cursor
        self.lastrowid = cursor.lastrowid
        
    def execute(self, query, args=()):
        """Execute query - SQLite uses ? placeholders like MySQL"""
        self.cursor.execute(query, args)
        return self
    
    def fetchall(self):
        """Fetch all results as dictionary-like objects"""
        rows = self.cursor.fetchall()
        if not rows:
            return []
        description = self.cursor.description
        return [dict(zip([desc[0] for desc in description], row)) for row in rows]
    
    def fetchone(self):
        """Fetch one result as a dictionary-like object"""
        row = self.cursor.fetchone()
        if not row:
            return None
        description = self.cursor.description
        return dict(zip([desc[0] for desc in description], row))

class SQLiteConnection:
    """Wrapper to make SQLite connection behave like MySQL"""
    def __init__(self, conn):
        self.conn = conn
        self.row_factory = None
        
    def cursor(self):
        """Return a wrapped cursor"""
        return SQLiteCursor(self.conn.cursor())
    
    def commit(self):
        """Commit transaction"""
        self.conn.commit()
    
    def rollback(self):
        """Rollback transaction"""
        self.conn.rollback()
    
    def close(self):
        """Close connection"""
        self.conn.close()

def get_db_conn_wrapped():
    """Get a database connection with MySQL-like interface"""
    sqlite_conn = get_db_conn()
    return SQLiteConnection(sqlite_conn)
