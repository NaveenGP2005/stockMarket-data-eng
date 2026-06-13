import os
import json
import hashlib
import snowflake.connector
import chromadb
import ollama
from typing import List, TypedDict, Optional, Dict, Any
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

# Load environment variables
load_dotenv(dotenv_path=os.path.abspath(".env"))

def generate_text(prompt: str, system_instruction: str = None, response_schema = None) -> str:
    """Generate text using local Ollama model."""
    local_model = os.getenv("LOCAL_LLM_MODEL", "gemma2:2b")
    
    # Construct dynamic prompt for JSON schema guidance if response_schema is provided
    if response_schema:
        schema_desc = response_schema.schema() if hasattr(response_schema, "schema") else str(response_schema)
        full_prompt = f"{prompt}\n\nYou must respond ONLY with a raw JSON object conforming to this schema:\n{schema_desc}\nReturn raw JSON text and do not wrap it in markdown block quotes (do not use ```json)."
    else:
        full_prompt = prompt
    
    print(f"[Ollama LLM] Generating using model '{local_model}'...")
    response = ollama.generate(
        model=local_model,
        prompt=full_prompt,
        system=system_instruction or ""
    )
    return response["response"].strip()

# Database & Vector configurations
CHROMA_PATH = "./chroma_db"
COLLECTION_NAME = "financial_news"
SNOWFLAKE_DB = "STOCKS_MDS"
SNOWFLAKE_SCHEMA = "COMMON"

SCHEMA_DESC = """
We have the following views/tables in database STOCKS_MDS, schema COMMON:

1. GOLD_KPI:
   - SYMBOL (VARCHAR)
   - CURRENT_PRICE (DOUBLE)
   - CHANGE_AMOUNT (DOUBLE)
   - CHANGE_PERCENT (DOUBLE)
   Note: Contains exactly one row per stock symbol representing its latest price and KPI metrics. Do NOT sort by date/time columns when querying this table.

2. GOLD_CANDLESTICK:
   - SYMBOL (VARCHAR)
   - CANDLE_TIME (DATE)
   - CANDLE_LOW (DOUBLE)
   - CANDLE_HIGH (DOUBLE)
   - CANDLE_OPEN (DOUBLE)
   - CANDLE_CLOSE (DOUBLE)
   - TREND_LINE (DOUBLE)
   Note: Contains historical timeseries candlestick data. Use CANDLE_TIME to filter or sort by date/time.

3. GOLD_TREECHART:
   - SYMBOL (VARCHAR)
   - AVG_PRICE (DOUBLE) (Average stock price for latest day)
   - VOLATILITY (DOUBLE) (All-time standard deviation of the stock)
   - RELATIVE_VOLATILITY (DOUBLE) (Relative volatility coefficient)
   Note: Contains exactly one row per stock symbol representing volatility rankings. Do NOT sort by date/time columns when querying this table.
"""

# Define the State Schema for LangGraph
class AgentState(TypedDict):
    query: str
    symbol: Optional[str]
    intent: Optional[str]
    sql_query: Optional[str]
    sql_error: Optional[str]
    sql_results: Optional[List[Any]]
    sql_columns: Optional[List[str]]
    news_context: Optional[str]
    response: Optional[str]
    sql_retry_count: int

# Pydantic schemas for structured LLM outputs
class IntentDetection(BaseModel):
    symbol: Optional[str] = Field(description="The stock ticker symbol mentioned (AAPL, MSFT, GOOGL, AMZN, TSLA, NVDA) or null if not applicable.")
    intent: str = Field(description="The query intent: 'structured' (for purely quantitative metrics/prices), 'unstructured' (for news/sentiment), or 'hybrid' (for questions requiring both news reasons and numbers/prices).")

# Helper functions
def get_ollama_embedding(text: str) -> list:
    """Generate embedding using local Ollama model."""
    response = ollama.embeddings(model="nomic-embed-text", prompt=text)
    return response["embedding"]

def get_snowflake_connection():
    """Establish a connection to Snowflake using environment credentials."""
    return snowflake.connector.connect(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        role=os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
        database=SNOWFLAKE_DB,
        schema=SNOWFLAKE_SCHEMA
    )

