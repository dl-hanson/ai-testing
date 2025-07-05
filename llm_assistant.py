import json
import google.generativeai as genai


class LLMAssistant:
    def __init__(self, model_name='gemini-pro'):
        self.model = None
        if genai.API_KEY:
            self.model = genai.GenerativeModel(model_name)

    def get_database_operation_from_text(self, user_input):
        """Uses the LLM to convert natural language to a structured DB operation."""
        if not self.model:
            print("LLM call skipped: API key not configured or model not initialized.")
            return None

        # The prompt is crucial. It tells the LLM its role, the schema it can use,
        # and the exact format for its response.
        prompt = f"""
        You are a database assistant for a personal item manager. Your task is to convert a user's natural language request
        into a structured JSON object that represents a database operation on their personal items.

        The user's items are stored in a table named 'items' with a single important column: 'content' (TEXT).

        Your response MUST be a JSON object with the following keys:
        - "action": Can be "INSERT", "UPDATE", or "DELETE".
        - "table": Must always be "items".
        - "data": (For INSERT/UPDATE) A JSON object with a "content" key for the new item text.
        - "where": (For UPDATE/DELETE) A JSON object with a "content" key to identify the item to be changed or removed.

        Here are some examples:

        User Request: "add a new item: buy milk"
        JSON Output:
        {{
          "action": "INSERT",
          "table": "items",
          "data": {{
            "content": "buy milk"
          }}
        }}

        User Request: "change 'buy milk' to 'buy almond milk'"
        JSON Output:
        {{
          "action": "UPDATE",
          "table": "items",
          "data": {{
            "content": "buy almond milk"
          }},
          "where": {{
            "content": "buy milk"
          }}
        }}

        User Request: "delete the item 'buy almond milk'"
        JSON Output:
        {{
          "action": "DELETE",
          "table": "items",
          "where": {{
            "content": "buy almond milk"
          }}
        }}

        User Request: "{user_input}"

        JSON Output:
        """

        try:
            response = self.model.generate_content(prompt)
            # The response might have markdown backticks, so we clean it.
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "").replace("`", "")
            return json.loads(cleaned_response)
        except Exception as e:
            print(f"An error occurred with the LLM API or JSON parsing: {e}")
            return None
