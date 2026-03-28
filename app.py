import streamlit as st
import requests
import base64
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import urllib3

# --- ⚙️ Configuration ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Constants & Secrets
GITHUB_TOKEN = st.secrets.get("MY_GITHUB_TOKEN", "REPLACE_ME")
REPO_NAME = st.secrets.get("REPO_NAME", 'ogihara-hiroki/my-dashboard')
STATUS_FILE = 'status.txt'
TOGGL_TOKEN = st.secrets.get("TOGGL_TOKEN", "REPLACE_ME")
TOGGL_WORKSPACE_ID = st.secrets.get("TOGGL_WORKSPACE_ID", "REPLACE_ME")

# Log sampling interval (seconds)
SAMPLING_INTERVAL = 10 

APP_CATEGORIES = {
    'Automation Studio (設計)': ['automation studio'],
    'IDE (開発)': ['visual studio', 'vscode', 'intellij', 'pycharm', 'cursor'],
    'Excel (作業/資料)': ['excel'],
    'ブラウザ (調査/メール)': ['chrome', 'edge', 'firefox', 'safari'],
    'フォルダ (探す無駄)': ['エクスプローラー', 'folder', 'finder'],
    'コミュニケーション': ['slack', 'teams', 'zoom', 'discord', 'line'],
    'その他': []
}

st.set_page_config(
    page_title="Work Analysis Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 🛠️ Logic ---

def update_github_status(status_text):
    """Updates the status.txt file on GitHub to control remote logging."""
    if GITHUB_TOKEN == "REPLACE_ME":
        return
    try:
        url = f"https://api.github.com/repos/{REPO_NAME}/contents/{STATUS_FILE}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        res = requests.get(url, headers=headers).json()
        if 'sha' not in res:
            return
        
        sha = res['sha']
        content = base64.b64encode(status_text.encode('utf-8')).decode('utf-8')
        data = {"message": f"Switch to {status_text}", "content": content, "sha": sha}
        res_put = requests.put(url, headers=headers, json=data)
        if res_put.status_code == 200:
            st.toast(f"GitHub Status Updated: {status_text}", icon="✅")
    except Exception as e:
        st.error(f"GitHub Update Failed: {e}")

@st.cache_data(ttl=600)
def get_pc_analysis(target_date_val, mode="日次"):
    """Fetches and analyzes PC usage logs from GitHub."""
    try:
        url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/pc_usage_log.csv"
        df_log = pd.read_csv(url, encoding='utf-8-sig', names=['timestamp', 'window_title'], header=None)
        df_log['timestamp'] = pd.to_datetime(df_log['timestamp'], errors='coerce')
        df_log = df_log.dropna(subset=['timestamp'])
        
        if mode == "日次":
            df_filtered = df_log[df_log['timestamp'].dt.date == target_date_val].copy()
            period_text = f"({target_date_val})"
        else:
            start_of_week = target_date_val - timedelta(days=target_date_val.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            df_filtered = df_log[(df_log['timestamp'].dt.date >= start_of_week) & (df_log['timestamp'].dt.date <= end_of_week)].copy()
            period_text = f"({start_of_week} 〜 {end_of_week})"
            
        if df_filtered.empty:
            return None, period_text
            
        def detect_app(title):
            title = str(title).lower()
            for cat, keywords in APP_CATEGORIES.items():
                if any(kw in title for kw in keywords):
                    return cat
            return 'その他'
            
        df_filtered['アプリ'] = df_filtered['window_title'].apply(detect_app)
        df_res = df_filtered['アプリ'].value_counts().reset_index()
        df_res.columns = ['アプリ', '合計時間(h)']
        # Convert sampling counts to hours
        df_res['合計時間(h)'] = round(df_res['合計時間(h)'] * SAMPLING_INTERVAL / 3600, 2)
        return df_res, period_text
    except Exception as e:
        return None, ""

@st.cache_data(ttl=300)
def get_toggl_analysis(target_date_val, mode="日次"):
    """Fetches time entries from Toggl Track API v3."""
    if TOGGL_TOKEN == "REPLACE_ME":
        return None
    try:
        if mode == "日次":
            start_date, end_date = target_date_val.strftime('%Y-%m-%d'), target_date_val.strftime('%Y-%m-%d')
        else:
            start_of_week = target_date_val - timedelta(days=target_date_val.weekday())
            start_date = start_of_week.strftime('%Y-%m-%d')
            end_date = (start_of_week + timedelta(days=6)).strftime('%Y-%m-%d')

        url = f"https://api.track.toggl.com/reports/api/v3/workspace/{TOGGL_WORKSPACE_ID}/summary/time_entries"
        auth = base64.b64encode(f"{TOGGL_TOKEN}:api_token".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        
        payload = {"start_date": start_date, "end_date": end_date}
        res = requests.post(url, headers=headers, json=payload)
        
        if res.status_code != 200:
            if res.status_code == 402:
                st.warning("Toggl API limit reached (402). Using cached data.")
            elif res.status_code == 401:
                st.error("Toggl Authentication failed. Check your token.")
            return None
        
        raw_data = res.json()
        entries = []
        for item in raw_data:
            title_info = item.get('title', {})
            name = title_info.get('description') or title_info.get('project') or "名称未設定"
            sec = item.get('seconds', 0)
            if sec > 0:
                entries.append({'作業内容': name, '時間(h)': round(sec / 3600, 2)})
        
        if not entries:
            return None
            
        df = pd.DataFrame(entries).groupby('作業内容')['時間(h)'].sum().reset_index()
        return df.sort_values('時間(h)', ascending=False)
    except Exception as e:
        st.error(f"Toggl Fetch Error: {e}")
        return None

# --- 🎨 UI Components ---

# Custom CSS for Premium Look
st.markdown("""
<style>
    .main {
        background: linear-gradient(135deg, #1e1e2f 0%, #2d2d44 100%);
        color: #ffffff;
    }
    .stMetric {
        background: rgba(255, 255, 255, 0.05);
        padding: 15px;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(5px);
    }
    .stTable {
        background: rgba(255, 255, 255, 0.02);
        border-radius: 10px;
    }
    h1, h2, h3 {
        color: #00d2ff !important;
        font-family: 'Inter', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.header("📊 Settings")
    analysis_mode = st.radio("Range:", ["日次", "週次"])
    target_date = st.date_input("Target Date:", date.today())
    
    st.markdown("---")
    st.header("🎮 Remote Control")
    is_logging = st.checkbox("Enable PC Tracking", help="Triggers the remote logger via GitHub")
    if is_logging:
        update_github_status("ON")
        st.success("Remote: ON")
    else:
        update_github_status("OFF")
        st.warning("Remote: OFF")

# Main Content
st.title(f"🚀 Work Analysis Pro")
st.caption(f"Analyzing {analysis_mode} data for {target_date}")

# Fetch Data
df_pc, period_text = get_pc_analysis(target_date, analysis_mode)
df_toggl = get_toggl_analysis(target_date, analysis_mode)
    st.subheader(f"⏱️ Toggl 作業記録 {analysis_mode}")
    c3, c4 = st.columns([2, 1])
    with c3: st.plotly_chart(px.bar(df_toggl, x='作業内容', y='時間(h)', color='作業内容', text_auto=True), use_container_width=True)
    with c4: st.table(df_toggl)
else: st.warning(f"⚠️ {target_date} の Toggl 記録が見つかりません。")