def extract_json(text: str) -> str:
    """Extracts a JSON substring from a text that might contain conversational filler or markdown blocks."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
        
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_str = text[first_brace:last_brace+1]
        # Normalize single quotes to double quotes for keys and values
        import re
        json_str = re.sub(r"\'(\w+)\'\s*:", r'"\1":', json_str)
        json_str = re.sub(r":\s*\'([^']*)\'", r': "\1"', json_str)
        json_str = re.sub(r"\'(\w+)\'", r'"\1"', json_str)
        return json_str
    return text

# --- GRAPH NODES ---

def detect_intent_node(state: AgentState) -> Dict[str, Any]:
    """Detects query intent and target stock ticker."""
    print("\n--- [Node] Detect Intent ---")
    query = state["query"]
    
    prompt = f"""Analyze the user query: '{query}'
Identify:
1. The stock symbol mentioned: Choose from ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA']. If none of these are mentioned or applicable, use null.
2. The query intent: 
   - 'structured': for purely quantitative numbers, stock prices, volumes, KPIs, average price, volatility.
   - 'unstructured': for news, reasons behind events, general sentiment, qualitative queries.
   - 'hybrid': for questions requiring both numerical data (price, change, etc.) AND news/reasons.

You must respond ONLY with a raw JSON object matching this format:
{{
  "symbol": "TICKER_OR_NULL",
  "intent": "structured_or_unstructured_or_hybrid"
}}

Respond with the raw JSON object only. Do not include any explanation or markdown formatting."""

    try:
        res_text = generate_text(
            prompt=prompt,
            system_instruction="You are a financial analyst routing queries. Categorize the intent and extract stock symbols."
        )
        # Parse JSON
        clean_text = extract_json(res_text)
        data = json.loads(clean_text)
        # Standardize symbol to uppercase if not None
        sym = data.get("symbol")
        if isinstance(sym, str):
            sym = sym.strip().upper()
            if sym not in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA']:
                sym = None
        else:
            sym = None
            
        print(f"Detected Intent: {data.get('intent')}, Symbol: {sym}")
        return {
            "intent": data.get("intent", "unstructured"),
            "symbol": sym,
            "sql_retry_count": 0
        }
    except Exception as e:
        print(f"Error in intent detection: {e}. Falling back to unstructured.")
        return {"intent": "unstructured", "symbol": None, "sql_retry_count": 0}

def write_sql_node(state: AgentState) -> Dict[str, Any]:
    """Generates a Snowflake SQL query based on the user's intent and table schema."""
    print("\n--- [Node] Write SQL ---")
    query = state["query"]
    
    prompt = f"""
    User Query: {query}
    
    {SCHEMA_DESC}
    
    Write a single Snowflake SQL query to retrieve the quantitative data requested in the user query.
    Rules:
    - Only write SQL to retrieve numbers/prices/KPIs (e.g. CURRENT_PRICE, CHANGE_PERCENT, AVG_PRICE, VOLATILITY, CANDLE_CLOSE).
    - Do NOT write SQL trying to answer qualitative questions like 'why it dropped' or 'reasons'. Those are handled by our news database.
    - Write exactly ONE single SELECT statement. Do not output multiple queries separated by semicolons.
    - Use uppercase for all table names and column names.
    - Return ONLY the raw SQL query. Do not wrap it in markdown code blocks or add explanations.
    """
    
    try:
        sql_query = generate_text(
            prompt=prompt,
            system_instruction="You are an expert SQL translator converting natural language to Snowflake SQL. Return ONLY raw SQL text."
        )
        # Clean markdown code block wraps if model hallucinated them
        if sql_query.startswith("```sql"):
            sql_query = sql_query.replace("```sql", "", 1)
        if sql_query.startswith("```"):
            sql_query = sql_query.replace("```", "", 1)
        if sql_query.endswith("```"):
            sql_query = sql_query[:-3]
        sql_query = sql_query.strip()
        
        print(f"Generated SQL:\n{sql_query}")
        return {"sql_query": sql_query}
    except Exception as e:
        print(f"Error generating SQL: {e}")
        return {"sql_error": str(e)}

