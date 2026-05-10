# ==================================================
# Imports
# ==================================================
from datetime import datetime
import os
import streamlit as st
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


# ==================================================
# ENV - Load API Key
# ==================================================

load_dotenv()
api_key = os.getenv("GROQ_API_KEY") 
if not api_key:
    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except:
        raise ValueError("GROQ_API_KEY not found in environment or Streamlit secrets")

# ==================================================
# LLM
# ==================================================

llm = ChatGroq(
    api_key=api_key, 
    model="llama-3.3-70b-versatile",
    temperature=0.1,
    max_tokens=1024,
    timeout=30,
    max_retries=3
    )

# ==================================================
# SEARCH TOOL
# ==================================================

search_tool = DuckDuckGoSearchRun()
tools = [search_tool]

# ==================================================
# PROMPT
# ==================================================

today = datetime.now().strftime("%B %d, %Y")
print(f"DEBUG: Today is {today}")

prompt = ChatPromptTemplate.from_messages([
    ("system", f"""You are a helpful assistant with persistent memory and access to web search.
    Today's date is {today}.
    You have access to the following tool: duckduckgo_search
    Use duckduckgo_search ONLY when the user asks about:
    - Current events, news, or recent developments
    - Real-time data like prices, scores, weather
    - Sports fixtures, match schedules, Premier League, IPL, football
    - Anything that may have changed after 2023
    For simple conversational responses like greetings, thanks, or acknowledgements, respond directly without using any tools.
    If search results are inconclusive, explain that to the user instead of searching again.
    IMPORTANT: Only use tools that are explicitly provided to you. Never say you don't have real-time access — use the search tool instead."""),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad")
])

# ==================================================
# AGENT
# ==================================================

agent = create_tool_calling_agent(
    llm=llm, tools=tools, prompt=prompt
    )

# ==================================================
# EXECUTOR
# ==================================================

agent_executor = AgentExecutor(
    agent=agent, 
    tools=tools, 
    verbose=True,
    handle_parsing_errors=True,
    max_iterations=5
)

# ==================================================
# CHAT LOOP
# ==================================================

def generate_response(prompt_text, chat_history=[]):
    try:
        response = agent_executor.invoke({
            "input": prompt_text,
            "chat_history": chat_history 
        })
        return response["output"]
    except Exception as e:
        error_str = str(e)
        if "rate_limit_exceeded" in error_str or "429" in error_str:
            return "I've hit my API rate limit for now. Please wait a few minutes and try again."
        # Fallback to direct LLM call without tools
        try:
            response = llm.invoke(prompt_text)
            return response.content
        except Exception as e2:
            if "rate_limit_exceeded" in str(e2) or "429" in str(e2):
                return "I've hit my API rate limit for now. Please wait a few minutes and try again."
            return "Something went wrong. Please try again."

# ==================================================
# MAIN
# ==================================================

if __name__ == "__main__":
    user_input = input("You: ")
    response = generate_response(user_input)
    print(f"Assistant: {response}")


