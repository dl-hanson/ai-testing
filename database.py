import sqlite3


# --- Database Interaction Class ---
class UserDatabase:
    def __init__(self, db_file):
        self.db_file = db_file
        self.init_db()

    def get_connection(self):
        """Establishes a connection to the SQLite database."""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row  # Allows accessing columns by name
        return conn

    def init_db(self):
        """Initializes the database with users and items tables if they don't exist."""
        print(f"Checking and initializing database at '{self.db_file}'...")
        conn = self.get_connection()
        cursor = conn.cursor()
        # Create users table for authentication
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        if cursor.fetchone() is None:
            print("Creating 'users' table...")
            # Store hashed passwords, not plain text
            conn.execute('CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);')
            print("'users' table created successfully.")
        else:
            print("'users' table already exists.")

        # Create items table for user-specific data
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items';")
        if cursor.fetchone() is None:
            print("Creating 'items' table...")
            conn.execute('''
                CREATE TABLE items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                );
            ''')
            print("'items' table created successfully.")
        else:
            print("'items' table already exists.")

        conn.close()
