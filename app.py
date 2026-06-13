import streamlit as st
import os
import time
from dotenv import load_dotenv
import importlib
import agent_brain
importlib.reload(agent_brain)
from agent_brain import build_agent_graph, AgentState

# Page configurations
st.set_page_config(
    page_title="Aegis AI | Autonomous Financial Analyst",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Design & Aesthetics
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Plus+Jakarta+Sans:wght@300;400;500;700&display=swap');
    
    /* Global Styles */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    /* Header Card styling with Gradient */
    .header-box {
        background: linear-gradient(135deg, #1e1b4b 0%, #311042 50%, #030712 100%);
        padding: 2.5rem;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        margin-bottom: 2rem;
    }
    .header-title {
        font-family: 'Outfit', sans-serif;
        font-weight: 800;
        font-size: 2.8rem;
        background: linear-gradient(90deg, #38bdf8, #c084fc);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .header-subtitle {
        color: #9ca3af;
        font-size: 1.1rem;
        margin-top: 0.5rem;
        margin-bottom: 0;
    }
    
    /* Custom Sidebar styling */
    .sidebar-section {
        background-color: rgba(255, 255, 255, 0.03);
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        margin-bottom: 1rem;
    }
    
    /* Step Cards during execution */
    .step-card {
        padding: 0.75rem 1rem;
        border-radius: 8px;
        background-color: #0f172a;
        border-left: 4px solid #c084fc;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
        color: #e2e8f0;
    }
    .step-card.success {
        border-left-color: #34d399;
    }
    .step-card.active {
        border-left-color: #38bdf8;
        animation: pulse 1.5s infinite;
    }
    
    @keyframes pulse {
        0% { opacity: 0.6; }
        50% { opacity: 1; }
        100% { opacity: 0.6; }
    }
</style>
""", unsafe_allow_html=True)

# App Title Box
st.markdown("""
<div class="header-box">
    <h1 class="header-title">AEGIS ANALYST</h1>
    <p class="header-subtitle">Autonomous Financial Agent connecting Snowflake Gold-Layer Tables and ChromaDB Vector News</p>
</div>
""", unsafe_allow_html=True)

# Sidebar configurations
with st.sidebar:
    st.markdown("### 🛠️ System Control Panel")
    
    # Ollama LLM Config
    st.markdown("<div class='sidebar-section'>", unsafe_allow_html=True)
    st.markdown("**🤖 Language Model (Local)**")
    local_model = st.text_input("Ollama Model", value=os.getenv("LOCAL_LLM_MODEL", "gemma2:2b"))
    os.environ["LOCAL_LLM_MODEL"] = local_model
    st.markdown("Status: **Ollama Active**")
    st.markdown("</div>", unsafe_allow_html=True)
            
    # Check Snowflake Configuration
    st.markdown("<div class='sidebar-section'>", unsafe_allow_html=True)
    st.markdown("**❄️ Snowflake Connection**")
    st.code(f"Account: {os.getenv('SNOWFLAKE_ACCOUNT')}\nUser: {os.getenv('SNOWFLAKE_USER')}\nDB: STOCKS_MDS\nSchema: COMMON")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Vector Database Info
    st.markdown("<div class='sidebar-section'>", unsafe_allow_html=True)
    st.markdown("**🗄️ Vector Database**")
    st.markdown("- Store: **ChromaDB** (Local)")
    st.markdown("- Embeddings: **Ollama (`nomic-embed-text`)**")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Supported Stocks List
    st.markdown("### 📈 Tracked Assets")
    st.markdown("`AAPL` | `MSFT` | `GOOGL` | `AMZN` | `TSLA` | `NVDA`")

# Suggestions / Quick Prompts
st.markdown("### 💡 Try asking:")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Why did Tesla drop recently?"):
        st.session_state.query = "Why did Tesla (TSLA) drop recently and what is its current stock price and change percent?"
with col2:
    if st.button("Which stock is most volatile?"):
        st.session_state.query = "Which stock is the most volatile in the database and what are the average prices?"
with col3:
    if st.button("Compare NVDA and AAPL performance"):
        st.session_state.query = "Compare NVDA and AAPL latest prices, change percents, and news context."

# Main query input
if "query" not in st.session_state:
    st.session_state.query = ""

user_query = st.text_input(
    "Enter your analysis query:",
    value=st.session_state.query,
    placeholder="e.g., Explain why Microsoft is dropping today and show its latest KPI metrics.",
    key="query_input"
)

# Run Agent button
if st.button("🚀 Analyze Market Data", type="primary") and user_query:
    # Clear query cache to prevent input field issues
    st.session_state.query = user_query
    
    # Create execution spaces
    status_header = st.empty()
    status_box = st.container()
    report_box = st.empty()
    details_box = st.container()
    
    status_header.markdown("### 🧠 Agent Execution Steps")
    
    # Initialize graph
    app = build_agent_graph()
    initial_state = {
        "query": user_query,
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
    
    # Keep track of UI representations of steps
    steps_history = []
    
    def render_steps():
        with status_box:
            for idx, (name, status) in enumerate(steps_history):
                cls = "success" if status == "done" else "active"
                st.markdown(f"<div class='step-card {cls}'><b>Step {idx+1}:</b> {name}</div>", unsafe_allow_html=True)
    
    # Stream the LangGraph execution
    try:
        current_state = initial_state
        
        # Start streaming nodes
        for event in app.stream(initial_state):
            for node_name, node_output in event.items():
                current_state.update(node_output)
                
                if node_name == "detect_intent":
                    steps_history.append((f"Intent Detected: <b>{current_state['intent'].upper()}</b> (Asset: <b>{current_state['symbol']}</b>)", "done"))
                elif node_name == "write_sql":
                    steps_history.append(("Snowflake SQL generated", "done"))
                elif node_name == "execute_sql":
                    if current_state.get("sql_error"):
                        steps_history.append((f"SQL Execution failed: <span style='color:#f87171'>{current_state['sql_error'][:100]}...</span>", "active"))
                    else:
                        steps_history.append((f"SQL Executed successfully on Snowflake (Returned {len(current_state.get('sql_results', []))} rows)", "done"))
                elif node_name == "correct_sql":
                    steps_history.append((f"Auto-correcting SQL (Attempt {current_state.get('sql_retry_count', 0)})...", "done"))
                elif node_name == "retrieve_news":
                    steps_history.append(("Retrieved news matching queries from ChromaDB Vector Store", "done"))
                elif node_name == "synthesize_response":
                    steps_history.append(("Synthesizing metrics and news headlines into markdown report", "done"))
                
                render_steps()
                time.sleep(0.5)
        
        # Print Final Report
        report_box.markdown("---")
        report_box.markdown("## 📊 Autonomous Analyst Report")
        report_box.markdown(current_state["response"])
        
        # Display raw query/results in tabs
        with details_box:
            st.markdown("### 🔍 Technical Details")
            tab1, tab2, tab3 = st.tabs(["💻 Snowflake SQL Query", "🔢 Database Rows", "📰 Retrieved Vector News"])
            
            with tab1:
                if current_state.get("sql_query"):
                    st.code(current_state["sql_query"], language="sql")
                else:
                    st.write("No SQL query executed.")
                    
            with tab2:
                if current_state.get("sql_results") is not None:
                    import pandas as pd
                    df = pd.DataFrame(current_state["sql_results"], columns=current_state.get("sql_columns", []))
                    st.dataframe(df, use_container_width=True)
                else:
                    st.write("No SQL query results.")
                    
            with tab3:
                if current_state.get("news_context"):
                    st.text_area("Vector Search Results", current_state["news_context"], height=300)
                else:
                    st.write("No news articles retrieved.")
                    
    except Exception as ex:
        st.error(f"An error occurred during workflow execution: {ex}")
