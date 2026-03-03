"""Settings page for Open Brain Dashboard"""

import streamlit as st
import yaml
import subprocess
from pathlib import Path

st.set_page_config(page_title="Settings - Open Brain", page_icon="⚙️")

st.title("⚙️ Settings")

# Load current settings
config_path = Path(__file__).parent.parent / "config" / "settings.yaml"

try:
    with open(config_path, 'r') as f:
        settings = yaml.safe_load(f)
except:
    settings = {}

with st.form("settings_form"):
    st.subheader("📀 Database")
    col1, col2 = st.columns(2)
    with col1:
        db_host = st.text_input("Host", value=settings.get('database', {}).get('host', 'postgres'))
        db_name = st.text_input("Database Name", value=settings.get('database', {}).get('name', 'openbrain'))
        db_user = st.text_input("User", value=settings.get('database', {}).get('user', 'postgres'))
    with col2:
        db_port = st.number_input("Port", value=settings.get('database', {}).get('port', 5432), min_value=1, max_value=65535, step=1)
        db_password = st.text_input("Password", type="password", value=settings.get('database', {}).get('password', ''))
    
    st.subheader("🧠 Embedding Provider")
    col1, col2 = st.columns(2)
    with col1:
        embedder_provider = st.selectbox("Provider", ["openrouter", "openai", "ollama", "custom"], 
            index=["openrouter", "openai", "ollama", "custom"].index(settings.get('embedder', {}).get('provider', 'openrouter')))
    with col2:
        embedder_model = st.text_input("Model", value=settings.get('embedder', {}).get('model', 'text-embedding-3-small'))
    
    st.subheader("🌐 Server Ports")
    col1, col2, col3 = st.columns(3)
    with col1:
        api_port = st.number_input("API Port", value=settings.get('api', {}).get('port', 8000), min_value=1, max_value=65535)
    with col2:
        mcp_port = st.number_input("MCP Port", value=settings.get('mcp', {}).get('port', 8080), min_value=1, max_value=65535)
    with col3:
        dashboard_port = st.number_input("Dashboard Port", value=settings.get('dashboard', {}).get('port', 8501), min_value=1, max_value=65535)
    
    st.subheader("🔒 Security")
    col1, col2 = st.columns(2)
    with col1:
        security_mode = st.selectbox("Mode", ["direct", "sandbox"], 
            index=["direct", "sandbox"].index(settings.get('security', {}).get('mode', 'direct')))
    with col2:
        st.write("")
        st.write("")
        if st.form_submit_button("🚀 Restart in Sandbox Mode", type="primary"):
            # Save settings first
            new_settings = {
                'database': {
                    'host': db_host,
                    'port': int(db_port),
                    'name': db_name,
                    'user': db_user,
                    'password': db_password,
                },
                'embedder': {
                    'provider': embedder_provider,
                    'model': embedder_model,
                    'dimensions': settings.get('embedder', {}).get('dimensions', 768),
                },
                'api': {
                    'host': '0.0.0.0',
                    'port': int(api_port),
                    'cors_origins': ['*'],
                },
                'mcp': {
                    'host': '0.0.0.0',
                    'port': int(mcp_port),
                },
                'dashboard': {
                    'port': int(dashboard_port),
                },
                'tags': settings.get('tags', {'deny_list': ['password', 'secret', 'api_key'], 'default_tags': ['auto']}),
                'analytics': settings.get('analytics', {'trend_weeks': 4, 'weekly_report_day': 6}),
                'security': {'mode': 'sandbox'},
            }
            
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w') as f:
                yaml.dump(new_settings, f, default_flow_style=False)
            
            # Restart in sandbox mode
            try:
                subprocess.run(["docker", "compose", "restart"], cwd="/app", check=True)
                st.success("✅ Restarting in sandbox mode!")
            except:
                st.success("✅ Settings saved! Run `docker compose restart` to apply sandbox mode.")
    
    submitted = st.form_submit_button("💾 Save Settings", type="secondary")
    
    if submitted:
        new_settings = {
            'database': {
                'host': db_host,
                'port': int(db_port),
                'name': db_name,
                'user': db_user,
                'password': db_password,
            },
            'embedder': {
                'provider': embedder_provider,
                'model': embedder_model,
                'dimensions': settings.get('embedder', {}).get('dimensions', 768),
            },
            'api': {
                'host': '0.0.0.0',
                'port': int(api_port),
                'cors_origins': ['*'],
            },
            'mcp': {
                'host': '0.0.0.0',
                'port': int(mcp_port),
            },
            'dashboard': {
                'port': int(dashboard_port),
            },
            'tags': settings.get('tags', {'deny_list': ['password', 'secret', 'api_key'], 'default_tags': ['auto']}),
            'analytics': settings.get('analytics', {'trend_weeks': 4, 'weekly_report_day': 6}),
            'security': {'mode': security_mode},
        }
        
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w') as f:
            yaml.dump(new_settings, f, default_flow_style=False)
        
        st.success("✅ Settings saved!")

st.markdown("---")
st.caption("🧠 Open Brain v1.0 - Personal Semantic Memory System")
