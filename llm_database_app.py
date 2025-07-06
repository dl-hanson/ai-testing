import os
import json
import sqlite3
from flask import Flask, request, jsonify, session, render_template
import google.generativeai as genai
from functools import wraps
from dotenv import load_dotenv
from database import UserDatabase
from llm_assistant import LLMAssistant


# --- Configuration ---
load_dotenv() # Load environment variables from .env file

app = Flask(__name__)
app.secret_key = os.urandom(24) # Necessary for session management
# It's best practice to load your API key from environment variables
# IMPORTANT: Do not commit your API key to version control.
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)
else:
    print("="*50)
    print("WARNING: GEMINI_API_KEY environment variable not set.")
    print("The application will not be able to contact the LLM.")
    print("Please set the environment variable and restart the server.")
    print("="*50)

# Initialize database
user_db = UserDatabase("app_database.db")

# Initialize LLM Assistant
llm_assistant = LLMAssistant(api_key=gemini_api_key)

# --- Centralized Error Handling ---

@app.errorhandler(Exception)
def handle_generic_exception(e):
    """Catches all unhandled exceptions and returns a standard JSON error response."""
    # For production, you would want to log the error in more detail.
    # For example: app.logger.error(f"Unhandled exception: {e}", exc_info=True)
    print(f"ERROR: An unhandled exception occurred: {e}")
    # To be safe, we don't expose internal error details to the client.
    return jsonify({"error": "An internal server error occurred."}), 500


# --- API Endpoints ---

@app.route('/')
def index():
    """Serves the main frontend application page."""
    # This assumes you have a 'templates' folder with an 'index.html' file.
    return render_template('index.html')

def login_required(f):
    """Decorator to ensure a user is logged in before accessing an endpoint."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "Authentication required. Please log in."}), 401
        
        # Good practice: Check if the user still exists in the database.
        # This handles cases where a user might be deleted but their session cookie remains.
        with user_db.managed_cursor(commit_on_exit=False) as cursor:
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if not cursor.fetchone():
                session.clear() # Clear the invalid session
                return jsonify({"error": "Invalid session. Please log in again."}), 401

        # Pass the user_id to the decorated function
        return f(user_id=user_id, *args, **kwargs)
    return decorated_function


@app.route('/register', methods=['POST'])
def register():
    """Registers a new user."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')

    if not name or not email or not password:
        return jsonify({"error": "Missing name, email, or password"}), 400

    success, message = user_db.register_user(name, email, password)

    if success:
        return jsonify({"success": True, "message": message}), 201
    else:
        return jsonify({"error": message}), 409

@app.route('/login', methods=['POST'])
def login():
    """Logs a user in by creating a session."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    user = user_db.authenticate_user(email, password)

    if user:
        session.clear()
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        return jsonify({"success": True, "message": "Login successful.", "userName": user['name']}), 200

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
    with user_db.managed_cursor(commit_on_exit=False) as cursor:
        cursor.execute("SELECT id, content FROM items WHERE user_id = ?", (user_id,))
        items = cursor.fetchall()
    # Convert Row objects to a list of dictionaries for JSON serialization
    items_list = [dict(item) for item in items]
    return jsonify({"success": True, "items": items_list})

@app.route('/items/add', methods=['POST'])
@login_required
def add_suggested_item(user_id):
    """Adds a single, specific item to the user's list, typically from a suggestion."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    content = data.get('content')

    if not content:
        return jsonify({"error": "No content provided"}), 400
    
    status, item_id = user_db.add_item(user_id, content)

    if status == "exists":
        return jsonify({
            "success": False,
            "message": f"Item '{content}' already exists on your list.",
            "itemId": item_id
        }), 409 # Conflict

    return jsonify({
        "success": True,
        "message": "Item added successfully.",
        "itemId": item_id
    }), 201

# --- Helper functions for process_request ---

def _handle_insert(cursor, db_op, user_id):
    """Handles the INSERT database operation, preventing duplicates."""
    if not db_op.data or not db_op.data.content:
        return {"error": "Missing 'content' in the data for INSERT."}, 400

    content = db_op.data.content
    normalized_content = content.strip().lower()

    # Check for existence using the provided cursor
    cursor.execute(
        "SELECT id FROM items WHERE lower(content) = ? AND user_id = ?",
        (normalized_content, user_id)
    )
    existing_item = cursor.fetchone()

    if existing_item:
        return {
            "success": False,
            "message": f"Item '{content}' already exists on your list.",
            "itemId": existing_item['id'],
            "action_type": "mutation"
        }, 409 # Conflict

    # If not, insert it
    cursor.execute(
        "INSERT INTO items (content, user_id) VALUES (?, ?)",
        (content.strip(), user_id)
    )
    new_item_id = cursor.lastrowid
    return {
        "success": True,
        "message": "Item added successfully.",
        "itemId": new_item_id,
        "action_type": "mutation"
    }, 201

