import streamlit as st
import requests, base64, pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 設定 ---
GITHUB_TOKEN = st.secrets["MY_GITHUB_TOKEN"]
REPO_NAME = 'ogihara-hiroki/my-dashboard'
STATUS_FILE = 'status.txt'
TOGGL_TOKEN = '2236bb0c27861b351b5546732733043e'
ASANA_TOKEN = '2/1202260582260384/1213620305884302:3b2113ab646543840f0e4192076e7c08'
ASANA_WORKSPACE_ID = '1200313649553191'

st.set_page_config(page_title="Work PDCA Dashboard", layout="wide")

# --- 1. GitHubリモコン ---
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
    except: pass

# --- 2. Asana予定取得 (完了状態も取得) ---
def get_asana_plan(target_date_val):
    try:
        url = "https://app.asana.com/api/1.0/tasks"
        headers = {"Authorization": f"Bearer {ASANA_TOKEN}"}
        # opt_fields に 'completed' を追加
        params = {"workspace": ASANA_WORKSPACE_ID, "assignee": "me", "opt_fields": "name,due_on,custom_fields,completed"}
        res = requests.get(url, headers=headers, params=params)
        if res.status_code != 200: return None
        tasks = res.json().get('data', [])
        plan_data = []
        for t in tasks:
            if t.get('due_on') == target_date_val.strftime('%Y-%m-%d'):
                # 完了していたら名前にチェックを入れる
                status_mark = "✅ " if t.get('completed') else ""
                display_name = status_mark + t['name']
                
                estimate = 0
                for cf in t.get('custom_fields', []):
                    if '予定' in cf.get('name', '') or 'Estimate' in cf.get('name', ''):
                        estimate = cf.get('number_value') or 0
                plan_data.append({"作業内容": display_name, "予定(h)": estimate})
        return pd.DataFrame(plan_data) if plan_data else None
    except: return None

# --- 3. Toggl実績取得 (Time Entries API) ---
def get_toggl_do(target_date_val):
    try:
        start_dt = datetime.combine(target_date_val, datetime.min.time()) - timedelta(hours=9)
        end_dt = datetime.combine(target_date_val, datetime.max.time()) - timedelta(hours=9)
        start_str = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_str = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        url = f"https://api.track.toggl.com/api/v9/me/time_entries"
        auth = base64.b64encode(f"{TOGGL_TOKEN}:api_token".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        
        params = {"start_date": start_str, "end_date": end_str}
        res = requests.get(url, headers=headers, params=params)
        if res.status_code != 200: return None
        
        raw_data = res.json()
        if not raw_data: return None
        
        entries = []
        for item in raw_data:
            desc = item.get('description') or "名称未設定"
            dur = item.get('duration', 0)
            if dur > 0:
                entries.append({'作業内容': desc, '実績(h)': round(dur / 3600, 1)})
         
        df = pd.DataFrame(entries).groupby('作業内容')['実績(h)'].sum().reset_index()
        return df
    except: return None

# --- UIメイン ---
st.sidebar.header("🗓️ PDCA設定")
target_date = st.sidebar.date_input("基準日:", date.today())

st.title(f"🚀 Work PDCA Dashboard")

df_plan = get_asana_plan(target_date)
df_do = get_toggl_do(target_date)

st.header("🔍 予実分析 (Plan vs Do)")

if df_do is not None:
    # --- データの結合と整理 ---
    if df_plan is not None:
        df_merge = pd.merge(df_plan, df_do, on="作業内容", how="outer").fillna(0)
    else:
        df_merge = df_do.copy()
        df_merge["予定(h)"] = 0

# 差分計算と並び替え
    df_merge['差分(h)'] = (df_merge['実績(h)'] - df_merge['予定(h)']).round(1)
    df_merge = df_merge.sort_values('実績(h)', ascending=False)

    # --- 合計行の作成 ---
    total_plan = df_merge['予定(h)'].sum()
    total_do = df_merge['実績(h)'].sum()
    total_diff = df_merge['差分(h)'].sum()

    # --- 表示 ---
    c1, c2 = st.columns([2, 1])
    with c1:
        fig = px.bar(df_merge, x="作業内容", y=["予定(h)", "実績(h)"], 
                     barmode="group", text_auto='.1f',
                     category_orders={"作業内容": df_merge["作業内容"].tolist()})
        st.plotly_chart(fig, use_container_width=True)
        
        # 合計時間のサマリーを表示
        st.metric(label="本日の総実績時間", value=f"{total_do:.1f} h", delta=f"予実差 {total_diff:.1f} h")
        
    with c2:
        st.write("📊 予実詳細（h）")
        # 完了マークの反映（Asanaから取得したデータに完了フラグがある場合）
        # ※ get_asana_planで 'completed' フィールドを取得するように修正が必要です
        st.table(df_merge.style.format("{:.1f}", subset=["予定(h)", "実績(h)", "差分(h)"]))

        # 末尾に合計を表示する簡易テーブル
        st.markdown(f"""
        | 項目 | 合計 |
        | :--- | :--- |
        | **予定合計** | **{total_plan:.1f} h** |
        | **実績合計** | **{total_do:.1f} h** |
        """)
else:
    st.warning(f"⚠️ {target_date} の Toggl 記録が見つかりません。")
