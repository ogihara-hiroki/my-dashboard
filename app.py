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

st.title(f"📊 業務分析: {target_date}")

# --- 1. Togglデータ取得 ---
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

# --- 2. PC操作ログ解析 ---
def get_pc_analysis(target_date_val):
    try:
        url = "https://raw.githubusercontent.com/ogihara-hiroki/my-dashboard/main/pc_usage_log.csv"
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

# --- 表示メイン ---
df_t = get_toggl_data(target_date)

if not df_t.empty:
    # 1. サマリー表示
    total_h = df_t['実績(h)'].sum()
    st.metric("今日の総稼働時間", f"{total_h:.2f} 時間")
    
    # 2. 横棒グラフ（以前のスタイル）
    df_plot = df_t.sort_values("実績(h)", ascending=True)
    fig_t = px.bar(df_plot, x="実績(h)", y="タスク名", orientation='h', 
                   title="タスク別実績時間（グラフ）", color="実績(h)", color_continuous_scale="Blues")
    st.plotly_chart(fig_t, use_container_width=True)

    # 3. 詳細表（今回追加）
    st.subheader("📋 詳細データテーブル")
    st.dataframe(df_t.sort_values("実績(h)", ascending=False), use_container_width=True)

    # 4. PCログ（折りたたみ式）
    st.markdown("---")
    with st.expander("💻 PC操作ログから見る「実際の動き」の内訳を確認"):
        df_pc = get_pc_analysis(target_date)
        if df_pc is not None:
            c1, c2 = st.columns([1, 1])
            with c1:
                st.plotly_chart(px.bar(df_pc, x="操作時間(h)", y="アプリ", orientation='h', color="アプリ"), use_container_width=True)
            with c2:
                st.write("アプリ別操作合計時間:")
                st.table(df_pc)
        else:
            st.info("この日のPC操作ログがGitHubに見つかりません。")
else:
    st.info(f"{target_date} のデータはありません。")
