import streamlit as st
import requests, base64, pandas as pd
import plotly.express as px
from datetime import datetime, date

# --- 設定（★ここをご自身のトークンに書き換えてください） ---
GITHUB_TOKEN = st.secrets["MY_GITHUB_TOKEN"]
REPO_NAME = 'ogihara-hiroki/my-dashboard'
ASANA_TOKEN = '2/1202260582260384/1213620305884302:3b2113ab646543840f0e4192076e7c08'
TOGGL_TOKEN = '2236bb0c27861b351b5546732733043e'
TOGGL_WORKSPACE_ID = '8358873'

st.set_page_config(page_title="Work Analysis Pro", layout="wide")

# --- 1. GitHubのリモコン状態を更新する関数 ---
def update_github_status(status_text):
    try:
        url = f"https://api.github.com/repos/{REPO_NAME}/contents/status.txt"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        res = requests.get(url, headers=headers).json()
        if 'sha' not in res: return
        data = {
            "message": f"Switch to {status_text}",
            "content": base64.b64encode(status_text.encode()).decode(),
            "sha": res['sha']
        }
        requests.put(url, headers=headers, json=data)
    except:
        pass

# --- 2. データ取得・解析関数 ---
@st.cache_data(ttl=60)
def get_toggl_data(target_date_val):
    start_dt = datetime.combine(target_date_val, datetime.min.time())
    end_dt = datetime.combine(target_date_val, datetime.max.time())
    auth = base64.b64encode(f"{TOGGL_TOKEN}:api_token".encode()).decode()
    t_url = f"https://api.track.toggl.com/reports/api/v3/workspace/{TOGGL_WORKSPACE_ID}/summary/time_entries"
    t_res = requests.post(t_url, headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/json'}, 
                          json={"start_date": start_dt.strftime('%Y-%m-%d'), "end_date": end_dt.strftime('%Y-%m-%d')}).json()
    results = []
    if 'groups' in t_res:
        for group in t_res['groups']:
            for sub in group.get('sub_groups', []):
                title = sub.get('title') or "名称未設定"
                sec = sub.get('seconds', 0)
                if sec > 0:
                    results.append({"タスク名": title, "実績(h)": round(sec / 3600, 2)})
    return pd.DataFrame(results)

def get_pc_analysis(target_date_val):
    try:
        url = f"https://raw.githubusercontent.com/{REPO_NAME}/main/pc_usage_log.csv"
        df_log = pd.read_csv(url)
        df_log['timestamp'] = pd.to_datetime(df_log['timestamp'])
        df_day = df_log[df_log['timestamp'].dt.date == target_date_val].copy()
        if df_day.empty: return None
        def detect_app(title):
            title = str(title).lower()
            if 'excel' in title: return 'Excel (作業/資料)'
            if 'chrome' in title or 'edge' in title: return 'ブラウザ (調査/メール)'
            if 'visual studio' in title or 'vscode' in title: return 'IDE (開発)'
            if 'エクスプローラー' in title or 'folder' in title: return 'フォルダ (探す無駄)'
            return 'その他'
        df_day['アプリ'] = df_day['window_title'].apply(detect_app)
        df_pc = df_day['アプリ'].value_counts().reset_index()
        df_pc.columns = ['アプリ', '操作時間(h)']
        df_pc['操作時間(h)'] = round(df_pc['操作時間(h)'] * 10 / 3600, 2)
        return df_pc
    except:
        return None

# --- サイドバー構成 ---
st.sidebar.header("表示設定")
target_date = st.sidebar.date_input("分析したい日を選択:", date.today())

st.sidebar.markdown("---")
st.sidebar.subheader("PCログリモコン")
if "last_status" not in st.session_state:
    st.session_state.last_status = "OFF"

toggle = st.sidebar.checkbox("PCログ記録を開始")
current_status = "ON" if toggle else "OFF"

if current_status != st.session_state.last_status:
    update_github_status(current_status)
    st.session_state.last_status = current_status
    st.sidebar.success(f"指示を送信: {current_status}")

if toggle:
    st.sidebar.info("🚀 PC側で記録中です...")
else:
    st.sidebar.warning("💤 記録停止中")

# --- メイン表示エリア ---
st.title(f"📊 業務分析: {target_date}")

df_t = get_toggl_data(target_date)

if not df_t.empty:
    st.metric("今日の総稼働時間", f"{df_t['実績(h)'].sum():.2f} 時間")
    
    # グラフ
    df_plot = df_t.sort_values("実績(h)", ascending=True)
    fig_t = px.bar(df_plot, x="実績(h)", y="タスク名", orientation='h', 
                   title="タスク別実績時間", color="実績(h)", color_continuous_scale="Blues")
    st.plotly_chart(fig_t, use_container_width=True)

    # 表
    st.subheader("📋 詳細データテーブル")
    st.dataframe(df_t.sort_values("実績(h)", ascending=False), use_container_width=True)

    # PCログ（折りたたみ）
    st.markdown("---")
    with st.expander("💻 PC操作ログの内訳を確認"):
        df_pc = get_pc_analysis(target_date)
        if df_pc is not None:
            c1, c2 = st.columns([1, 1])
            with c1:
                st.plotly_chart(px.bar(df_pc, x="操作時間(h)", y="アプリ", orientation='h', color="アプリ"), use_container_width=True)
            with c2:
                st.table(df_pc)
        else:
            st.info("この日のPC操作ログがGitHubに見つかりません。")
else:
    st.info(f"{target_date} のデータはありません。")
