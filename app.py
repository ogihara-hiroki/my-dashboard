import streamlit as st
import requests, base64, pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta

# --- 設定 ---
ASANA_TOKEN = '2/1202260582260384/1213620305884302:3b2113ab646543840f0e4192076e7c08'
ASANA_WORKSPACE_ID = '1200313649553191'
TOGGL_TOKEN = '2236bb0c27861b351b5546732733043e'
TOGGL_WORKSPACE_ID = '8358873'

st.set_page_config(page_title="Work Analysis Pro", layout="wide")
st.sidebar.header("表示設定")
target_date = st.sidebar.date_input("分析したい日を選択:", date.today())

st.title(f"📊 業務詳細分析: {target_date}")

# --- 1. Toggl/Asanaデータ取得（以前と同じ） ---
@st.cache_data(ttl=60)
def get_base_data(target_date_val):
    start_dt = datetime.combine(target_date_val, datetime.min.time())
    end_dt = datetime.combine(target_date_val, datetime.max.time())
    auth = base64.b64encode(f"{TOGGL_TOKEN}:api_token".encode()).decode()
    t_url = f"https://api.track.toggl.com/reports/api/v3/workspace/{TOGGL_WORKSPACE_ID}/summary/time_entries"
    t_res = requests.post(t_url, headers={'Authorization': f'Basic {auth}', 'Content-Type': 'application/json'}, 
                          json={"start_date": start_dt.strftime('%Y-%m-%d'), "end_date": end_dt.strftime('%Y-%m-%d')}).json()
    
    toggl_actuals = {}
    if 'groups' in t_res:
        for group in t_res['groups']:
            for sub in group.get('sub_groups', []):
                title = sub.get('title') or "名称未設定"
                sec = sub.get('seconds', 0)
                toggl_actuals[title] = toggl_actuals.get(title, 0) + (sec / 3600)
    return toggl_actuals

# --- 2. PC操作ログの解析 ---
def analyze_pc_log(target_date_val):
    try:
        # GitHubにアップしたCSVを読み込む
        url = "https://raw.githubusercontent.com/ogihara-hiroki/my-dashboard/main/pc_usage_log.csv"
        df_log = pd.read_csv(url)
        df_log['timestamp'] = pd.to_datetime(df_log['timestamp'])
        
        # 選択した日付のデータのみ抽出
        df_day = df_log[df_log['timestamp'].dt.date == target_date_val].copy()
        
        if df_day.empty:
            return None

        # アプリ名の簡易判定
        def detect_app(title):
            title = str(title).lower()
            if 'excel' in title: return 'Excel (作業/資料)'
            if 'chrome' in title or 'edge' in title: return 'ブラウザ (調査/メール)'
            if 'visual studio' in title or 'vscode' in title: return 'IDE (開発)'
            if 'エクスプローラー' in title or 'folder' in title: return 'フォルダ (探す無駄)'
            if 'teams' in title or 'slack' in title or 'outlook' in title: return '連絡対応'
            return 'その他'

        df_day['app'] = df_day['window_title'].apply(detect_app)
        app_counts = df_day['app'].value_counts() * 10 / 3600 # 10秒おきなので時間に変換
        return app_counts
    except:
        return None

# 実行
toggl_data = get_base_data(target_date)
pc_counts = analyze_pc_log(target_date)

# 表示
if toggl_data:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("🛠 タスク別実績 (Toggl)")
        df_t = pd.DataFrame(list(toggl_data.items()), columns=['タスク', '時間(h)']).sort_values('時間(h)', ascending=False)
        st.plotly_chart(px.pie(df_t, values='時間(h)', names='タスク', hole=0.4), use_container_width=True)

    with col2:
        st.subheader("💻 実際の操作内訳 (PC Log)")
        if pc_counts is not None:
            df_pc = pd.DataFrame({'アプリ': pc_counts.index, '時間(h)': pc_counts.values})
            st.plotly_chart(px.pie(df_pc, values='時間(h)', names='アプリ', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu), use_container_width=True)
        else:
            st.info("この日のPC操作ログがGitHubにありません。")

    if pc_counts is not None and 'フォルダ (探す無駄)' in pc_counts:
        waste_min = pc_counts['フォルダ (探す無駄)'] * 60
        if waste_min > 10:
            st.warning(f"⚠️ 【無駄発見】今日は「資料探し（フォルダ操作）」に **{waste_min:.1f}分** 使っています。よく使うフォルダをAsanaにリンクしませんか？")
else:
    st.info("データがありません。")
