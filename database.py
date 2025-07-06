import sqlite3
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash


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

    @contextmanager
    def managed_cursor(self, commit_on_exit: bool = True):
        """A context manager for safe database transactions."""
        conn = self.get_connection()
        try:
            yield conn.cursor()
            if commit_on_exit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def register_user(self, name, email, password):
        """Hashes a password and adds a new user to the database.

        Returns:
            tuple: A tuple containing (bool, str) for success status and a message.
        """
        password_hash = generate_password_hash(password)
        try:
            with self.managed_cursor() as cursor:
                cursor.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, password_hash)
                )
            return True, "User registered successfully."
        except sqlite3.IntegrityError:
            return False, "Registration failed. Email may already be in use."

    def authenticate_user(self, email, password):
        """Authenticates a user by email and password, returning user data if successful."""
        with self.managed_cursor(commit_on_exit=False) as cursor:
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            user = cursor.fetchone()

        if user and check_password_hash(user['password_hash'], password):
            return dict(user)  # Return user data as a dictionary
        return None

    def add_item(self, user_id, content):
        """Adds a single item to the database for a given user.
        This method now prevents duplicate items from being added.

        Returns:
            tuple: A tuple of (status, item_id).
                   status can be "added" or "exists".
                   item_id is the id of the new or existing item.
        """
        # Normalize content to prevent case-sensitive duplicates
        normalized_content = content.strip().lower()

        # First, check for existence in a non-committing transaction
        with self.managed_cursor(commit_on_exit=False) as cursor:
            cursor.execute(
                "SELECT id FROM items WHERE lower(content) = ? AND user_id = ?",
                (normalized_content, user_id)
            )
            existing_item = cursor.fetchone()

        if existing_item:
            return "exists", existing_item['id']

        # If not, insert it using a new transaction that commits.
        with self.managed_cursor(commit_on_exit=True) as cursor:
            cursor.execute(
                "INSERT INTO items (content, user_id) VALUES (?, ?)",
                (content.strip(), user_id) # Insert original, but stripped, content
            )
            return "added", cursor.lastrowid

    def init_db(self):
        """Initializes the database with users and items tables if they don't exist."""
        print(f"Checking and initializing database at '{self.db_file}'...")
        with self.managed_cursor() as cursor:
            # Create users table for authentication
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
            if cursor.fetchone() is None:
                print("Creating 'users' table...")
                # Store hashed passwords, not plain text
                cursor.execute('CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL);')
                print("'users' table created successfully.")
            else:
                print("'users' table already exists.")

            # Create items table for user-specific data
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items';")
            if cursor.fetchone() is None:
                print("Creating 'items' table...")
                cursor.execute('''
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
