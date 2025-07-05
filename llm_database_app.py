import os
import json
import sqlite3
from flask import Flask, request, jsonify, session
import google.generativeai as genai
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from database import UserDatabase
from llm_assistant import LLMAssistant


# --- Configuration ---
app = Flask(__name__)
app.secret_key = os.urandom(24) # Necessary for session management
# It's best practice to load your API key from environment variables
# IMPORTANT: Do not commit your API key to version control.
try:
    # Replace "YOUR_API_KEY" with your actual key, or set the environment variable
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
except KeyError:
    print("="*50)
    print("WARNING: GEMINI_API_KEY environment variable not set.")
    print("The application will not be able to contact the LLM.")
    print("Please set the environment variable and restart the server.")
    print("="*50)

# Initialize database
user_db = UserDatabase("app_database.db")

# Initialize LLM Assistant
llm_assistant = LLMAssistant()

# --- API Endpoints ---

def login_required(f):
    """Decorator to ensure a user is logged in before accessing an endpoint."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({"error": "Authentication required. Please log in."}), 401
        # Pass the user_id to the decorated function
        return f(user_id=session['user_id'], *args, **kwargs)
    return decorated_function


@app.route('/register', methods=['POST'])
def register():
    """Registers a new user."""
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({"error": "Missing name, email, or password"}), 400

    password_hash = generate_password_hash(password)

    try:
        conn = user_db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "User registered successfully."}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Registration failed. Email may already be in use."}), 409
    except Exception as e:
        return jsonify({"error": f"A database error occurred: {e}"}), 500

@app.route('/login', methods=['POST'])
def login():
    """Logs a user in by creating a session."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    conn = user_db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        session.clear()
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        return jsonify({"success": True, "message": "Login successful."}), 200

    return jsonify({"error": "Invalid email or password"}), 401

@app.route('/logout', methods=['POST'])
def logout():
    """Logs the current user out."""
    session.clear()
    return jsonify({"success": True, "message": "Logout successful."}), 200

@app.route('/items', methods=['GET'])
@login_required
def get_items(user_id):
    """Retrieves all items for the logged-in user."""
    conn = user_db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, content FROM items WHERE user_id = ?", (user_id,))
    items = cursor.fetchall()
    conn.close()
    # Convert Row objects to a list of dictionaries for JSON serialization
    items_list = [dict(item) for item in items]
    return jsonify({"success": True, "items": items_list})

@app.route('/process-request', methods=['POST'])
@login_required
def process_request(user_id):
    """API endpoint to handle natural language requests for logged-in users."""
    user_text = request.json.get('text')
    if not user_text:
        return jsonify({"error": "No text provided"}), 400

    db_op = llm_assistant.get_database_operation_from_text(user_text)
    if not db_op:
        return jsonify({"error": "Failed to understand the request or LLM is not configured."}), 500

    # **CRITICAL**: Validate and Sanitize the LLM output
    action = db_op.get("action")
    table = db_op.get("table")

    if action not in ["INSERT", "UPDATE", "DELETE"] or table != "items":
        return jsonify({"error": "Invalid or unsupported operation requested."}), 400

    conn = user_db.get_connection()
    cursor = conn.cursor()

    try:
        if action == "INSERT":
            data = db_op.get("data")
            content = data.get("content") if isinstance(data, dict) else None

            if not content:
                return jsonify({"error": "Missing 'content' in the data for INSERT."}), 400

            cursor.execute(
                "INSERT INTO items (content, user_id) VALUES (?, ?)",
                (content, user_id)
            )
            new_item_id = cursor.lastrowid
            conn.commit()
            return jsonify({"success": True, "message": "Item added successfully.", "itemId": new_item_id}), 201

        elif action == "UPDATE":
            data = db_op.get("data")
            where_clause = db_op.get("where")
            new_content = data.get("content") if isinstance(data, dict) else None
            old_content = where_clause.get("content") if isinstance(where_clause, dict) else None

            if not new_content or not old_content:
                return jsonify({"error": "UPDATE requires 'content' in both 'data' and 'where' clauses."}), 400

            # The WHERE clause now also checks for user_id to ensure users can only update their own items.
            cursor.execute(
                "UPDATE items SET content = ? WHERE content = ? AND user_id = ?",
                (new_content, old_content, user_id)
            )
            updated_rows = cursor.rowcount
            conn.commit()

            if updated_rows == 0:
                return jsonify({"success": False, "message": "No item found with that content to update."}), 404
            else:
                return jsonify({"success": True, "message": f"Successfully updated {updated_rows} item(s)."}), 200

        elif action == "DELETE":
            where_clause = db_op.get("where")
            content_to_delete = where_clause.get("content") if isinstance(where_clause, dict) else None

            if not content_to_delete:
                return jsonify({"error": "DELETE action requires 'content' in the 'where' clause."}), 400

            # The WHERE clause now also checks for user_id to ensure users can only delete their own items.
            cursor.execute(
                "DELETE FROM items WHERE content = ? AND user_id = ?",
                (content_to_delete, user_id)
            )
            deleted_rows = cursor.rowcount
            conn.commit()

            if deleted_rows == 0:
                return jsonify({"success": False, "message": "No item found with that content to delete."}), 404
            else:
                return jsonify({"success": True, "message": f"Successfully deleted {deleted_rows} item(s)."}), 200

    except Exception as e:
        conn.rollback() # Rollback changes on any error
        return jsonify({"error": f"A database error occurred: {e}"}), 500
    finally:
        conn.close() # Ensure connection is always closed

# --- Main execution block ---
if __name__ == '__main__':
    app.run(debug=True, port=5001)
