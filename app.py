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

# --- 2. Asana予定取得 ---
def get_asana_plan(target_date_val):
    try:
        url = "https://app.asana.com/api/1.0/tasks"
        headers = {"Authorization": f"Bearer {ASANA_TOKEN}"}
        params = {"workspace": ASANA_WORKSPACE_ID, "assignee": "me", "opt_fields": "name,due_on,custom_fields"}
        res = requests.get(url, headers=headers, params=params)
        if res.status_code != 200: return None
        tasks = res.json().get('data', [])
        plan_data = []
        for t in tasks:
            if t.get('due_on') == target_date_val.strftime('%Y-%m-%d'):
                estimate = 0
                for cf in t.get('custom_fields', []):
                    if '予定' in cf.get('name', '') or 'Estimate' in cf.get('name', ''):
                        estimate = cf.get('number_value') or 0
                plan_data.append({"作業内容": t['name'], "予定(h)": estimate})
        return pd.DataFrame(plan_data) if plan_data else None
    except: return None

# --- 3. Toggl実績取得 (最も確実な Time Entries API 方式) ---
def get_toggl_do(target_date_val, mode="日次"):
    try:
        # 日本時間の開始と終了を ISO8601 形式で作成 (JST)
        start_dt = datetime.combine(target_date_val, datetime.min.time()) - timedelta(hours=9)
        end_dt = datetime.combine(target_date_val, datetime.max.time()) - timedelta(hours=9)
        
        start_str = start_dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        end_str = end_dt.strftime('%Y-%m-%dT%H:%M:%SZ')

        # Workspace ID を使わない最も原始的なエンドポイント
        url = f"https://api.track.toggl.com/api/v9/me/time_entries"
        auth = base64.b64encode(f"{TOGGL_TOKEN}:api_token".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
        
        params = {"start_date": start_str, "end_date": end_str}
        res = requests.get(url, headers=headers, params=params)
        
        if res.status_code != 200:
            st.error(f"Toggl通信失敗: {res.status_code}")
            return None
        
        raw_data = res.json()
        if not raw_data: return None
        
        entries = []
        for item in raw_data:
            desc = item.get('description') or "名称未設定"
            dur = item.get('duration', 0)
            if dur > 0:
                # ★修正：小数点第1位に丸める
                entries.append({'作業内容': desc, '実績(h)': round(dur / 3600, 1)})
         
        df = pd.DataFrame(entries).groupby('作業内容')['実績(h)'].sum().reset_index()
        
        # ★修正：実績(h)の大きい順に並べ替える
        df = df.sort_values('実績(h)', ascending=False)
        return df
    except Exception as e:
        st.error(f"Togglエラー: {e}")
        return None

# --- UIメイン ---
st.sidebar.header("🗓️ PDCA設定")
target_date = st.sidebar.date_input("基準日:", date.today())

st.title(f"🚀 Work PDCA Dashboard")

df_plan = get_asana_plan(target_date)
df_do = get_toggl_do(target_date)

st.header("🔍 予実分析 (Plan vs Do)")

if df_do is not None:
    if df_plan is not None:
        df_merge = pd.merge(df_plan, df_do, on="作業内容", how="outer").fillna(0)
    else:
        df_merge = df_do.copy()
        df_merge["予定(h)"] = 0
    
   # 差分計算も小数点第1位に
    df_merge['差分(h)'] = (df_merge['実績(h)'] - df_merge['予定(h)']).round(1)
    
    c1, c2 = st.columns([2, 1])
    with c1:
        # category_orders を指定して、df の並び順（実績順）をグラフに反映させる
        fig = px.bar(df_merge, x="作業内容", y=["予定(h)", "実績(h)"], 
                     barmode="group", text_auto='.1f',
                     category_orders={"作業内容": df_merge["作業内容"].tolist()})
        st.plotly_chart(fig, use_container_width=True)
        
    with c2:
        st.write("📊 予実詳細（h）")
        # 表の表示も第1位までに制限
        st.table(df_merge.style.format("{:.1f}", subset=["予定(h)", "実績(h)", "差分(h)"]))
else:
    st.warning(f"⚠️ {target_date} の Toggl 記録が見つかりません。")
