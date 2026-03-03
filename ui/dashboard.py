"""Open Brain Dashboard - Elegant Minimalist Design"""

import streamlit as st
import requests
import pandas as pd
import yaml
from datetime import datetime
from pathlib import Path

# Config
st.set_page_config(page_title="Open Brain", page_icon="🧠", layout="wide")

# Simple minimalist CSS
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    
    * { font-family: 'Inter', sans-serif !important; }
    
    :root {
        --bg: #111111;
        --surface: #1a1a1a;
        --border: #333333;
        --text: #ffffff;
        --text-dim: #888888;
        --accent: #3b82f6;
    }
    
    html, body, .stApp { background: var(--bg) !important; color: var(--text) !important; }
    
    [data-testid="stSidebar"] { background: var(--surface) !important; border-right: 1px solid var(--border); }
    
    h1, h2, h3, p, span, div, label { font-family: 'Inter', sans-serif !important; color: var(--text) !important; }
    h1 { font-size: 1.25rem !important; font-weight: 500 !important; margin: 0 !important; }
    h2 { font-size: 1rem !important; font-weight: 500 !important; }
    p { font-size: 0.875rem !important; margin: 0 !important; }
    
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div > div {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        color: var(--text) !important;
        border-radius: 6px !important;
    }
    
    .stButton > button {
        background: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        font-size: 0.875rem !important;
        width: 100%;
        text-align: left;
        padding: 12px 16px !important;
    }
    
    .stButton > button:hover {
        border-color: var(--accent) !important;
    }
    
    .stButton > button[kind="primary"] {
        background: var(--accent) !important;
        color: white !important;
        border: none !important;
    }
    
    [data-testid="stHeader"] { display: none !important; }
    
    /* Hide Streamlit keyboard shortcut hints */
    div[data-testid="stTooltipIcon"] { display: none !important; }
    [class*="keyboard"] { display: none !important; }
    
    .card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    
    .nav-btn { margin-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# API
API = "http://localhost:8000"

def get_stats():
    try: return requests.get(f"{API}/stats", timeout=5).json()
    except: return {"total": 0, "this_week": 0, "by_source": {}, "top_tags": {}}

def search(q, limit=20):
    try: return requests.get(f"{API}/memories/search", params={"query": q, "limit": limit}, timeout=10).json()
    except: return []

def create(content, source="dashboard", tags=None):
    try: return requests.post(f"{API}/memories", json={"content": content, "source": source, "tags": tags or []}, timeout=10).json()
    except: return {"error": "Failed"}

# Initialize session state for page
if 'page' not in st.session_state:
    st.session_state.page = "Search"

# Sidebar with buttons
with st.sidebar:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.image("ui/logo.jpg", width=60)
    with col2:
        st.markdown("**Open Brain**")
    st.markdown("---")
    
    stats = get_stats()
    st.metric("Total", stats.get("total", 0))
    st.metric("This Week", stats.get("this_week", 0))
    
    st.markdown("---")
    
    # Flat buttons for navigation
    if st.button("Search", use_container_width=True):
        st.session_state.page = "Search"
    if st.button("Create", use_container_width=True):
        st.session_state.page = "Create"
    if st.button("Stats", use_container_width=True):
        st.session_state.page = "Stats"
    if st.button("Settings", use_container_width=True):
        st.session_state.page = "Settings"

# Main content
page = st.session_state.page

if page == "Search":
    st.title("Search")
    q = st.text_input("", placeholder="Search memories...")
    
    if q:
        results = search(q)
        for mem in results:
            st.markdown(f"""
            <div class="card">
                <p>{mem.get("content", "")[:200]}</p>
                <p style="color: var(--text-dim); margin-top: 8px;">{mem.get("source", "")} • {", ".join(mem.get("tags", [])[:3])}</p>
            </div>
            """, unsafe_allow_html=True)

elif page == "Create":
    st.title("Create")
    content = st.text_area("", placeholder="What do you want to remember?", height=120)
    
    c1, c2 = st.columns([3, 1])
    source = c1.selectbox("Source", ["manual", "telegram", "whatsapp", "email"])
    tags = c2.text_input("Tags", placeholder="ai, idea")
    
    if st.button("Save Memory", type="primary"):
        if content:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            result = create(content, source, tag_list)
            if result.get("id"): 
                st.success("Saved!")
            else: 
                st.error("Error")

elif page == "Stats":
    st.title("Stats")
    stats = get_stats()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", stats.get("total", 0))
    c2.metric("Week", stats.get("this_week", 0))
    c3.metric("Sources", len(stats.get("by_source", {})))
    
    if stats.get("by_source"):
        st.bar_chart(pd.DataFrame(list(stats["by_source"].items()), columns=["Source", "Count"]).set_index("Source"))

elif page == "Settings":
    st.title("Settings")
    
    # Load settings
    config_path = Path("config/settings.yaml")
    if config_path.exists():
        with open(config_path) as f:
            settings = yaml.safe_load(f) or {}
    else:
        settings = {}
    
    with st.form("settings"):
        st.subheader("Database")
        db = settings.get("database", {})
        c1, c2 = st.columns(2)
        db_host = c1.text_input("Host", db.get("host", "postgres"))
        db_port = c2.number_input("Port", value=db.get("port", 5432), min_value=1, max_value=65535, step=1)
        c1, c2 = st.columns(2)
        db_name = c1.text_input("Name", db.get("name", "openbrain"))
        db_user = c2.text_input("User", db.get("user", "postgres"))
        
        st.subheader("Embedder")
        emb = settings.get("embedder", {})
        c1, c2 = st.columns(2)
        emb_provider = c1.selectbox("Provider", ["openrouter", "openai", "ollama", "custom"], 
            ["openrouter", "openai", "ollama", "custom"].index(emb.get("provider", "openrouter")))
        emb_model = c2.text_input("Model", emb.get("model", "text-embedding-3-small"))
        
        st.subheader("Security")
        sec = settings.get("security", {})
        sec_mode = st.selectbox("Mode", ["direct", "sandbox"],
            ["direct", "sandbox"].index(sec.get("mode", "direct")))
        
        if st.form_submit_button("Save"):
            settings["database"] = {"host": db_host, "port": int(db_port), "name": db_name, "user": db_user, "password": db.get("password", "")}
            settings["embedder"] = {"provider": emb_provider, "model": emb_model, "dimensions": emb.get("dimensions", 768)}
            settings["security"] = {"mode": sec_mode}
            settings["api"] = settings.get("api", {"host": "0.0.0.0", "port": 8000})
            settings["mcp"] = settings.get("mcp", {"host": "0.0.0.0", "port": 8080})
            settings["dashboard"] = settings.get("dashboard", {"port": 8501})
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                yaml.dump(settings, f)
            st.success("Saved! Restart containers to apply.")

st.caption(f"Updated: {datetime.now().strftime('%H:%M')}")