def execute_sql_node(state: AgentState) -> Dict[str, Any]:
    """Executes the generated SQL query in Snowflake."""
    print("\n--- [Node] Execute SQL ---")
    sql_query = state.get("sql_query")
    if not sql_query:
        return {"sql_error": "No SQL query generated"}
        
    try:
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        cursor.execute(sql_query)
        results = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
        cursor.close()
        conn.close()
        
        print(f"SQL execution succeeded. Returned {len(results)} rows.")
        return {"sql_results": results, "sql_columns": columns, "sql_error": None}
    except Exception as e:
        print(f"SQL Execution Failed: {e}")
        return {"sql_error": str(e), "sql_retry_count": state.get("sql_retry_count", 0) + 1}

def correct_sql_node(state: AgentState) -> Dict[str, Any]:
    """Self-corrects the SQL query using the compiler/execution error message."""
    print("\n--- [Node] Correct SQL ---")
    failed_sql = state["sql_query"]
    error_msg = state["sql_error"]
    original_query = state["query"]
    retry_count = state["sql_retry_count"]
    
    prompt = f"""
    The original question was: {original_query}
    
    The database schema is:
    {SCHEMA_DESC}
    
    The generated SQL query was:
    {failed_sql}
    
    This query failed with the following Snowflake error:
    {error_msg}
    
    Please correct the SQL query to fix the error.
    Rules:
    - Only write SQL to retrieve numbers/prices/KPIs (e.g. CURRENT_PRICE, CHANGE_PERCENT, AVG_PRICE, VOLATILITY, CANDLE_CLOSE).
    - Do NOT write SQL trying to answer qualitative questions like 'why it dropped' or 'reasons'. Those are handled by our news database.
    - Write exactly ONE single SELECT statement. Do not output multiple queries separated by semicolons.
    - Return ONLY the corrected raw SQL query. Do not wrap it in markdown code blocks or add explanations.
    """
    
    try:
        corrected_sql = generate_text(
            prompt=prompt,
            system_instruction="You are an expert SQL debugging assistant. Review the SQL query and the database error message, correct the SQL, and return ONLY the raw SQL code."
        )
        if corrected_sql.startswith("```sql"):
            corrected_sql = corrected_sql.replace("```sql", "", 1)
        if corrected_sql.startswith("```"):
            corrected_sql = corrected_sql.replace("```", "", 1)
        if corrected_sql.endswith("```"):
            corrected_sql = corrected_sql[:-3]
        corrected_sql = corrected_sql.strip()
        
        print(f"Corrected SQL (Attempt {retry_count}):\n{corrected_sql}")
        return {"sql_query": corrected_sql}
    except Exception as e:
        print(f"Error correcting SQL: {e}")
        return {"sql_error": str(e)}

def retrieve_news_node(state: AgentState) -> Dict[str, Any]:
    """Retrieves context from ChromaDB using local Ollama embeddings."""
    print("\n--- [Node] Retrieve News ---")
    query = state["query"]
    symbol = state.get("symbol")
    
    try:
        chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
        
        # Check if vector DB has documents
        if collection.count() == 0:
            print("Vector store is empty.")
            return {"news_context": "No news articles found in the database."}
            
        print("Generating embedding for query...")
        query_embedding = get_ollama_embedding(query)
        
        # Apply filter on ticker symbol if detected
        where_filter = {"symbol": symbol} if symbol else None
        
        print(f"Querying ChromaDB (filter={where_filter})...")
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=5,
            where=where_filter
        )
        
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        
        if not documents:
            print("No relevant news documents matched.")
            return {"news_context": f"No relevant news articles found for symbol '{symbol}'."}
            
        context_parts = []
        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            title = meta.get("title", "Unknown")
            publisher = meta.get("publisher", "Unknown")
            pub_date = meta.get("pub_date", "Unknown")
            link = meta.get("link", "#")
            context_parts.append(
                f"[{i+1}] Title: {title}\nPublisher: {publisher}\nDate: {pub_date}\nLink: {link}\nContent:\n{doc}\n"
            )
            
        news_context = "\n---\n".join(context_parts)
        print(f"Retrieved {len(documents)} news articles from vector database.")
        return {"news_context": news_context}
    except Exception as e:
        print(f"Error retrieving news: {e}")
        return {"news_context": f"Error retrieving news: {e}"}

