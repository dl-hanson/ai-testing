from typing import Literal, Optional, Union, List
from pydantic import BaseModel, Field, model_validator

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI


# --- Pydantic Models for Structured, Validated Output ---
# These models define the exact JSON structure we expect from the LLM.
# LangChain uses these to generate parsing instructions and validate the output.

class InsertData(BaseModel):
    content: str = Field(description="The content of the new item to be added.")

class UpdateData(BaseModel):
    content: str = Field(description="The new content for the item being updated.")

class WhereClause(BaseModel):
    content: str = Field(description="The exact content of the item to be updated or deleted. This MUST match an item from the user's current list.")

class Suggestion(BaseModel):
    message: str = Field(description="A friendly message introducing the suggestions.")
    items: List[str] = Field(description="A list of suggested items for the user to add.")

# These two models represent the possible outcomes.
class AmbiguousRequest(BaseModel):
    message: str = Field(description="A helpful message asking the user for clarification.")

class DatabaseOperation(BaseModel):
    action: Literal["INSERT", "UPDATE", "DELETE", "QUERY"] = Field(description="The database action to perform.")
    table: Literal["items"] = Field(description="The table to perform the action on, which must be 'items'.")
    data: Optional[Union[InsertData, UpdateData]] = Field(default=None, description="The data for an INSERT or UPDATE operation.")
    where: Optional[WhereClause] = Field(default=None, description="The 'where' clause to identify an item for UPDATE or DELETE operations.")

# NEW: A single top-level response model that contains one of the outcomes.
# This gives the parser a single, concrete Pydantic model to work with, resolving the error.
class LLMResponse(BaseModel):
    """A container for the LLM's response. It can contain an operation, a clarification request, or suggestions."""
    database_operation: Optional[DatabaseOperation] = Field(default=None, description="A valid database operation to be executed.")
    ambiguous_request: Optional[AmbiguousRequest] = Field(default=None, description="A request for user clarification if the input is ambiguous.")
    suggestion: Optional[Suggestion] = Field(default=None, description="An optional list of suggested items for the user to add, based on their request.")

    @model_validator(mode='after')
    def check_exclusive_fields(self) -> 'LLMResponse':
        """Ensures that ambiguous_request is not set at the same time as other fields."""
        if self.ambiguous_request and (self.database_operation or self.suggestion):
            raise ValueError("ambiguous_request cannot be set with database_operation or suggestion")
        return self

class LLMAssistant:
    def __init__(self, api_key: Optional[str], model_name: str = 'gemini-1.5-flash-latest'):
        # 1. Initialize the LangChain model wrapper
        if not api_key:
            print("WARNING: LLMAssistant initialized without an API key. Model will be disabled.")
            self.model = None
        else:
            self.model = ChatGoogleGenerativeAI(
                model=model_name,
                google_api_key=api_key,
            )

        # 2. Initialize the parser with our Pydantic model
        self.parser = PydanticOutputParser(pydantic_object=LLMResponse)
        # 3. Create a robust prompt template
        self.prompt_template = PromptTemplate(
            template="""You are a database assistant for a personal item manager. Your task is to convert a user's natural language request into a structured JSON object.

{format_instructions}

{item_context}

**IMPORTANT RULES**:
1. Your response MUST be a JSON object with one or more of the following top-level keys: "database_operation", "ambiguous_request", "suggestion".
2. If the user's request is clear, populate the "database_operation" field with the correct action (INSERT, UPDATE, DELETE, or QUERY).
3. If a request to UPDATE or DELETE is ambiguous (e.g., the user says "delete milk" when their list contains "buy milk" and "get whole milk"), you MUST populate ONLY the "ambiguous_request" field with a helpful message asking for clarification.
4. For simple requests like "get bread", assume an INSERT operation.
5. **SUGGESTION FEATURE**: If the user performs an INSERT, you may also populate the "suggestion" field with a list of related items. For example, if they add "hot dogs", you could suggest ["hot dog buns", "ketchup", "mustard"]. Provide a friendly message. Do not provide suggestions for UPDATE, DELETE, or QUERY actions.
6. **YOUR SCOPE**: Your ONLY job is to manage a list of personal items (like a shopping or to-do list). If the user asks you to do anything else (like create a user, change a password, or have a general conversation), you MUST respond by populating ONLY the "ambiguous_request" field with a message explaining that you can only manage their item list.

User Request: "{user_input}"
""",
            input_variables=["user_input", "item_context"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()},
        )
        # 4. Create the processing chain
        # Only create the chain if the model was successfully initialized
        if self.model:
            self.chain = self.prompt_template | self.model | self.parser
        else:
            self.chain = None

    def get_database_operation_from_text(self, user_input, current_items=None):
        """Uses a LangChain chain to convert natural language to a structured Pydantic object."""
        if not self.chain:
            print("LLM chain is not initialized (likely missing API key).")
            return None

        item_context = "The user currently has no items."
        if current_items:
            item_list_str = "\n".join([f"- \"{item['content']}\"" for item in current_items])
            item_context = f"""Here is the user's current list of items. Use this list to resolve ambiguity and to find the exact 'content' for UPDATE and DELETE operations.
{item_list_str}"""

        try:
            return self.chain.invoke({
                "user_input": user_input,
                "item_context": item_context
            })
        except Exception as e:
            print(f"An error occurred with the LangChain chain: {e}")
            return None
