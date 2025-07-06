# AI-Powered List Manager

This is a simple web application that demonstrates how to use a Large Language Model (LLM) as a natural language interface for a database. Users can register, log in, and manage a personal item list (like a shopping or to-do list) by typing commands in plain English. The LLM interprets these commands, generates structured database operations, and can even suggest related items to add.

## Features

-   **User Authentication**: Secure user registration and login system.
-   **Natural Language Interface**: Add, update, delete, and query items on your list using everyday language (e.g., "add milk and eggs", "remove bread", "what's on my list?").
-   **AI-Powered Suggestions**: After adding an item, the assistant suggests related items you might also need (e.g., adding "cereal" might prompt a suggestion for "milk").
-   **Duplicate Prevention**: The application intelligently prevents duplicate items from being added to your list.
-   **Safe Database Transactions**: Uses context managers to ensure database connections are handled safely and transactions are atomic.

## Prerequisites

Before you begin, ensure you have the following installed on your system.

### 1. Python
This project requires Python 3.10 or newer.

-   **Windows**: Download the latest Python installer from the [official Python website](https://www.python.org/downloads/). Make sure to check the box that says **"Add Python to PATH"** during installation.
-   **macOS/Linux**: Python is often pre-installed. You can check your version by running `python3 --version`. If you need to install or upgrade, it's recommended to use a version manager like `pyenv`.

`pip`, the Python package installer, is included with all modern versions of Python.

### 2. Git
You will need Git to clone the repository. You can download it from the official Git website.

### 3. Gemini API Key
This application uses the Google Gemini API. You will need an API key to connect to the LLM.

1.  Visit Google AI Studio.
2.  Log in with your Google account.
3.  Click on **"Get API key"** and then **"Create API key in new project"**.
4.  Copy the generated API key. You will need it in the configuration step.

> **Note on gcloud**: This application is configured to use an API key directly. You do not need to install the `gcloud` CLI or set up Application Default Credentials.

## Setup and Installation

Follow these steps to get the application running on your local machine.

### 1. Clone the Repository
Open your terminal or command prompt and run the following command to clone the project:
```bash
git clone <repository-url>
cd <repository-folder-name>
```

### 2. Create and Activate a Virtual Environment
It is highly recommended to use a virtual environment to manage project dependencies.

-   **On Windows**:
    ```bash
    python -m venv venv
    venv\Scripts\activate
    ```

-   **On macOS/Linux**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
You will know the environment is active when you see `(venv)` at the beginning of your command prompt.

### 3. Install Dependencies
With your virtual environment active, install the required Python packages using the `requirements.txt` file:
```bash
pip install -r requirements.txt
```

## Configuration

The application requires your Gemini API key to be set as an environment variable.

1.  In the root of the project folder, create a new file named `.env`.
2.  Open the `.env` file and add your API key in the following format:

    ```
    GEMINI_API_KEY="your_api_key_here"
    ```
    Replace `"your_api_key_here"` with the actual key you obtained from Google AI Studio. The `.gitignore` file is configured to prevent this file from being committed to version control.

## Running the Application

Once the setup and configuration are complete, you can start the Flask web server.

1.  Make sure your virtual environment is still active.
2.  Run the main application file from the root of the project directory:
    ```bash
    python llm_database_app.py
    ```
3.  The server will start, and you will see output in your terminal indicating that it is running, typically on port 5001.
    ```
     * Running on http://127.0.0.1:5001
    ```
4.  Open your web browser and navigate to **http://127.0.0.1:5001** to use the application.