def synthesize_response_node(state: AgentState) -> Dict[str, Any]:
    """Synthesizes SQL results and news context into a cohesive final financial report."""
    print("\n--- [Node] Synthesize Response ---")
    query = state["query"]
    sql_results = state.get("sql_results")
    sql_columns = state.get("sql_columns")
    sql_error = state.get("sql_error")
    news_context = state.get("news_context")
    
    prompt = f"""
    User Question: {query}
    
    --- DATA SOURCES ---
    """
    
    if sql_results is not None:
        prompt += f"\n1. Database Query Results (Snowflake):\nColumns: {sql_columns}\nRows:\n{sql_results}\n"
    elif sql_error:
        prompt += f"\n1. Database Query Error:\n{sql_error}\n"
        
    if news_context:
        prompt += f"\n2. Relevant Financial News Articles:\n{news_context}\n"
        
    prompt += """
    Based on the above structured data and news headlines, generate a professional, clear, and comprehensive response.
    Rules:
    - Ground your response in the provided data. Do not hallucinate prices or details.
    - Format numerical data clearly (e.g. format double/float columns as currency, percentages, etc.).
    - Reference specific news sources (e.g., Reuters, Yahoo Finance) and cite the publication dates when discussing news items.
    - If a database error occurred, explain what you tried to query and summarize the results using the news headlines, noting the database limitation.
    """
    
    try:
        response_text = generate_text(
            prompt=prompt,
            system_instruction="You are an elite Autonomous Financial Analyst. You synthesize hard numbers from relational databases and context from vector news sources into insights."
        )
        return {"response": response_text}
    except Exception as e:
        print(f"Error synthesizing response: {e}")
        return {"response": f"Error generating final response: {e}"}

# --- LANGGRAPH FLOW ROUTING ---

def route_after_intent(state: AgentState):
    intent = state["intent"]
    if intent == "structured" or intent == "hybrid":
        return "write_sql"
    else:
        return "retrieve_news"

def route_after_sql_execution(state: AgentState):
    if state.get("sql_error"):
        if state.get("sql_retry_count", 0) < 3:
            return "correct_sql"
        else:
            return "synthesize_response"  # Abort correction, synthesize with what we have
            
    if state["intent"] == "hybrid":
        return "retrieve_news"
    return "synthesize_response"

# --- COMPILE STATE GRAPH ---

def build_agent_graph():
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("detect_intent", detect_intent_node)
    workflow.add_node("write_sql", write_sql_node)
    workflow.add_node("execute_sql", execute_sql_node)
    workflow.add_node("correct_sql", correct_sql_node)
    workflow.add_node("retrieve_news", retrieve_news_node)
    workflow.add_node("synthesize_response", synthesize_response_node)
    
    # Set Entry Point
    workflow.set_entry_point("detect_intent")
    
    # Add Edges
    workflow.add_conditional_edges(
        "detect_intent",
        route_after_intent,
        {
            "write_sql": "write_sql",
            "retrieve_news": "retrieve_news"
        }
    )
    
    workflow.add_edge("write_sql", "execute_sql")
    
    workflow.add_conditional_edges(
        "execute_sql",
        route_after_sql_execution,
        {
            "correct_sql": "correct_sql",
            "retrieve_news": "retrieve_news",
            "synthesize_response": "synthesize_response"
        }
    )
    
    workflow.add_edge("correct_sql", "execute_sql")
    workflow.add_edge("retrieve_news", "synthesize_response")
    workflow.add_edge("synthesize_response", END)
    
    return workflow.compile()

# --- CONVENIENCE EXECUTION FUNCTION ---

def run_agent(query: str) -> str:
    """Run the agentic workflow for a given query and return the final report."""
    app = build_agent_graph()
    initial_state = {
        "query": query,
        "symbol": None,
        "intent": None,
        "sql_query": None,
        "sql_error": None,
        "sql_results": None,
        "sql_columns": None,
        "news_context": None,
        "response": None,
        "sql_retry_count": 0
    }
    
    final_output = app.invoke(initial_state)
    return final_output["response"]

if __name__ == "__main__":
    # Test query
    test_query = "Why did Tesla drop recently and what is its current stock price and price change?"
    print(f"Running Agent with test query: '{test_query}'")
    report = run_agent(test_query)
    print("\n================ FINAL REPORT ================")
    print(report)
    print("==============================================")