def _handle_update(cursor, db_op, user_id):
    """Handles the UPDATE database operation."""
    new_content = db_op.data.content if db_op.data else None
    old_content = db_op.where.content if db_op.where else None

    if not new_content or not old_content:
        return {"error": "UPDATE requires 'content' in both 'data' and 'where' clauses."}, 400

    # The WHERE clause now also checks for user_id to ensure users can only update their own items.
    cursor.execute(
        "UPDATE items SET content = ? WHERE content = ? AND user_id = ?",
        (new_content, old_content, user_id)
    )
    updated_rows = cursor.rowcount

    if updated_rows == 0:
        return {"success": False, "message": "No item found with that content to update.", "action_type": "mutation"}, 404
    
    return {"success": True, "message": f"Successfully updated {updated_rows} item(s).", "action_type": "mutation"}, 200

def _handle_delete(cursor, db_op, user_id):
    """Handles the DELETE database operation."""
    content_to_delete = db_op.where.content if db_op.where else None
    if not content_to_delete:
        return {"error": "DELETE action requires 'content' in the 'where' clause."}, 400

    # The WHERE clause now also checks for user_id to ensure users can only delete their own items.
    cursor.execute(
        "DELETE FROM items WHERE content = ? AND user_id = ?",
        (content_to_delete, user_id)
    )
    deleted_rows = cursor.rowcount

    if deleted_rows == 0:
        return {"success": False, "message": "No item found with that content to delete.", "action_type": "mutation"}, 404
    
    return {"success": True, "message": f"Successfully deleted {deleted_rows} item(s).", "action_type": "mutation"}, 200

def _handle_query(cursor, db_op, user_id):
    """Handles the QUERY database operation."""
    cursor.execute("SELECT content FROM items WHERE user_id = ?", (user_id,))
    query_items = cursor.fetchall() # Use a different variable name to avoid conflict
    
    if not query_items:
        message = "You do not have any items on your list."
    else:
        # Format the items into a readable string
        item_contents = [f"'{item['content']}'" for item in query_items]
        if len(item_contents) == 1:
            message = f"You have one item: {item_contents[0]}."
        else:
            items_str = ", ".join(item_contents)
            message = f"Your items are: {items_str}."
    
    return {"success": True, "message": message, "action_type": "query"}, 200

def _build_final_response(base_response_data, status_code, llm_response):
    """Builds the final JSON response, adding suggestions if applicable."""
    # If the database operation was successful, check for and attach any suggestions from the LLM.
    is_successful_operation = status_code < 300
    if is_successful_operation and llm_response and llm_response.suggestion:
        base_response_data['suggestion'] = {
            "message": llm_response.suggestion.message,
            "items": llm_response.suggestion.items
        }
    
    # This debug print is crucial for verifying the data sent to the frontend.
    print(f"DEBUG: Final response data being sent: {json.dumps(base_response_data, indent=2)}")
    
    return jsonify(base_response_data), status_code


@app.route('/process-request', methods=['POST'])
@login_required
def process_request(user_id):
    """API endpoint to handle natural language requests for logged-in users."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid or missing JSON body"}), 400
    user_text = data.get('text')
    if not user_text:
        return jsonify({"error": "No text provided"}), 400

    # The broad try/except is removed. The @app.errorhandler will catch exceptions,
    # and the managed_cursor context manager will handle database rollback.
    with user_db.managed_cursor() as cursor:
        # --- Provide Context to the LLM ---
        cursor.execute("SELECT id, content FROM items WHERE user_id = ?", (user_id,))
        items = cursor.fetchall()
        items_list = [dict(item) for item in items]

        # 2. Call the LLM with the user's text and the context of their current items.
        llm_response = llm_assistant.get_database_operation_from_text(user_text, current_items=items_list)

        if not llm_response:
            return jsonify({"error": "Failed to understand the request or LLM is not configured."}), 500

        # For debugging, print the Pydantic object received from the LLM.
        print(f"DEBUG: Received response from LLM: {llm_response}")

        # Check if the LLM returned a request for clarification
        if llm_response.ambiguous_request:
            return jsonify({"success": False, "error": llm_response.ambiguous_request.message}), 400

        # Extract the actual database operation
        db_op = llm_response.database_operation

        # Check if the LLM failed to produce a valid operation
        if not db_op:
            return jsonify({"error": "LLM did not return a valid database operation."}), 500

        # --- Action Dispatcher ---
        # Use a dictionary to map action strings to their handler functions.
        action_handlers = {
            "INSERT": _handle_insert,
            "UPDATE": _handle_update,
            "DELETE": _handle_delete,
            "QUERY": _handle_query,
        }

        handler = action_handlers.get(db_op.action)

        if handler:
            base_response_data, status_code = handler(cursor, db_op, user_id)
            return _build_final_response(base_response_data, status_code, llm_response)
        else:
            return jsonify({"error": f"Unknown or unsupported action: {db_op.action}"}), 400

# --- Main execution block ---
if __name__ == '__main__':
    app.run(debug=True, port=5001)
