"""
MySQL Database Configuration
Update these credentials with your MySQL information

LOCAL SETUP (for testing):
1. Install MySQL Community Server from https://dev.mysql.com/downloads/mysql/
2. During installation, set:
   - Port: 3306 (default)
   - Root password: something you remember
3. Open MySQL Command Line Client and run:
   CREATE DATABASE adhd_app;
   CREATE USER 'adhd_user'@'localhost' IDENTIFIED BY 'adhd_password_123';
   GRANT ALL PRIVILEGES ON adhd_app.* TO 'adhd_user'@'localhost';
   FLUSH PRIVILEGES;
4. Update DB_CONFIG below with those values
5. Run the app - it will create all tables automatically

GODADDY SETUP (when ready):
1. Log into GoDaddy control panel
2. Create a MySQL database
3. Update DB_CONFIG with the credentials GoDaddy gives you
"""
import mysql.connector
from mysql.connector import Error

# Database credentials - UPDATE THESE WITH YOUR MYSQL INFO
DB_CONFIG = {
    'host': 'localhost',           # localhost for local, GoDaddy host for production
    'user': 'adhd_user',           # Your MySQL username
    'password': 'adhd_password_123',   # Your MySQL password
    'database': 'adhd_app'         # Your database name
}

def get_db_conn():
    """Get a MySQL database connection"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        raise

def dict_cursor_factory(cursor):
    """Convert MySQL cursor results to return dictionaries like sqlite3.Row"""
    description = cursor.description
    def make_dict(row):
        return {description[idx][0]: value for idx, value in enumerate(row)}
    return make_dict

class MySQLCursor:
    """Wrapper to make MySQL cursor behave like sqlite3 cursor"""
    def __init__(self, cursor):
        self.cursor = cursor
        self.lastrowid = None
        
    def execute(self, query, args=()):
        """Execute query with parameter conversion from ? to %s"""
        # Replace ? placeholders with %s for MySQL
        mysql_query = query.replace('?', '%s')
        self.cursor.execute(mysql_query, args)
        self.lastrowid = self.cursor.lastrowid
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

class MySQLConnection:
    """Wrapper to make MySQL connection behave like sqlite3"""
    def __init__(self, conn):
        self.conn = conn
        self.row_factory = None
        
    def cursor(self):
        """Return a wrapped cursor"""
        return MySQLCursor(self.conn.cursor())
    
    def commit(self):
        """Commit transaction"""
        self.conn.commit()
    
    def close(self):
        """Close connection"""
        self.conn.close()

def get_db_conn_wrapped():
    """Get a database connection with sqlite3-like interface"""
    mysql_conn = get_db_conn()
    return MySQLConnection(mysql_conn)
