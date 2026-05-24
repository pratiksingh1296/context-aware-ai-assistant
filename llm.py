# ==================================================
# Imports
# ==================================================

# Standard library imports
from datetime import datetime, timedelta
import os 
import re
# Third-party imports
import streamlit as st
from dotenv import load_dotenv
# LangChain imports
from langchain_groq import ChatGroq
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, AIMessage


# ==================================================
# Environment Setup
# ==================================================

load_dotenv() # Load environment variables from .env file

def get_secret(key):
    """
    Retrieve a secret from environment variables
    or Streamlit secrets.

    """
    value = os.getenv(key)

    if not value:
        try:
            value = st.secrets[key]
        except KeyError:
            raise ValueError(f"{key} not found")

    return value

groq_api_key = get_secret("GROQ_API_KEY")
tavily_api_key = get_secret("TAVILY_API_KEY")

os.environ["TAVILY_API_KEY"] = tavily_api_key


# ==================================================
# Prompts
# ==================================================

def get_today():
    """
    Returns current date in a human-readable format.
    """
    return {
        "date": datetime.now().strftime("%B %d, %Y"),
        "weekday": datetime.now().strftime("%A")
    }

prompt = ChatPromptTemplate.from_messages([
    ("system", f"""

    You are a helpful AI assistant with persistent memory and web search access.

    You have access to a web search tool that returns structured web results.

    Use the web search tool whenever the query requires current or real-time information, including:
    - current events
    - news
    - sports results and fixtures
    - weather
    - prices
    - recent developments
    - topics or events after 2023

    When using web search:
    - interpret relative dates like "today", "yesterday", "last night", and "this week" using the current date
    - generate precise search queries
    - prefer queries containing exact dates, event names, and relevant entities
    - use only the most relevant retrieved information and avoid unnecessary repetition

    For sports-related queries:
    - prefer precise searches including team names, tournaments, match dates, and match results

    When using web search results:
    - include relevant source names or URLs at the end of the response
    - if results are unclear, incomplete, or conflicting, say so honestly instead of inventing information
    - when including sources, avoid raw URLs when possible.
    - prefer concise source names or website domains.
    - format sources cleanly as bullet points.

    Do not claim you lack real-time information if web search can answer the question.
    Use the search tool when appropriate.

    For greetings, casual conversation, or general knowledge questions that do not require current information, respond directly without using web search.

    If relevant memories are retrieved from previous conversations:
    - naturally incorporate them into the response conversationally
    - use phrasing like:
        - "You mentioned earlier that..."
        - "I remember you said..."
        - "From our previous chats..."
    - only reference memory when it is genuinely relevant
    - do not invent memories or claim the user mentioned something unless it appears in retrieved memory context

    Keep responses clear, concise, and helpful.
    """),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])


# ==================================================
# Cache Resources
# ==================================================

@st.cache_resource
def get_llm():

    return ChatGroq(
        api_key=groq_api_key,
        model="llama-3.3-70b-versatile",
        temperature=0.1,
        max_tokens=1024,
        timeout=30,
        max_retries=3
    )


@st.cache_resource
def get_agent_executor():
    """
    Caches the agent executor to optimize performance and resource usage across interactions
    """

    llm = get_llm() # Retrieve the cached LLM instance for consistent performance
    search_tool = TavilySearchResults(
        max_results=3,
        search_depth="advanced"
    )
    tools = [search_tool]
    agent = create_tool_calling_agent(
        llm=llm,
        tools=tools,
        prompt=prompt
    )
    
    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5
    )


# ==================================================
# Utility Functions
# ==================================================

def generate_chat_title(first_message):
    """    
    Title generation function to create concise chat titles from the first user message
    """

    prompt = f"""
    Create a concise 3-5 word title for a chat based on the following first user message.
    Remove common stop words and punctuation.
    
    User Message: {first_message}

    Return only the title.
    """
    llm = get_llm() # Retrieve the cached LLM instance for consistent performance
    response = llm.invoke(prompt)
    return response.content.strip()


def normalize_dates(query):
    """
    Function to normalize relative date terms in user queries to absolute dates
    Replace relative date terms in the query with absolute dates based on the current date.
    """
    today = datetime.now()

    replacements = {
        r"\btoday\b": today.strftime("%B %d %Y"),
        r"\byesterday\b": (today - timedelta(days=1)).strftime("%B %d %Y"),
        r"\btomorrow\b": (today + timedelta(days=1)).strftime("%B %d %Y"),
    }

    normalized_query = query

    for pattern,replacement in replacements.items():
        normalized_query = re.sub(pattern, replacement, normalized_query, flags=re.IGNORECASE)

    return normalized_query


# ==================================================
# Response Generation
# ==================================================

def generate_response(prompt_text, chat_history=None):
    """
    Main function to generate a response from the agent based on the user prompt and chat history
    - Normalizes relative date terms in the user query
    - Invokes the agent executor with the processed query and chat history
    - Handles exceptions gracefully, including API rate limits, and falls back to direct LLM response if necessary
    - Returns the final response to be sent back to the user
    """

    agent_executor = get_agent_executor() # Retrieve the cached agent executor instance for optimal performance

    if chat_history is None:
        chat_history = []

    today_info = get_today() # Get current date & day information for temporal context

    # Process relative temporal terms (e.g., 'yesterday', 'last week')
    processed_query = normalize_dates(prompt_text)

    # Prepend current date to the query to provide temporal context for the agent and improve relevance of web search results when handling time-sensitive queries
    if any(word in prompt_text.lower() for word in [
    "today", "yesterday", "tomorrow",
    "latest", "recent", "current", "news"
    ]):
        processed_query = (
            f"Today's date is {today_info['date']} "
            f"and today is {today_info['weekday']}.\n\n"
            f"{processed_query}")
        

    # --------------------------------------------------
    # Track 1: Try executing via Agent Executor (with Tools)
    # --------------------------------------------------
    try:
        response = agent_executor.invoke({
            "input": processed_query,
            "chat_history": chat_history 
        })
        return response["output"]
    
    except Exception as e:
        print("AGENT ERROR:", repr(e))
        error_str = str(e)

        # Immediate exit for API exhaustion
        if "rate_limit_exceeded" in error_str or "429" in error_str:
            return "I've hit my API rate limit for now. Please wait a few minutes and try again."
        
        # --------------------------------------------------
        # Track 2: Fallback to Direct LLM (Maintaining Chat History Context)
        # --------------------------------------------------
        try:
            message_list = []
            for msg in chat_history:
                if msg.get("role") == "user":
                    message_list.append(HumanMessage(content=msg["content"]))
                elif msg.get("role") == "assistant":
                    message_list.append(AIMessage(content=msg["content"]))

            # Append the current memory-enriched prompt to the end of the history chain
            message_list.append(HumanMessage(content=processed_query))

            # Invoke the model directly with full conversational context
            llm = get_llm() # Retrieve the cached LLM instance for consistent performance
            response = llm.invoke(message_list)
            return response.content
        
        except Exception as e2:
            print("LLM FALLBACK ERROR:", repr(e2))
            if "rate_limit_exceeded" in str(e2) or "429" in str(e2):
                return "I've hit my API rate limit for now. Please wait a few minutes and try again."
            return "Something went wrong. Please try again."

# Example usage for testing the response generation function    
if __name__ == "__main__":
    user_input = input("You: ")
    response = generate_response(user_input)
    print(f"Assistant: {response}")


