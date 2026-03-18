import streamlit as st
import requests, base64, pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import urllib3

# SSL警告を非表示にする
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 設定 ---
GITHUB_TOKEN = st.secrets["MY_GITHUB_TOKEN"]
REPO_NAME = 'ogihara-hiroki/my-dashboard'
STATUS_FILE = 'status.txt'
TOGGL_TOKEN = '2236bb0c27861b351b5546732733043e'
TOGGL_WORKSPACE_ID = '8358873'

st.set_page_config(page_title="Work Analysis Pro", layout="wide")

# --- 1. GitHubのリモコン状態を更新する関数 ---
def update_github_status(status_text):
    try:
        url = f"https://api.github.com/repos/{REPO_NAME}/contents/{STATUS_FILE}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        res = requests.get(url, headers=headers).json()
        if 'sha' not in res: return
        sha = res['sha']
        content = base64.b64encode(status_text.encode('utf-8')).decode('utf-8')
        data = {"message": f"Switch to {status_text}", "content": content, "sha": sha}
        requests.put(url, headers=headers, json=data)
    except:
        pass

# --- 2. PC操作ログを解析する関数 ---
def get_pc_analysis(target_date_val, mode="日次"):
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
            df_filtered = df_log[(df_log['timestamp'].dt.date >= start_of_week) & 
                                 (df_log['timestamp'].dt.date <= end_of_week)].copy()
            period_text = f"({start_of_week} 〜 {end_of_week})"

        if df_filtered.empty: return None, period_text

        def detect_app(title):
            title = str(title).lower()
            if 'automation studio' in title: return 'Automation Studio (設計)'
            if 'visual studio' in title or 'vscode' in title: return 'IDE (開発)'
            if 'excel' in title: return 'Excel (作業/資料)'
            if 'chrome' in title or 'edge' in title: return 'ブラウザ (調査/メール)'
            if 'エクスプローラー' in title or 'folder' in title: return 'フォルダ (探す無駄)'
            return 'その他'

        df_filtered['アプリ'] = df_filtered['window_title'].apply(detect_app)
        df_res = df_filtered['アプリ'].value_counts().reset_index()
        df_res.columns = ['アプリ', '合計時間(h)']
        df_res['合計時間(h)'] = round(df_res['合計時間(h)'] * 10 / 3600, 2)
        return df_res, period_text
    except:
        return None, ""

# --- 3. Togglからデータを取得する関数 (時差・詳細取得対策版) ---
def get_toggl_analysis(target_date_val, mode="日次"):
    try:
        # 時差対策: 日本時間(JST)の開始と終了を明示する
        if mode == "日次":
            start_dt = datetime.combine(target_date_val, datetime.min.time())
            end_dt = datetime.combine(target_date_val, datetime.max.time())
        else:
            start_of_week = target_date_val - timedelta(days=target_date_val.weekday())
            start_dt = datetime.combine(start_of_week, datetime.min.time())
            end_dt = datetime.combine(start_of_week + timedelta(days=6), datetime.max.time())

        # ISO形式に変換
        start_date_str = start_dt.strftime('%Y-%m-%dT%H:%M:%S')
        end_date_str = end_dt.strftime('%Y-%m-%dT%H:%M:%S')

        # Toggl Reports API v3 (Summary)
        url = f"https://api.track.toggl.com/reports/api/v3/workspace/{TOGGL_WORKSPACE_ID}/summary/time_entries"
        auth = base64.b64encode(f"{TOGGL_TOKEN}:api_token".encode()).decode()
        headers = {
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json"
        }
        # 日本時間を考慮するためタイムゾーンを指定（必要に応じて）
        payload = {
            "start_date": start_date_str,
            "end_date": end_date_str
        }
        
        res = requests.post(url, headers=headers, json=payload)
        
        if res.status_code != 200:
            st.error(f"Toggl APIエラー: {res.status_code}")
            return None
        
        report_data = res.json()
        entries = []
        for item in report_data:
            project = item.get('title', {}).get('project', 'なし') or 'なし'
            duration = item.get('seconds', 0) / 3600
            if duration > 0:
                entries.append({'プロジェクト': project, '時間(h)': round(duration, 2)})
        
        return pd.DataFrame(entries) if entries else None
    except Exception as e:
        st.error(f"Toggl接続エラー: {e}")
        return None

# --- サイドバー構成 ---
st.sidebar.header("表示設定")
analysis_mode = st.sidebar.radio("分析範囲:", ["日次", "週次"])
target_date = st.sidebar.date_input("基準日:", date.today())

st.sidebar.markdown("---")
st.sidebar.header("PCログリモコン")
remote_on = st.sidebar.checkbox("PCログ記録を開始")
if remote_on:
    update_github_status("ON")
    st.sidebar.success("指示を送信: ON")
else:
    update_github_status("OFF")
    st.sidebar.warning("指示を送信: OFF")

# --- メイン表示 ---
st.title(f"📊 業務分析: {analysis_mode}")

# A. PC操作ログ
df_pc, period_text = get_pc_analysis(target_date, analysis_mode)
if df_pc is not None:
    st.subheader(f"💻 PC操作ログの内訳 {period_text}")
    c1, c2 = st.columns([2, 1])
    with c1:
        st.plotly_chart(px.pie(df_pc, values='合計時間(h)', names='アプリ', hole=0.4), use_container_width=True)
    with c2:
        st.table(df_pc)
else:
    st.info(f"💡 PCログはありません。")

st.markdown("---")

# B. Toggl 作業記録
df_toggl = get_toggl_analysis(target_date, analysis_mode)
if df_toggl is not None:
    st.subheader(f"⏱️ Toggl 作業記録 {analysis_mode}")
    c3, c4 = st.columns([2, 1])
    with c3:
        st.plotly_chart(px.bar(df_toggl, x='プロジェクト', y='時間(h)', color='プロジェクト', text_auto=True), use_container_width=True)
    with c4:
        st.table(df_toggl)
else:
    st.warning(f"⚠️ {target_date} の Toggl 記録が見つかりません。")
